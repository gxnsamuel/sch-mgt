# accounts/views/accounts_views.py
# ─────────────────────────────────────────────────────────────────────────────
# Views:
#   user_list               — all users with stats and filters
#   register_parent         — create parent user + ParentProfile
#   register_staff          — create teacher/staff/admin user + StaffProfile
#   user_detail             — full profile page (dispatches by user_type)
#   user_edit               — edit user + profile fields
#   user_toggle_active      — POST: activate / deactivate account
# ─────────────────────────────────────────────────────────────────────────────

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from academics.models import SchoolClass
from accounts.models import ParentProfile, StaffProfile, USER_TYPE_CHOICES
from accounts.utils import (
    generate_employee_id,
    generate_parent_id,
    get_user_list_stats,
    validate_and_parse_parent_registration,
    validate_and_parse_staff_registration,
    VALID_STAFF_ROLES,
    VALID_EMPLOYMENT_TYPES,
    VALID_QUALIFICATIONS,
)

User = get_user_model()
_T   = 'accounts/'


# ── Helpers ────────────────────────────────────────────────────────────────────

def _staff_form_lookups() -> dict:
    return {
        'all_classes':       SchoolClass.objects.filter(
                                 is_active=True
                             ).order_by('section', 'level', 'stream'),
        'role_choices':      StaffProfile.ROLE_CHOICES,
        'employment_choices':StaffProfile.EMPLOYMENT_TYPE_CHOICES,
        'qualification_choices': StaffProfile.QUALIFICATION_CHOICES,
        'user_type_choices': [
            ('teacher', 'Teacher'),
            ('staff',   'Support Staff'),
            ('admin',   'Administrator'),
        ],
    }


def _parent_form_lookups() -> dict:
    return {
        'relationship_choices': ParentProfile.RELATIONSHIP_CHOICES,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  1. USER LIST
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def user_list(request):
    """
    All system users with stats and filters.

    Stats: total, by-type counts, active/inactive.

    Filters:
        ?q=          name / username / parent_id search
        ?type=       parent | teacher | staff | admin
        ?active=1|0  active or inactive accounts
    """
    qs = User.objects.prefetch_related('parent_profile', 'staff_profile')

    search      = request.GET.get('q', '').strip()
    type_filter = request.GET.get('type', '').strip()
    active_filter = request.GET.get('active', '').strip()

    if search:
        qs = qs.filter(
            Q(first_name__icontains=search)   |
            Q(last_name__icontains=search)    |
            Q(username__icontains=search)     |
            Q(parent_id__icontains=search)    |
            Q(email__icontains=search)        |
            Q(phone__icontains=search)
        )

    if type_filter:
        qs = qs.filter(user_type=type_filter)

    if active_filter == '1':
        qs = qs.filter(is_active=True)
    elif active_filter == '0':
        qs = qs.filter(is_active=False)

    qs = qs.order_by('user_type', 'last_name', 'first_name')

    paginator = Paginator(qs, 25)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    stats = get_user_list_stats()

    context = {
        'users':         page_obj.object_list,
        'page_obj':      page_obj,
        'search':        search,
        'type_filter':   type_filter,
        'active_filter': active_filter,
        'type_choices':  USER_TYPE_CHOICES,
        **stats,
    }
    return render(request, f'{_T}user_list.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  2. REGISTER PARENT
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def register_parent(request):
    """
    Register a new parent / guardian account.

    GET  — blank form showing all parent fields.
           parent_id is auto-generated and displayed as read-only preview.
    POST — validate; create CustomUser (user_type=parent, username=parent_id);
           create ParentProfile; redirect to user_detail.

    The parent receives their parent_id on paper / SMS — it is their
    login credential at the login screen.
    """
    lookups = _parent_form_lookups()

    if request.method == 'GET':
        # Pre-generate a preview ID (not reserved until save)
        try:
            preview_id = generate_parent_id()
        except Exception:
            preview_id = 'PAR' + str(__import__('datetime').date.today().year) + 'XXXX'

        return render(request, f'{_T}register_parent.html', {
            'form_title':  'Register Parent / Guardian',
            'preview_id':  preview_id,
            'post':        {},
            'errors':      {},
            **lookups,
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    user_c, prof_c, errors = validate_and_parse_parent_registration(request.POST)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}register_parent.html', {
            'form_title': 'Register Parent / Guardian',
            'post':       request.POST,
            'errors':     errors,
            **lookups,
        })

    try:
        with transaction.atomic():
            # Generate unique parent_id inside the transaction
            parent_id = generate_parent_id()

            user = User.objects.create_parent_user(
                parent_id  = parent_id,
                password   = user_c.pop('password'),
                first_name = user_c.get('first_name', ''),
                last_name  = user_c.get('last_name', ''),
                other_names= user_c.get('other_names', ''),
                gender     = user_c.get('gender', ''),
                email      = user_c.get('email', ''),
                phone      = user_c.get('phone', ''),
                alt_phone  = user_c.get('alt_phone', ''),
                address    = user_c.get('address', ''),
                nin        = user_c.get('nin', ''),
            )

            # ParentProfile
            ParentProfile.objects.create(user=user, **prof_c)

    except Exception as exc:
        messages.error(request, f'Could not create parent account: {exc}')
        return render(request, f'{_T}register_parent.html', {
            'form_title': 'Register Parent / Guardian',
            'post':       request.POST,
            'errors':     {},
            **lookups,
        })

    messages.success(
        request,
        f'Parent account created. '
        f'Parent ID: {user.parent_id} — {user.full_name}. '
        f'Please provide the parent with their ID and password.'
    )
    return redirect('accounts:user_detail', pk=user.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  3. REGISTER STAFF / TEACHER / ADMIN
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def register_staff(request):
    """
    Register a new teacher, support staff, or admin account.

    GET  — blank form. user_type selector drives which fields show.
    POST — validate; create CustomUser + StaffProfile; redirect to user_detail.

    Staff log in with username + password.
    Employee ID is auto-generated (EMP<YEAR><SEQ>).
    """
    lookups = _staff_form_lookups()

    if request.method == 'GET':
        return render(request, f'{_T}register_staff.html', {
            'form_title': 'Register Staff / Teacher',
            'post':       {},
            'errors':     {},
            **lookups,
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    user_c, prof_c, errors = validate_and_parse_staff_registration(request.POST)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}register_staff.html', {
            'form_title': 'Register Staff / Teacher',
            'post':       request.POST,
            'errors':     errors,
            **lookups,
        })

    try:
        with transaction.atomic():
            employee_id = generate_employee_id()

            user = User.objects.create_user(
                username    = user_c['username'],
                email       = user_c.get('email', ''),
                password    = user_c.pop('password'),
                user_type   = user_c['user_type'],
                first_name  = user_c.get('first_name', ''),
                last_name   = user_c.get('last_name', ''),
                other_names = user_c.get('other_names', ''),
                gender      = user_c.get('gender', ''),
                phone       = user_c.get('phone', ''),
                alt_phone   = user_c.get('alt_phone', ''),
                address     = user_c.get('address', ''),
                nin         = user_c.get('nin', ''),
                # Staff are granted is_staff so they can access the admin
                is_staff    = user_c['user_type'] in ('admin',),
            )

            # Handle photo upload
            if request.FILES.get('profile_photo'):
                user.profile_photo = request.FILES['profile_photo']
                user.save(update_fields=['profile_photo'])

            # StaffProfile
            class_managed_id = prof_c.pop('class_managed_id', None)
            sp = StaffProfile.objects.create(
                user        = user,
                employee_id = employee_id,
                **prof_c,
            )
            if class_managed_id:
                sp.class_managed_id = class_managed_id
                sp.save(update_fields=['class_managed_id'])

            # Handle signature upload
            if request.FILES.get('signature'):
                sp.signature = request.FILES['signature']
                sp.save(update_fields=['signature'])

    except Exception as exc:
        messages.error(request, f'Could not create staff account: {exc}')
        return render(request, f'{_T}register_staff.html', {
            'form_title': 'Register Staff / Teacher',
            'post':       request.POST,
            'errors':     {},
            **lookups,
        })

    type_label = dict(USER_TYPE_CHOICES).get(user.user_type, user.user_type)
    messages.success(
        request,
        f'{type_label} account created — {user.full_name} '
        f'(Username: {user.username}, Employee ID: {sp.employee_id}).'
    )
    return redirect('accounts:user_detail', pk=user.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  4. USER DETAIL
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def user_detail(request, pk):
    """
    Full profile page for any user type.
    Shows user fields + the linked ParentProfile or StaffProfile.
    """
    user = get_object_or_404(
        User.objects.prefetch_related(
            'parent_profile', 'staff_profile', 'staff_profile__class_managed'
        ),
        pk=pk
    )

    profile = None
    if user.user_type == 'parent':
        profile = getattr(user, 'parent_profile', None)
    else:
        profile = getattr(user, 'staff_profile', None)

    # Children if parent
    children = []
    if user.user_type == 'parent' and profile:
        from students.models import Student
        children = list(
            Student.objects.filter(parent=profile, is_active=True)
            .select_related('current_class')
            .order_by('last_name', 'first_name')
        )

    context = {
        'user_obj':    user,
        'profile':     profile,
        'children':    children,
        'type_label':  dict(USER_TYPE_CHOICES).get(user.user_type, user.user_type),
        'page_title':  user.full_name,
    }
    return render(request, f'{_T}user_detail.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  5. TOGGLE ACTIVE  (POST-only)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def user_toggle_active(request, pk):
    """POST-only: activate or deactivate a user account."""
    if request.method != 'POST':
        messages.warning(request, 'Invalid request method.')
        return redirect('accounts:user_list')

    user = get_object_or_404(User, pk=pk)

    # Prevent deactivating your own account
    if user.pk == request.user.pk:
        messages.error(request, 'You cannot deactivate your own account.')
        return redirect('accounts:user_detail', pk=user.pk)

    user.is_active = not user.is_active
    user.save(update_fields=['is_active'])

    state = 'activated' if user.is_active else 'deactivated'
    messages.success(request, f'Account for "{user.full_name}" has been {state}.')

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('accounts:user_detail', pk=user.pk)
