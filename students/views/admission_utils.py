# students/utils/admission_utils.py
# ─────────────────────────────────────────────────────────────────────────────
# Helpers for Admission views:
#   - Auto admission number generation
#   - Manual field validation (full form + status-update form)
#   - Enrolment helper (Admission → Student conversion)
#   - List-level and detail statistics
# ─────────────────────────────────────────────────────────────────────────────

from datetime import date, datetime

from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db.models import Count, Max, Q

from students.models import Admission


# ═══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

VALID_STATUSES = {
    'pending', 'shortlisted', 'approved', 'rejected', 'waitlisted', 'enrolled',
}

STATUS_LABELS = {
    'pending':     'Pending Review',
    'shortlisted': 'Shortlisted',
    'approved':    'Approved',
    'rejected':    'Rejected',
    'waitlisted':  'Waitlisted',
    'enrolled':    'Enrolled',
}

# Valid forward transitions from each status
STATUS_TRANSITIONS = {
    'pending':     {'shortlisted', 'approved', 'rejected', 'waitlisted'},
    'shortlisted': {'approved', 'rejected', 'waitlisted'},
    'waitlisted':  {'approved', 'rejected'},
    'approved':    {'enrolled', 'rejected'},
    'rejected':    {'pending'},   # allow re-opening
    'enrolled':    set(),          # terminal — cannot move back
}

VALID_GENDERS = {'male', 'female'}


# ═══════════════════════════════════════════════════════════════════════════════
#  ADMISSION NUMBER GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def generate_admission_number() -> str:
    """
    Auto-generate a unique admission number: ADM<YEAR><SEQ>.
    Example: ADM20250001, ADM20250002 …
    Sequence resets each calendar year.
    Call inside transaction.atomic() in the view.
    """
    year   = date.today().year
    prefix = f'ADM{year}'

    last = (
        Admission.objects
        .filter(admission_number__startswith=prefix)
        .aggregate(m=Max('admission_number'))['m']
    )

    if last:
        try:
            seq = int(last.replace(prefix, '')) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1

    return f'{prefix}{seq:04d}'


# ═══════════════════════════════════════════════════════════════════════════════
#  DATE PARSING
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_date(value: str, field_label: str, errors: dict) -> date | None:
    value = (value or '').strip()
    if not value:
        return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    errors[field_label] = f'{field_label} is not a valid date (use YYYY-MM-DD).'
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  FULL FORM VALIDATION  (add + edit)
# ═══════════════════════════════════════════════════════════════════════════════

def validate_and_parse_admission(
    post: dict,
    instance: Admission | None = None,
) -> tuple[dict, dict]:
    """
    Validate all Admission POST fields.

    Returns:
        (cleaned_data, errors)

    cleaned_data — ready for setattr loop on the instance.
                   applied_class_id stored as int; view resolves FK.
    errors       — dict of field_name → error message. Empty = passed.
    """
    errors:  dict = {}
    cleaned: dict = {}

    # ── academic_year ─────────────────────────────────────────────────────────
    academic_year = (post.get('academic_year') or '').strip()
    if not academic_year:
        errors['academic_year'] = 'Academic year is required (e.g. 2025).'
    else:
        try:
            yr = int(academic_year)
            now = date.today().year
            if yr < 2000 or yr > now + 5:
                errors['academic_year'] = (
                    f'Academic year must be between 2000 and {now + 5}.'
                )
            else:
                cleaned['academic_year'] = str(yr)
        except ValueError:
            errors['academic_year'] = 'Academic year must be a 4-digit year (e.g. 2025).'

    # ── applied_class (optional FK) ───────────────────────────────────────────
    class_id = (post.get('applied_class') or '').strip()
    if class_id:
        try:
            cleaned['applied_class_id'] = int(class_id)
        except ValueError:
            errors['applied_class'] = 'Invalid class selected.'
    else:
        cleaned['applied_class_id'] = None

    # ── APPLICANT DETAILS ─────────────────────────────────────────────────────

    first_name = (post.get('first_name') or '').strip()
    if not first_name:
        errors['first_name'] = 'First name is required.'
    elif len(first_name) > 50:
        errors['first_name'] = 'First name must not exceed 50 characters.'
    else:
        cleaned['first_name'] = first_name

    last_name = (post.get('last_name') or '').strip()
    if not last_name:
        errors['last_name'] = 'Last name is required.'
    elif len(last_name) > 50:
        errors['last_name'] = 'Last name must not exceed 50 characters.'
    else:
        cleaned['last_name'] = last_name

    other_names = (post.get('other_names') or '').strip()
    if len(other_names) > 50:
        errors['other_names'] = 'Other names must not exceed 50 characters.'
    else:
        cleaned['other_names'] = other_names

    dob = _parse_date(post.get('date_of_birth'), 'Date of birth', errors)
    if not dob:
        errors.setdefault('date_of_birth', 'Date of birth is required.')
    else:
        today = date.today()
        age = (today - dob).days // 365
        if dob > today:
            errors['date_of_birth'] = 'Date of birth cannot be in the future.'
        elif age > 20:
            errors['date_of_birth'] = (
                f'Date of birth gives an age of {age} years — please verify.'
            )
        else:
            cleaned['date_of_birth'] = dob

    gender = (post.get('gender') or '').strip()
    if not gender:
        errors['gender'] = 'Gender is required.'
    elif gender not in VALID_GENDERS:
        errors['gender'] = 'Invalid gender selected.'
    else:
        cleaned['gender'] = gender

    cleaned['nationality']         = (post.get('nationality') or 'Ugandan').strip()
    cleaned['district_of_origin']  = (post.get('district_of_origin') or '').strip()
    cleaned['religion']            = (post.get('religion') or '').strip()

    bc = (post.get('birth_certificate_no') or '').strip()
    if len(bc) > 50:
        errors['birth_certificate_no'] = 'Birth certificate number must not exceed 50 characters.'
    else:
        cleaned['birth_certificate_no'] = bc

    # ── PREVIOUS SCHOOLING ────────────────────────────────────────────────────
    cleaned['previous_school'] = (post.get('previous_school') or '').strip()
    cleaned['previous_class']  = (post.get('previous_class') or '').strip()
    cleaned['last_result']     = (post.get('last_result') or '').strip()

    # ── PARENT / GUARDIAN ─────────────────────────────────────────────────────
    parent_name = (post.get('parent_full_name') or '').strip()
    if not parent_name:
        errors['parent_full_name'] = "Parent / guardian's full name is required."
    elif len(parent_name) > 100:
        errors['parent_full_name'] = 'Parent name must not exceed 100 characters.'
    else:
        cleaned['parent_full_name'] = parent_name

    parent_rel = (post.get('parent_relationship') or '').strip()
    if not parent_rel:
        errors['parent_relationship'] = 'Relationship to applicant is required.'
    else:
        cleaned['parent_relationship'] = parent_rel

    parent_phone = (post.get('parent_phone') or '').strip()
    if not parent_phone:
        errors['parent_phone'] = "Parent's phone number is required."
    elif len(parent_phone) > 15:
        errors['parent_phone'] = 'Phone number must not exceed 15 characters.'
    elif not parent_phone.replace('+', '').replace(' ', '').replace('-', '').isdigit():
        errors['parent_phone'] = 'Phone must contain only digits, spaces, hyphens, or a leading +.'
    else:
        cleaned['parent_phone'] = parent_phone

    parent_email = (post.get('parent_email') or '').strip()
    if parent_email:
        try:
            validate_email(parent_email)
            cleaned['parent_email'] = parent_email
        except ValidationError:
            errors['parent_email'] = 'Enter a valid email address.'
    else:
        cleaned['parent_email'] = ''

    cleaned['parent_occupation'] = (post.get('parent_occupation') or '').strip()

    parent_address = (post.get('parent_address') or '').strip()
    if not parent_address:
        errors['parent_address'] = "Parent's address is required."
    else:
        cleaned['parent_address'] = parent_address

    # ── APPLICATION STATUS FIELDS ─────────────────────────────────────────────
    cleaned['notes']           = (post.get('notes') or '').strip()
    cleaned['interview_notes'] = (post.get('interview_notes') or '').strip()
    cleaned['rejection_reason']= (post.get('rejection_reason') or '').strip()

    cleaned['interview_date'] = _parse_date(
        post.get('interview_date'), 'Interview date', errors
    )
    cleaned['admission_date'] = _parse_date(
        post.get('admission_date'), 'Admission date', errors
    )

    return cleaned, errors


# ═══════════════════════════════════════════════════════════════════════════════
#  STATUS UPDATE VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def validate_status_update(
    post: dict,
    current_status: str,
) -> tuple[dict, dict]:
    """
    Validate a status-change POST.

    Rules:
        - new_status must be a valid forward transition from current_status
        - rejection_reason required when moving to 'rejected'
        - admission_date required when moving to 'approved'
        - interview_date required when moving to 'shortlisted'
          (recommended, not blocked — only a warning stored in errors as 'warning_*')

    Returns (cleaned, errors) where errors is empty on success.
    """
    errors:  dict = {}
    cleaned: dict = {}

    new_status = (post.get('status') or '').strip()
    if not new_status:
        errors['status'] = 'New status is required.'
        return cleaned, errors

    if new_status not in VALID_STATUSES:
        errors['status'] = 'Invalid status selected.'
        return cleaned, errors

    allowed = STATUS_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        errors['status'] = (
            f'Cannot move from "{STATUS_LABELS[current_status]}" '
            f'to "{STATUS_LABELS[new_status]}". '
            f'Allowed transitions: {", ".join(STATUS_LABELS[s] for s in allowed) or "none"}.'
        )
        return cleaned, errors

    cleaned['status'] = new_status

    # Status-specific required fields
    if new_status == 'rejected':
        reason = (post.get('rejection_reason') or '').strip()
        if not reason:
            errors['rejection_reason'] = (
                'Rejection reason is required when rejecting an application.'
            )
        else:
            cleaned['rejection_reason'] = reason

    if new_status == 'approved':
        admission_date = _parse_date(
            post.get('admission_date'), 'Admission date', errors
        )
        if not admission_date:
            errors.setdefault('admission_date', 'Admission date is required when approving.')
        else:
            cleaned['admission_date'] = admission_date

    if new_status == 'shortlisted':
        interview_date = _parse_date(
            post.get('interview_date'), 'Interview date', errors
        )
        cleaned['interview_date'] = interview_date  # optional

    cleaned['notes'] = (post.get('notes') or '').strip()
    cleaned['interview_notes'] = (post.get('interview_notes') or '').strip()

    return cleaned, errors


# ═══════════════════════════════════════════════════════════════════════════════
#  ENROLMENT VALIDATION  (Admission → Student)
# ═══════════════════════════════════════════════════════════════════════════════

def validate_enrolment(post: dict) -> tuple[dict, dict]:
    """
    Validate the enrolment form that converts an approved Admission
    into a Student record.

    Collected fields:
        student_id   — unique student number (auto-suggested, overridable)
        current_class — SchoolClass pk (the class to enrol into)
        academic_year — enrolment year
        date_enrolled — date of enrolment
    """
    errors:  dict = {}
    cleaned: dict = {}

    student_id_val = (post.get('student_id') or '').strip()
    if not student_id_val:
        errors['student_id'] = 'Student ID is required.'
    elif len(student_id_val) > 20:
        errors['student_id'] = 'Student ID must not exceed 20 characters.'
    else:
        from students.models import Student
        qs = Student.objects.filter(student_id=student_id_val)
        if qs.exists():
            errors['student_id'] = f'Student ID "{student_id_val}" is already in use.'
        else:
            cleaned['student_id'] = student_id_val

    class_id = (post.get('current_class') or '').strip()
    if not class_id:
        errors['current_class'] = 'Class to enrol into is required.'
    else:
        try:
            cleaned['current_class_id'] = int(class_id)
        except ValueError:
            errors['current_class'] = 'Invalid class selected.'

    academic_year = (post.get('academic_year') or '').strip()
    if not academic_year:
        errors['academic_year'] = 'Academic year is required.'
    else:
        cleaned['academic_year'] = academic_year

    date_enrolled = _parse_date(post.get('date_enrolled'), 'Date enrolled', errors)
    if not date_enrolled:
        errors.setdefault('date_enrolled', 'Date of enrolment is required.')
    else:
        cleaned['date_enrolled'] = date_enrolled

    return cleaned, errors


# ═══════════════════════════════════════════════════════════════════════════════
#  AUTO STUDENT ID SUGGESTION
# ═══════════════════════════════════════════════════════════════════════════════

def suggest_student_id() -> str:
    """
    Suggest the next available student ID: STD<YEAR><SEQ>.
    Example: STD20250001
    """
    from students.models import Student

    year   = date.today().year
    prefix = f'STD{year}'

    last = (
        Student.objects
        .filter(student_id__startswith=prefix)
        .aggregate(m=Max('student_id'))['m']
    )

    if last:
        try:
            seq = int(last.replace(prefix, '')) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1

    return f'{prefix}{seq:04d}'


# ═══════════════════════════════════════════════════════════════════════════════
#  LIST STATS
# ═══════════════════════════════════════════════════════════════════════════════

def get_admission_list_stats() -> dict:
    """High-level statistics shown above the admissions list page."""
    today = date.today()
    qs    = Admission.objects.all()

    total       = qs.count()
    by_status   = {
        item['status']: item['count']
        for item in qs.values('status').annotate(count=Count('id'))
    }

    pending     = by_status.get('pending', 0)
    shortlisted = by_status.get('shortlisted', 0)
    approved    = by_status.get('approved', 0)
    rejected    = by_status.get('rejected', 0)
    waitlisted  = by_status.get('waitlisted', 0)
    enrolled    = by_status.get('enrolled', 0)

    approval_rate = (
        round((approved + enrolled) / total * 100, 1) if total else 0
    )
    enrolment_rate = (
        round(enrolled / (approved + enrolled) * 100, 1)
        if (approved + enrolled) else 0
    )

    # By gender
    by_gender = list(
        qs.values('gender').annotate(count=Count('id'))
    )

    # By academic year
    by_year = list(
        qs.values('academic_year')
        .annotate(count=Count('id'))
        .order_by('-academic_year')
    )

    # By applied class
    by_class = list(
        qs.exclude(applied_class__isnull=True)
        .values(
            'applied_class__level',
            'applied_class__stream',
            'applied_class__section',
        )
        .annotate(count=Count('id'))
        .order_by('applied_class__section', 'applied_class__level')
    )

    # Upcoming interviews (interview_date >= today, not yet decided)
    upcoming_interviews = list(
        qs.filter(
            interview_date__gte=today,
            status__in=('pending', 'shortlisted'),
        )
        .select_related('applied_class')
        .order_by('interview_date')[:5]
    )

    # Recent 10 applications
    recent = list(
        qs.select_related('applied_class', 'reviewed_by')
        .order_by('-application_date')[:10]
    )

    # Available academic years for filter dropdown
    years = list(
        qs.values_list('academic_year', flat=True)
        .distinct()
        .order_by('-academic_year')
    )

    return {
        'total':                total,
        'pending':              pending,
        'shortlisted':          shortlisted,
        'approved':             approved,
        'rejected':             rejected,
        'waitlisted':           waitlisted,
        'enrolled':             enrolled,
        'approval_rate':        approval_rate,
        'enrolment_rate':       enrolment_rate,
        'by_gender':            by_gender,
        'by_year':              by_year,
        'by_class':             by_class,
        'upcoming_interviews':  upcoming_interviews,
        'recent':               recent,
        'years':                years,
        'status_labels':        STATUS_LABELS,
        'today':                today,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  DETAIL STATS
# ═══════════════════════════════════════════════════════════════════════════════

def get_admission_detail_stats(admission: Admission) -> dict:
    """Stats and context for the single admission detail page."""
    today = date.today()

    # Days since application
    days_since_application = (today - admission.application_date).days

    # Days until interview (if set and in future)
    days_until_interview = None
    if admission.interview_date:
        days_until_interview = (admission.interview_date - today).days

    # Allowed next status transitions
    allowed_transitions = [
        (s, STATUS_LABELS[s])
        for s in STATUS_TRANSITIONS.get(admission.status, set())
    ]

    # Sibling applications: same academic year + same applied class
    siblings = list(
        Admission.objects.filter(
            academic_year=admission.academic_year,
            applied_class=admission.applied_class,
        )
        .exclude(pk=admission.pk)
        .order_by('-application_date')[:5]
    )

    return {
        'days_since_application': days_since_application,
        'days_until_interview':   days_until_interview,
        'allowed_transitions':    allowed_transitions,
        'siblings':               siblings,
        'status_label':           STATUS_LABELS.get(admission.status, admission.status),
        'can_enrol':              admission.status == 'approved' and not admission.student_id,
        'is_enrolled':            admission.status == 'enrolled' and admission.student_id is not None,
        'today':                  today,
    }
