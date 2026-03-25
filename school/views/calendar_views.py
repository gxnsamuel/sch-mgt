# school/views/calendar_views.py
# ─────────────────────────────────────────────────────────────────────────────
# All SchoolCalendar views.
#
# Views:
#   calendar_list             — list with full stats and filters
#   calendar_add              — add a new calendar entry
#   calendar_edit             — edit an existing calendar entry
#   calendar_delete           — confirm + perform deletion
#   calendar_detail           — full single calendar page with milestones
#   calendar_toggle_published — POST-only quick publish/unpublish
#   calendar_toggle_active    — POST-only quick activate/deactivate
#
# Rules:
#   - Function-based views only
#   - No Django Forms / forms.py
#   - No Class-based Views
#   - No JSON responses
#   - Manual validation via calendar_utils
#   - django.contrib.messages for all feedback
#   - login_required on every view
# ─────────────────────────────────────────────────────────────────────────────

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from academics.models import Term
from school.models import SchoolCalendar
from school.utils.calendar_utils import (
    get_calendar_detail_stats,
    get_calendar_list_stats,
    validate_and_parse_calendar,
)

_T = 'school/calendars/'


# ── Private helpers ────────────────────────────────────────────────────────────

def _get_form_lookups() -> dict:
    """Querysets every calendar form template needs."""
    return {
        'all_terms': Term.objects.all().order_by('-start_date'),
    }


def _apply_to_instance(instance: SchoolCalendar, cleaned: dict) -> None:
    """Write cleaned scalar and FK fields onto a SchoolCalendar instance."""
    scalar_fields = (
        'title', 'academic_year', 'description', 'is_active', 'is_published',
    )
    for f in scalar_fields:
        if f in cleaned:
            setattr(instance, f, cleaned[f])

    if 'term_id' in cleaned:
        instance.term_id = cleaned['term_id']


# ═══════════════════════════════════════════════════════════════════════════════
#  1. CALENDAR LIST
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def calendar_list(request):
    """
    All school calendars with statistics and filters.

    Stats cards:
        total, published, draft, active, inactive,
        with/without document uploaded.
        By academic-year and by-term breakdowns.
        Current-year calendars strip.
        5 most recently published.

    Filters (GET — all stackable):
        ?q=           title / description search
        ?year=        academic_year value  (e.g. 2025)
        ?term=<id>    filter by term FK
        ?published=   1 | 0
        ?active=      1 | 0
        ?document=    1 (has document) | 0 (no document)
    """
    qs = SchoolCalendar.objects.select_related('term', 'created_by')

    # ── Filters ───────────────────────────────────────────────────────────────
    search           = request.GET.get('q', '').strip()
    year_filter      = request.GET.get('year', '').strip()
    term_filter      = request.GET.get('term', '').strip()
    published_filter = request.GET.get('published', '').strip()
    active_filter    = request.GET.get('active', '').strip()
    document_filter  = request.GET.get('document', '').strip()

    if search:
        qs = qs.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(academic_year__icontains=search)
        )

    if year_filter:
        qs = qs.filter(academic_year=year_filter)

    if term_filter:
        qs = qs.filter(term__pk=term_filter)

    if published_filter == '1':
        qs = qs.filter(is_published=True)
    elif published_filter == '0':
        qs = qs.filter(is_published=False)

    if active_filter == '1':
        qs = qs.filter(is_active=True)
    elif active_filter == '0':
        qs = qs.filter(is_active=False)

    if document_filter == '1':
        qs = qs.exclude(document='').exclude(document__isnull=True)
    elif document_filter == '0':
        qs = qs.filter(Q(document='') | Q(document__isnull=True))

    qs = qs.order_by('-academic_year', 'term__name')

    # ── Pagination ────────────────────────────────────────────────────────────
    paginator = Paginator(qs, 15)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    stats = get_calendar_list_stats()

    context = {
        'calendars':        page_obj.object_list,
        'page_obj':         page_obj,
        # active filters
        'search':           search,
        'year_filter':      year_filter,
        'term_filter':      term_filter,
        'published_filter': published_filter,
        'active_filter':    active_filter,
        'document_filter':  document_filter,
        # choice lists for filter controls
        'all_terms':        Term.objects.all().order_by('-start_date'),
        **stats,
    }
    return render(request, f'{_T}list.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  2. ADD CALENDAR
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def calendar_add(request):
    """
    Add a new school calendar entry.
    GET  — blank form; academic_year pre-filled with current year.
    POST — validate; save on success; re-render with per-field errors on failure.

    Uniqueness enforced: one calendar per term.
    """
    lookups = _get_form_lookups()

    if request.method == 'GET':
        from datetime import date
        current_term = Term.objects.filter(is_current=True).first()
        return render(request, f'{_T}form.html', {
            'form_title':    'Add School Calendar',
            'action':        'add',
            'post':          {},
            'errors':        {},
            'current_year':  str(date.today().year),
            'current_term':  current_term,
            **lookups,
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    cleaned, errors = validate_and_parse_calendar(request.POST, request.FILES)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}form.html', {
            'form_title': 'Add School Calendar',
            'action':     'add',
            'post':       request.POST,
            'errors':     errors,
            **lookups,
        })

    try:
        with transaction.atomic():
            cal = SchoolCalendar()
            _apply_to_instance(cal, cleaned)
            cal.created_by = request.user

            # Auto-stamp published_at when publishing for the first time
            if cal.is_published:
                cal.published_at = timezone.now()

            # Document upload
            if request.FILES.get('document'):
                cal.document = request.FILES['document']

            cal.save()

    except Exception as exc:
        messages.error(request, f'Could not save calendar: {exc}')
        return render(request, f'{_T}form.html', {
            'form_title': 'Add School Calendar',
            'action':     'add',
            'post':       request.POST,
            'errors':     {},
            **lookups,
        })

    messages.success(
        request,
        f'Calendar "{cal.title}" has been '
        f'{"published" if cal.is_published else "saved as draft"} successfully.'
    )
    return redirect('school:calendar_detail', pk=cal.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  3. EDIT CALENDAR
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def calendar_edit(request, pk):
    """
    Edit an existing school calendar entry.
    GET  — form pre-filled with current values.
    POST — validate; save; handle document replace/clear.

    Document handling:
        - 'clear_document' checkbox removes existing file from disk.
        - Uploading a new file replaces the existing one.
        - Not touching the file field leaves it unchanged.
    """
    cal     = get_object_or_404(SchoolCalendar.objects.select_related('term'), pk=pk)
    lookups = _get_form_lookups()

    if request.method == 'GET':
        return render(request, f'{_T}form.html', {
            'calendar':   cal,
            'form_title': f'Edit — {cal.title}',
            'action':     'edit',
            'post':       {},
            'errors':     {},
            **lookups,
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    cleaned, errors = validate_and_parse_calendar(
        request.POST, request.FILES, instance=cal
    )

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}form.html', {
            'calendar':   cal,
            'form_title': f'Edit — {cal.title}',
            'action':     'edit',
            'post':       request.POST,
            'errors':     errors,
            **lookups,
        })

    try:
        with transaction.atomic():
            was_draft = not cal.is_published
            _apply_to_instance(cal, cleaned)

            # Auto-stamp published_at on first publish
            if cal.is_published and was_draft and not cal.published_at:
                cal.published_at = timezone.now()

            # Document handling
            if cleaned.get('clear_document'):
                if cal.document:
                    cal.document.delete(save=False)
                cal.document = None
            elif request.FILES.get('document'):
                if cal.document:
                    cal.document.delete(save=False)
                cal.document = request.FILES['document']

            cal.save()

    except Exception as exc:
        messages.error(request, f'Could not update calendar: {exc}')
        return render(request, f'{_T}form.html', {
            'calendar':   cal,
            'form_title': f'Edit — {cal.title}',
            'action':     'edit',
            'post':       request.POST,
            'errors':     {},
            **lookups,
        })

    messages.success(request, f'Calendar "{cal.title}" has been updated successfully.')
    return redirect('school:calendar_detail', pk=cal.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  4. DELETE CALENDAR
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def calendar_delete(request, pk):
    """
    Delete a school calendar entry.
    GET  — confirmation page showing calendar summary.
    POST — delete record and document from disk, redirect to list.
    """
    cal = get_object_or_404(SchoolCalendar.objects.select_related('term'), pk=pk)

    if request.method == 'GET':
        return render(request, f'{_T}delete_confirm.html', {
            'calendar': cal,
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    title = cal.title
    try:
        if cal.document:
            cal.document.delete(save=False)
        cal.delete()
        messages.success(request, f'Calendar "{title}" has been permanently deleted.')
    except Exception as exc:
        messages.error(request, f'Could not delete calendar: {exc}')
        return redirect('school:calendar_detail', pk=pk)

    return redirect('school:calendar_list')


# ═══════════════════════════════════════════════════════════════════════════════
#  5. CALENDAR DETAIL
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def calendar_detail(request, pk):
    """
    Full single calendar detail page.

    Displays:
        - Title, academic year, linked term, description
        - Published / Draft + Active / Inactive status badges
        - Document download link (if uploaded)
        - Full term milestone timeline derived from the linked Term's
          date fields (BOT / MOT / EOT windows, closing, holiday studies,
          next term opening)
        - All published SchoolEvents falling within this term's date range
        - Sibling calendars (same academic year, different terms)
        - Prev / Next calendar navigation
        - Holiday study classes (if term has holiday studies enabled)
        - Created by and timestamps
    """
    cal = get_object_or_404(
        SchoolCalendar.objects.select_related('term', 'term__class_teacher', 'created_by'),
        pk=pk
    )
    stats = get_calendar_detail_stats(cal)

    context = {
        'calendar':   cal,
        'term':       cal.term,
        'page_title': cal.title,
        **stats,
    }
    return render(request, f'{_T}detail.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  6. TOGGLE PUBLISHED  (POST-only)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def calendar_toggle_published(request, pk):
    """
    POST-only: flip is_published on a calendar entry.
    Auto-stamps published_at when first publishing.
    Clears published_at when reverting to draft so it resets on next publish.
    """
    if request.method != 'POST':
        messages.warning(request, 'Invalid request method.')
        return redirect('school:calendar_list')

    cal = get_object_or_404(SchoolCalendar, pk=pk)
    cal.is_published = not cal.is_published

    update_fields = ['is_published', 'published_at']

    if cal.is_published and not cal.published_at:
        cal.published_at = timezone.now()
    elif not cal.is_published:
        cal.published_at = None

    cal.save(update_fields=update_fields)

    state = 'published' if cal.is_published else 'reverted to draft'
    messages.success(request, f'Calendar "{cal.title}" has been {state}.')

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('school:calendar_detail', pk=cal.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  7. TOGGLE ACTIVE  (POST-only)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def calendar_toggle_active(request, pk):
    """
    POST-only: flip is_active on a calendar entry.
    Inactive calendars are hidden from public-facing views but kept on record.
    """
    if request.method != 'POST':
        messages.warning(request, 'Invalid request method.')
        return redirect('school:calendar_list')

    cal = get_object_or_404(SchoolCalendar, pk=pk)
    cal.is_active = not cal.is_active
    cal.save(update_fields=['is_active'])

    state = 'activated' if cal.is_active else 'deactivated'
    messages.success(request, f'Calendar "{cal.title}" has been {state}.')

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('school:calendar_detail', pk=cal.pk)
