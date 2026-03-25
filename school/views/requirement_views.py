# school/views/requirement_views.py
# ─────────────────────────────────────────────────────────────────────────────
# All SchoolRequirement views.
#
# Views:
#   requirement_list       — list with full stats and filters
#   requirement_add        — add a new requirement
#   requirement_edit       — edit an existing requirement
#   requirement_delete     — confirm + perform deletion
#   requirement_duplicate  — clone an object then redirect to edit the clone
#   requirement_toggle_published — POST-only quick publish/unpublish toggle
#
# Rules:
#   - Function-based views only
#   - No Django Forms / forms.py
#   - No Class-based Views
#   - No JSON responses
#   - Manual validation via requirement_utils
#   - django.contrib.messages for all feedback
#   - login_required on every view
# ─────────────────────────────────────────────────────────────────────────────

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from academics.models import SchoolClass, Term
from school.models import SchoolRequirement
from school.utils.requirement_utils import (
    CATEGORY_LABELS,
    get_requirement_list_stats,
    validate_and_parse_requirement,
)

_T = 'school/requirements/'

# Choice list passed to every form template
_CATEGORY_CHOICES = list(CATEGORY_LABELS.items())

# Level choices for the class filter dropdown
_CLASS_LEVEL_CHOICES = [
    ('baby',   'Baby Class'), ('middle', 'Middle Class'), ('top', 'Top Class'),
    ('p1', 'P1'), ('p2', 'P2'), ('p3', 'P3'), ('p4', 'P4'),
    ('p5', 'P5'), ('p6', 'P6'), ('p7', 'P7'),
]


# ── Private helpers ────────────────────────────────────────────────────────────

def _get_form_lookups() -> dict:
    """
    Returns the querysets / choice lists every form needs:
    all active classes and all terms, ordered for display.
    """
    return {
        'all_classes':       SchoolClass.objects.filter(
                                 is_active=True
                             ).order_by('section', 'level', 'stream'),
        'all_terms':         Term.objects.all().order_by('-start_date'),
        'category_choices':  _CATEGORY_CHOICES,
    }


def _apply_to_instance(instance: SchoolRequirement, cleaned: dict) -> None:
    """
    Write cleaned scalar and FK fields onto a SchoolRequirement instance.
    Handles the school_class_id / term_id → FK resolution safely.
    """
    # Scalar fields
    scalar_fields = ('title', 'description', 'category',
                     'estimated_cost', 'is_compulsory', 'is_published')
    for f in scalar_fields:
        if f in cleaned:
            setattr(instance, f, cleaned[f])

    # FK fields — set via _id to avoid extra DB queries
    if 'school_class_id' in cleaned:
        instance.school_class_id = cleaned['school_class_id']
    if 'term_id' in cleaned:
        instance.term_id = cleaned['term_id']


# ═══════════════════════════════════════════════════════════════════════════════
#  1. REQUIREMENTS LIST
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def requirement_list(request):
    """
    All school requirements with full statistics and filters.

    Filters (all via GET params):
      ?q=search           — title / description full-text search
      ?category=          — stationery | uniform | scholastic | sports |
                            equipment | other
      ?published=1|0      — published or draft
      ?compulsory=1|0     — compulsory or optional
      ?term=<id>          — filter by term FK
      ?class=<level>      — filter by class level (e.g. p3, p6)
      ?scope=wide|class   — school-wide or class-specific

    Stats cards:
      total, published, draft, compulsory, optional,
      school-wide, class-specific, by-category breakdown,
      total estimated cost of published compulsory items.
    """
    qs = SchoolRequirement.objects.select_related(
        'school_class', 'term', 'created_by'
    ).order_by('-created_at')

    # ── Filters ───────────────────────────────────────────────────────────────
    search            = request.GET.get('q', '').strip()
    category_filter   = request.GET.get('category', '').strip()
    published_filter  = request.GET.get('published', '').strip()
    compulsory_filter = request.GET.get('compulsory', '').strip()
    term_filter       = request.GET.get('term', '').strip()
    class_filter      = request.GET.get('class', '').strip()
    scope_filter      = request.GET.get('scope', '').strip()

    if search:
        qs = qs.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search)
        )

    if category_filter:
        qs = qs.filter(category=category_filter)

    if published_filter == '1':
        qs = qs.filter(is_published=True)
    elif published_filter == '0':
        qs = qs.filter(is_published=False)

    if compulsory_filter == '1':
        qs = qs.filter(is_compulsory=True)
    elif compulsory_filter == '0':
        qs = qs.filter(is_compulsory=False)

    if term_filter:
        qs = qs.filter(term__pk=term_filter)

    if class_filter:
        qs = qs.filter(school_class__level=class_filter)

    if scope_filter == 'wide':
        qs = qs.filter(school_class__isnull=True)
    elif scope_filter == 'class':
        qs = qs.filter(school_class__isnull=False)

    # ── Pagination ────────────────────────────────────────────────────────────
    paginator = Paginator(qs, 20)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    # ── Stats ─────────────────────────────────────────────────────────────────
    stats = get_requirement_list_stats()

    context = {
        'requirements':       page_obj.object_list,
        'page_obj':           page_obj,
        # active filters — returned to template to pre-select form controls
        'search':             search,
        'category_filter':    category_filter,
        'published_filter':   published_filter,
        'compulsory_filter':  compulsory_filter,
        'term_filter':        term_filter,
        'class_filter':       class_filter,
        'scope_filter':       scope_filter,
        # filter choice lists
        'category_choices':   _CATEGORY_CHOICES,
        'class_level_choices': _CLASS_LEVEL_CHOICES,
        'category_labels':    CATEGORY_LABELS,
        **stats,
    }
    return render(request, f'{_T}list.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  2. ADD REQUIREMENT
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def requirement_add(request):
    """
    Add a new school requirement.
    GET  — blank form with class and term dropdowns.
    POST — validate; save on success; re-render with per-field errors on failure.
    """
    lookups = _get_form_lookups()

    if request.method == 'GET':
        # Pre-select current term if one is active
        current_term = Term.objects.filter(is_current=True).first()
        return render(request, f'{_T}form.html', {
            'form_title':    'Add Requirement',
            'action':        'add',
            'post':          {},
            'errors':        {},
            'current_term':  current_term,
            **lookups,
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    cleaned, errors = validate_and_parse_requirement(request.POST)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}form.html', {
            'form_title': 'Add Requirement',
            'action':     'add',
            'post':       request.POST,
            'errors':     errors,
            **lookups,
        })

    try:
        with transaction.atomic():
            req = SchoolRequirement()
            _apply_to_instance(req, cleaned)
            req.created_by = request.user
            req.save()
    except Exception as exc:
        messages.error(request, f'Could not save requirement: {exc}')
        return render(request, f'{_T}form.html', {
            'form_title': 'Add Requirement',
            'action':     'add',
            'post':       request.POST,
            'errors':     {},
            **lookups,
        })

    messages.success(request, f'Requirement "{req.title}" has been added successfully.')
    return redirect('school:requirement_list')


# ═══════════════════════════════════════════════════════════════════════════════
#  3. EDIT REQUIREMENT
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def requirement_edit(request, pk):
    """
    Edit an existing school requirement.
    GET  — form pre-filled with current values.
    POST — validate; save; re-render with errors on failure.
    """
    req     = get_object_or_404(SchoolRequirement, pk=pk)
    lookups = _get_form_lookups()

    if request.method == 'GET':
        return render(request, f'{_T}form.html', {
            'requirement': req,
            'form_title':  f'Edit — {req.title}',
            'action':      'edit',
            'post':        {},
            'errors':      {},
            **lookups,
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    cleaned, errors = validate_and_parse_requirement(request.POST, instance=req)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}form.html', {
            'requirement': req,
            'form_title':  f'Edit — {req.title}',
            'action':      'edit',
            'post':        request.POST,
            'errors':      errors,
            **lookups,
        })

    try:
        with transaction.atomic():
            _apply_to_instance(req, cleaned)
            req.save()
    except Exception as exc:
        messages.error(request, f'Could not update requirement: {exc}')
        return render(request, f'{_T}form.html', {
            'requirement': req,
            'form_title':  f'Edit — {req.title}',
            'action':      'edit',
            'post':        request.POST,
            'errors':      {},
            **lookups,
        })

    messages.success(request, f'Requirement "{req.title}" has been updated.')
    return redirect('school:requirement_list')


# ═══════════════════════════════════════════════════════════════════════════════
#  4. DELETE REQUIREMENT
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def requirement_delete(request, pk):
    """
    Delete a school requirement.
    GET  — confirmation page showing the requirement details.
    POST — perform deletion, redirect to list.
    """
    req = get_object_or_404(SchoolRequirement, pk=pk)

    if request.method == 'GET':
        return render(request, f'{_T}delete_confirm.html', {
            'requirement': req,
            'category_label': CATEGORY_LABELS.get(req.category, req.category),
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    title = req.title
    try:
        req.delete()
        messages.success(request, f'Requirement "{title}" has been permanently deleted.')
    except Exception as exc:
        messages.error(request, f'Could not delete requirement: {exc}')

    return redirect('school:requirement_list')


# ═══════════════════════════════════════════════════════════════════════════════
#  5. DUPLICATE REQUIREMENT
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def requirement_duplicate(request, pk):
    """
    Duplicate a requirement then immediately redirect to edit the new copy.

    Flow:
      POST /requirements/<pk>/duplicate/
        → clones the object
        → prefixes title with "Copy of …"
        → sets is_published=False on the duplicate (draft until reviewed)
        → sets created_by to the current user
        → redirects to requirement_edit for the new duplicate

    This allows a user to take an existing Term 1 requirement list item
    and quickly adapt it for Term 2 without starting from scratch.

    Only accepts POST to prevent accidental duplicate-on-page-refresh.
    """
    if request.method != 'POST':
        messages.warning(request, 'Invalid request method.')
        return redirect('school:requirement_list')

    original = get_object_or_404(SchoolRequirement, pk=pk)

    try:
        with transaction.atomic():
            duplicate = SchoolRequirement(
                title           = f'Copy of {original.title}',
                description     = original.description,
                category        = original.category,
                school_class    = original.school_class,
                term            = original.term,
                estimated_cost  = original.estimated_cost,
                is_compulsory   = original.is_compulsory,
                is_published    = False,       # always a draft until explicitly published
                created_by      = request.user,
            )
            duplicate.save()
    except Exception as exc:
        messages.error(request, f'Could not duplicate requirement: {exc}')
        return redirect('school:requirement_list')

    messages.info(
        request,
        f'A copy of "{original.title}" has been created as a draft. '
        f'Review and update the details below before publishing.'
    )
    # Redirect straight to edit so user can update the duplicate immediately
    return redirect('school:requirement_edit', pk=duplicate.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  6. TOGGLE PUBLISHED  (POST-only quick action)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def requirement_toggle_published(request, pk):
    """
    Quick POST-only toggle for is_published.
    Flips the published state without opening the full edit form.
    Redirects back to the referring page (list or wherever).
    """
    if request.method != 'POST':
        messages.warning(request, 'Invalid request method.')
        return redirect('school:requirement_list')

    req = get_object_or_404(SchoolRequirement, pk=pk)
    req.is_published = not req.is_published
    req.save(update_fields=['is_published'])

    state = 'published' if req.is_published else 'unpublished (draft)'
    messages.success(request, f'"{req.title}" has been {state}.')

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('school:requirement_list')
