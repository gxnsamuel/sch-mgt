# students/views/admission_views.py
# ─────────────────────────────────────────────────────────────────────────────
# All Admission views.
#
# Views:
#   admission_list          — list with full stats and filters
#   admission_add           — submit a new application
#   admission_edit          — edit application details
#   admission_delete        — confirm + perform deletion
#   admission_detail        — full single application page
#   admission_update_status — POST: move to a new status with required fields
#   admission_enrol         — GET/POST: convert Approved → Student record
#
# Rules:
#   - Function-based views only
#   - No Django Forms / forms.py
#   - No Class-based Views
#   - No JSON responses
#   - Manual validation via admission_utils
#   - django.contrib.messages for all feedback
#   - login_required on every view
#   - transaction.atomic() on all saves
# ─────────────────────────────────────────────────────────────────────────────

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from academics.models import SchoolClass
from students.models import Admission, Student
from students.utils.admission_utils import (
    STATUS_LABELS,
    STATUS_TRANSITIONS,
    generate_admission_number,
    get_admission_detail_stats,
    get_admission_list_stats,
    suggest_student_id,
    validate_and_parse_admission,
    validate_enrolment,
    validate_status_update,
)

_T = 'students/admissions/'

_STATUS_CHOICES      = list(STATUS_LABELS.items())
_CLASS_LEVEL_CHOICES = [
    ('baby', 'Baby Class'), ('middle', 'Middle Class'), ('top', 'Top Class'),
    ('p1', 'P1'), ('p2', 'P2'), ('p3', 'P3'), ('p4', 'P4'),
    ('p5', 'P5'), ('p6', 'P6'), ('p7', 'P7'),
]
_GENDER_CHOICES = [('male', 'Male'), ('female', 'Female')]


# ── Private helpers ────────────────────────────────────────────────────────────

def _get_form_lookups() -> dict:
    """Common querysets every admission form needs."""
    return {
        'all_classes':    SchoolClass.objects.filter(
                              is_active=True
                          ).order_by('section', 'level', 'stream'),
        'gender_choices': _GENDER_CHOICES,
    }


def _apply_to_instance(instance: Admission, cleaned: dict) -> None:
    """Write cleaned scalar and FK fields onto an Admission instance."""
    scalar_fields = (
        'academic_year', 'first_name', 'last_name', 'other_names',
        'date_of_birth', 'gender', 'nationality', 'district_of_origin',
        'religion', 'birth_certificate_no',
        'previous_school', 'previous_class', 'last_result',
        'parent_full_name', 'parent_relationship', 'parent_phone',
        'parent_email', 'parent_occupation', 'parent_address',
        'notes', 'interview_notes', 'rejection_reason',
        'interview_date', 'admission_date',
    )
    for f in scalar_fields:
        if f in cleaned:
            setattr(instance, f, cleaned[f])

    if 'applied_class_id' in cleaned:
        instance.applied_class_id = cleaned['applied_class_id']


# ═══════════════════════════════════════════════════════════════════════════════
#  1. ADMISSIONS LIST
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def admission_list(request):
    """
    All admission applications with statistics and filters.

    Stats cards:
        total, by-status counts, approval rate, enrolment rate,
        by-gender, by-year, by-class, upcoming interviews strip,
        recent 10 applications.

    Filters (GET — all stackable):
        ?q=         name / admission number search
        ?status=    pending|shortlisted|approved|rejected|waitlisted|enrolled
        ?year=      academic_year value
        ?class=     applied_class level (e.g. p1)
        ?section=   nursery | primary
        ?gender=    male | female
        ?interview= upcoming  (interview_date >= today)
    """
    from datetime import date
    today = date.today()

    qs = Admission.objects.select_related('applied_class', 'reviewed_by', 'student')

    # ── Filters ───────────────────────────────────────────────────────────────
    search           = request.GET.get('q', '').strip()
    status_filter    = request.GET.get('status', '').strip()
    year_filter      = request.GET.get('year', '').strip()
    class_filter     = request.GET.get('class', '').strip()
    section_filter   = request.GET.get('section', '').strip()
    gender_filter    = request.GET.get('gender', '').strip()
    interview_filter = request.GET.get('interview', '').strip()

    if search:
        qs = qs.filter(
            Q(admission_number__icontains=search)  |
            Q(first_name__icontains=search)        |
            Q(last_name__icontains=search)         |
            Q(other_names__icontains=search)       |
            Q(parent_full_name__icontains=search)  |
            Q(parent_phone__icontains=search)
        )

    if status_filter:
        qs = qs.filter(status=status_filter)

    if year_filter:
        qs = qs.filter(academic_year=year_filter)

    if class_filter:
        qs = qs.filter(applied_class__level=class_filter)

    if section_filter:
        qs = qs.filter(applied_class__section=section_filter)

    if gender_filter:
        qs = qs.filter(gender=gender_filter)

    if interview_filter == 'upcoming':
        qs = qs.filter(interview_date__gte=today)

    qs = qs.order_by('-application_date')

    # ── Pagination ────────────────────────────────────────────────────────────
    paginator = Paginator(qs, 20)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    # Annotate each item with status label and allowed transitions
    items = list(page_obj.object_list)
    for item in items:
        item._status_label          = STATUS_LABELS.get(item.status, item.status)
        item._allowed_transitions   = [
            (s, STATUS_LABELS[s])
            for s in STATUS_TRANSITIONS.get(item.status, set())
        ]
        item._days_since_application = (today - item.application_date).days
        if item.interview_date:
            item._days_until_interview = (item.interview_date - today).days
        else:
            item._days_until_interview = None

    stats = get_admission_list_stats()

    context = {
        'admissions':        items,
        'page_obj':          page_obj,
        # active filters
        'search':            search,
        'status_filter':     status_filter,
        'year_filter':       year_filter,
        'class_filter':      class_filter,
        'section_filter':    section_filter,
        'gender_filter':     gender_filter,
        'interview_filter':  interview_filter,
        # choices
        'status_choices':    _STATUS_CHOICES,
        'gender_choices':    _GENDER_CHOICES,
        'class_level_choices': _CLASS_LEVEL_CHOICES,
        'today':             today,
        **stats,
    }
    return render(request, f'{_T}list.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  2. ADD ADMISSION
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def admission_add(request):
    """
    Submit a new admission application.
    GET  — blank form; academic_year pre-filled with next year.
    POST — validate; auto-generate admission_number; save; redirect to detail.
    """
    lookups = _get_form_lookups()

    if request.method == 'GET':
        from datetime import date
        next_year = str(date.today().year + 1)
        return render(request, f'{_T}form.html', {
            'form_title':  'New Admission Application',
            'action':      'add',
            'post':        {},
            'errors':      {},
            'next_year':   next_year,
            **lookups,
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    cleaned, errors = validate_and_parse_admission(request.POST)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}form.html', {
            'form_title': 'New Admission Application',
            'action':     'add',
            'post':       request.POST,
            'errors':     errors,
            **lookups,
        })

    try:
        with transaction.atomic():
            adm = Admission()
            _apply_to_instance(adm, cleaned)
            adm.admission_number = generate_admission_number()
            adm.status           = 'pending'
            adm.save()
    except Exception as exc:
        messages.error(request, f'Could not save application: {exc}')
        return render(request, f'{_T}form.html', {
            'form_title': 'New Admission Application',
            'action':     'add',
            'post':       request.POST,
            'errors':     {},
            **lookups,
        })

    messages.success(
        request,
        f'Application submitted. Admission number: {adm.admission_number} — '
        f'{adm.first_name} {adm.last_name}.'
    )
    return redirect('students:admission_detail', pk=adm.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  3. EDIT ADMISSION
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def admission_edit(request, pk):
    """
    Edit application details (personal info, parent info, class applied to).
    Status changes must go through admission_update_status.
    Enrolled applications cannot be edited (guard below).
    """
    adm     = get_object_or_404(
        Admission.objects.select_related('applied_class', 'reviewed_by'), pk=pk
    )
    lookups = _get_form_lookups()

    # Guard: do not allow editing an enrolled application
    if adm.status == 'enrolled':
        messages.warning(
            request,
            f'Application {adm.admission_number} has been enrolled as a student '
            f'and can no longer be edited.'
        )
        return redirect('students:admission_detail', pk=adm.pk)

    if request.method == 'GET':
        return render(request, f'{_T}form.html', {
            'admission':  adm,
            'form_title': f'Edit Application — {adm.admission_number}',
            'action':     'edit',
            'post':       {},
            'errors':     {},
            **lookups,
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    cleaned, errors = validate_and_parse_admission(request.POST, instance=adm)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}form.html', {
            'admission':  adm,
            'form_title': f'Edit Application — {adm.admission_number}',
            'action':     'edit',
            'post':       request.POST,
            'errors':     errors,
            **lookups,
        })

    try:
        with transaction.atomic():
            _apply_to_instance(adm, cleaned)
            adm.save()
    except Exception as exc:
        messages.error(request, f'Could not update application: {exc}')
        return render(request, f'{_T}form.html', {
            'admission':  adm,
            'form_title': f'Edit Application — {adm.admission_number}',
            'action':     'edit',
            'post':       request.POST,
            'errors':     {},
            **lookups,
        })

    messages.success(
        request,
        f'Application {adm.admission_number} has been updated successfully.'
    )
    return redirect('students:admission_detail', pk=adm.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  4. DELETE ADMISSION
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def admission_delete(request, pk):
    """
    Delete an admission application.
    GET  — confirmation page showing application summary.
    POST — perform deletion.

    Guard: enrolled applications (linked to a Student) cannot be deleted.
    """
    adm = get_object_or_404(
        Admission.objects.select_related('applied_class', 'student'), pk=pk
    )

    if request.method == 'GET':
        return render(request, f'{_T}delete_confirm.html', {
            'admission':    adm,
            'status_label': STATUS_LABELS.get(adm.status, adm.status),
            'is_enrolled':  adm.status == 'enrolled',
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    if adm.status == 'enrolled':
        messages.error(
            request,
            f'Application {adm.admission_number} is linked to an enrolled student '
            f'and cannot be deleted.'
        )
        return redirect('students:admission_detail', pk=adm.pk)

    label = f'{adm.admission_number} — {adm.first_name} {adm.last_name}'
    try:
        adm.delete()
        messages.success(request, f'Application "{label}" has been permanently deleted.')
    except Exception as exc:
        messages.error(request, f'Could not delete application: {exc}')
        return redirect('students:admission_detail', pk=pk)

    return redirect('students:admission_list')


# ═══════════════════════════════════════════════════════════════════════════════
#  5. ADMISSION DETAIL
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def admission_detail(request, pk):
    """
    Full single admission application page.

    Displays:
        - Admission number, status badge, application date
        - Applicant details (personal, previous schooling)
        - Parent / guardian details
        - Applied class + academic year
        - Interview date / notes
        - Admission date (if approved)
        - Rejection reason (if rejected)
        - Linked student record link (if enrolled)
        - Days since application, days until interview
        - Allowed next-status transitions (action buttons)
        - Sibling applications (same class + year)
    """
    adm = get_object_or_404(
        Admission.objects.select_related(
            'applied_class', 'reviewed_by', 'student', 'student__current_class'
        ),
        pk=pk
    )
    stats = get_admission_detail_stats(adm)

    context = {
        'admission':   adm,
        'page_title':  f'{adm.admission_number} — {adm.first_name} {adm.last_name}',
        **stats,
    }
    return render(request, f'{_T}detail.html', context)


# ═══════════════════════════════════════════════════════════════════════════════
#  6. UPDATE STATUS
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def admission_update_status(request, pk):
    """
    POST-only: move an application to a new status.

    Validates the transition is allowed (see STATUS_TRANSITIONS).
    Collects additional fields required by the target status:
        → shortlisted : interview_date (recommended)
        → approved    : admission_date (required)
        → rejected    : rejection_reason (required)

    Stamps reviewed_by = request.user on every status change.

    Renders a dedicated status-update form on GET so the user
    can supply the required fields before confirming.
    """
    adm = get_object_or_404(
        Admission.objects.select_related('applied_class'), pk=pk
    )

    # Determine target status from GET param (when opening the form)
    # or from POST param (when submitting)
    target_status = (
        request.POST.get('status') or
        request.GET.get('to') or
        ''
    ).strip()

    # Allowed transitions for context
    allowed = [
        (s, STATUS_LABELS[s])
        for s in STATUS_TRANSITIONS.get(adm.status, set())
    ]

    if request.method == 'GET':
        if target_status and target_status not in STATUS_TRANSITIONS.get(adm.status, set()):
            messages.error(
                request,
                f'Cannot move from "{STATUS_LABELS[adm.status]}" '
                f'to "{STATUS_LABELS.get(target_status, target_status)}".'
            )
            return redirect('students:admission_detail', pk=adm.pk)

        return render(request, f'{_T}update_status.html', {
            'admission':      adm,
            'target_status':  target_status,
            'status_label':   STATUS_LABELS.get(adm.status, adm.status),
            'target_label':   STATUS_LABELS.get(target_status, target_status),
            'allowed':        allowed,
            'post':           {},
            'errors':         {},
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    cleaned, errors = validate_status_update(request.POST, adm.status)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}update_status.html', {
            'admission':     adm,
            'target_status': target_status,
            'status_label':  STATUS_LABELS.get(adm.status, adm.status),
            'target_label':  STATUS_LABELS.get(target_status, target_status),
            'allowed':       allowed,
            'post':          request.POST,
            'errors':        errors,
        })

    try:
        with transaction.atomic():
            for field, value in cleaned.items():
                setattr(adm, field, value)
            adm.reviewed_by = request.user
            adm.save()
    except Exception as exc:
        messages.error(request, f'Could not update status: {exc}')
        return redirect('students:admission_detail', pk=adm.pk)

    new_label = STATUS_LABELS.get(cleaned['status'], cleaned['status'])
    messages.success(
        request,
        f'Application {adm.admission_number} has been moved to '
        f'"{new_label}" successfully.'
    )

    # If approved — nudge toward enrolment
    if cleaned['status'] == 'approved':
        messages.info(
            request,
            f'Application is now approved. '
            f'Use "Enrol Student" to create the student record.'
        )

    return redirect('students:admission_detail', pk=adm.pk)


# ═══════════════════════════════════════════════════════════════════════════════
#  7. ENROL STUDENT  (Admission → Student record)
# ═══════════════════════════════════════════════════════════════════════════════

@login_required
def admission_enrol(request, pk):
    """
    Convert an Approved admission into a full Student record.

    GET  — pre-filled enrolment form.
           student_id auto-suggested (STD<YEAR><SEQ>).
           current_class defaults to applied_class.
           academic_year and date_enrolled default to today's year / today.

    POST — validate; create Student; link Admission.student = new student;
           set Admission.status = 'enrolled'; redirect to student detail.

    Guards:
        - Only 'approved' applications can be enrolled.
        - If admission.student is already set, redirect to that student.
    """
    adm = get_object_or_404(
        Admission.objects.select_related('applied_class', 'student'), pk=pk
    )

    # Guard: must be approved
    if adm.status != 'approved':
        messages.error(
            request,
            f'Only approved applications can be enrolled. '
            f'This application is currently "{STATUS_LABELS.get(adm.status, adm.status)}".'
        )
        return redirect('students:admission_detail', pk=adm.pk)

    # Guard: already enrolled
    if adm.student_id:
        messages.info(
            request,
            f'This application is already linked to student {adm.student}.'
        )
        return redirect('students:student_detail', pk=adm.student_id)

    all_classes = SchoolClass.objects.filter(
        is_active=True
    ).order_by('section', 'level', 'stream')

    if request.method == 'GET':
        suggested_id = suggest_student_id()
        from datetime import date
        return render(request, f'{_T}enrol.html', {
            'admission':     adm,
            'page_title':    f'Enrol — {adm.first_name} {adm.last_name}',
            'suggested_id':  suggested_id,
            'today_str':     date.today().strftime('%Y-%m-%d'),
            'current_year':  str(date.today().year),
            'all_classes':   all_classes,
            'post':          {},
            'errors':        {},
        })

    # ── POST ──────────────────────────────────────────────────────────────────
    cleaned, errors = validate_enrolment(request.POST)

    if errors:
        for msg in errors.values():
            messages.error(request, msg)
        return render(request, f'{_T}enrol.html', {
            'admission':    adm,
            'page_title':   f'Enrol — {adm.first_name} {adm.last_name}',
            'all_classes':  all_classes,
            'post':         request.POST,
            'errors':       errors,
        })

    try:
        with transaction.atomic():
            # Create the Student record from admission data
            student = Student.objects.create(
                student_id         = cleaned['student_id'],
                first_name         = adm.first_name,
                last_name          = adm.last_name,
                other_names        = adm.other_names,
                date_of_birth      = adm.date_of_birth,
                gender             = adm.gender,
                nationality        = adm.nationality,
                district_of_origin = adm.district_of_origin,
                religion           = adm.religion,
                birth_certificate_no = adm.birth_certificate_no,
                current_class_id   = cleaned['current_class_id'],
                academic_year      = cleaned['academic_year'],
                date_enrolled      = cleaned['date_enrolled'],
                previous_school    = adm.previous_school,
                previous_class     = adm.previous_class,
                is_active          = True,
            )

            # Link and close the admission
            adm.student  = student
            adm.status   = 'enrolled'
            adm.reviewed_by = request.user
            adm.save(update_fields=['student', 'status', 'reviewed_by'])

    except Exception as exc:
        messages.error(request, f'Could not enrol student: {exc}')
        return render(request, f'{_T}enrol.html', {
            'admission':   adm,
            'page_title':  f'Enrol — {adm.first_name} {adm.last_name}',
            'all_classes': all_classes,
            'post':        request.POST,
            'errors':      {},
        })

    messages.success(
        request,
        f'{student.first_name} {student.last_name} has been enrolled successfully. '
        f'Student ID: {student.student_id}.'
    )
    return redirect('students:student_detail', pk=student.pk)
