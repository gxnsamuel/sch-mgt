# school/utils/setting_utils.py
# ─────────────────────────────────────────────────────────────────────────────
# Helpers for SchoolSetting views:
#   - Singleton loader (get or None)
#   - Manual field-by-field validation split into sections
#   - File (image) validation
#   - Profile completeness checker
# ─────────────────────────────────────────────────────────────────────────────

import os
from datetime import date

from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from school.models import SchoolSetting


# ═══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

VALID_SCHOOL_TYPES  = {'day', 'boarding', 'mixed'}
VALID_OWNERSHIP     = {'government', 'private', 'community', 'faith_based'}
VALID_REGIONS       = {'central', 'eastern', 'northern', 'western'}
VALID_CURRICULA     = {'uganda', 'ib', 'british', 'mixed'}

ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
MAX_IMAGE_SIZE_MB         = 2
MAX_IMAGE_SIZE_BYTES      = MAX_IMAGE_SIZE_MB * 1024 * 1024


# ═══════════════════════════════════════════════════════════════════════════════
#  SINGLETON LOADER
# ═══════════════════════════════════════════════════════════════════════════════

def get_school_setting() -> SchoolSetting | None:
    """
    Returns the single SchoolSetting record, or None if not yet created.
    Never raises — callers handle the None case.
    """
    return SchoolSetting.objects.first()


# ═══════════════════════════════════════════════════════════════════════════════
#  FILE VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def _validate_image(file, field_label: str, errors: dict) -> bool:
    """
    Validates an uploaded image file.
    Returns True if valid (or no file uploaded), False if invalid.
    Writes to errors dict on failure.
    """
    if not file:
        return True

    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        errors[field_label] = (
            f'{field_label} must be a JPG, PNG, or WebP image '
            f'(uploaded: {file.name}).'
        )
        return False

    if file.size > MAX_IMAGE_SIZE_BYTES:
        errors[field_label] = (
            f'{field_label} must not exceed {MAX_IMAGE_SIZE_MB} MB '
            f'(uploaded: {file.size / (1024*1024):.1f} MB).'
        )
        return False

    return True


# ═══════════════════════════════════════════════════════════════════════════════
#  FULL PROFILE VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def validate_and_parse_setting(post: dict, files: dict) -> tuple[dict, dict]:
    """
    Validates all SchoolSetting POST fields manually.

    Returns:
        (cleaned_data, errors)

    cleaned_data  — dict ready for setattr loop on the instance.
                    Does NOT include image fields (handled separately
                    by the view using request.FILES).
    errors        — dict of field_name → error message string.
                    Empty dict = validation passed.

    Sections validated:
        Identity     — school_name (required), motto
        Registration — registration_number, establishment_year,
                       ownership, school_type, curriculum
        Location     — address, district, region (required),
                       county, sub_county, village, po_box
        Contact      — phone (required), alt_phone, email, website
        Academic     — has_nursery, has_primary, report_footer_text
    """
    errors:  dict = {}
    cleaned: dict = {}

    # ── IDENTITY ──────────────────────────────────────────────────────────────

    school_name = (post.get('school_name') or '').strip()
    if not school_name:
        errors['school_name'] = 'School name is required.'
    elif len(school_name) > 200:
        errors['school_name'] = 'School name must not exceed 200 characters.'
    else:
        cleaned['school_name'] = school_name

    motto = (post.get('school_motto') or '').strip()
    if len(motto) > 200:
        errors['school_motto'] = 'School motto must not exceed 200 characters.'
    else:
        cleaned['school_motto'] = motto

    # ── REGISTRATION ──────────────────────────────────────────────────────────

    cleaned['registration_number'] = (post.get('registration_number') or '').strip()

    est_year_raw = (post.get('establishment_year') or '').strip()
    if est_year_raw:
        try:
            est_year = int(est_year_raw)
            current_year = date.today().year
            if est_year < 1800 or est_year > current_year:
                errors['establishment_year'] = (
                    f'Establishment year must be between 1800 and {current_year}.'
                )
            else:
                cleaned['establishment_year'] = est_year
        except ValueError:
            errors['establishment_year'] = 'Establishment year must be a valid year number.'
    else:
        cleaned['establishment_year'] = None

    ownership = (post.get('ownership') or '').strip()
    if not ownership:
        errors['ownership'] = 'School ownership type is required.'
    elif ownership not in VALID_OWNERSHIP:
        errors['ownership'] = 'Invalid ownership type selected.'
    else:
        cleaned['ownership'] = ownership

    school_type = (post.get('school_type') or '').strip()
    if not school_type:
        errors['school_type'] = 'School type is required.'
    elif school_type not in VALID_SCHOOL_TYPES:
        errors['school_type'] = 'Invalid school type selected.'
    else:
        cleaned['school_type'] = school_type

    curriculum = (post.get('curriculum') or '').strip()
    if not curriculum:
        errors['curriculum'] = 'Curriculum type is required.'
    elif curriculum not in VALID_CURRICULA:
        errors['curriculum'] = 'Invalid curriculum selected.'
    else:
        cleaned['curriculum'] = curriculum

    # ── LOCATION ──────────────────────────────────────────────────────────────

    address = (post.get('address') or '').strip()
    if not address:
        errors['address'] = 'School physical address is required.'
    else:
        cleaned['address'] = address

    district = (post.get('district') or '').strip()
    if not district:
        errors['district'] = 'District is required.'
    elif len(district) > 100:
        errors['district'] = 'District name must not exceed 100 characters.'
    else:
        cleaned['district'] = district

    region = (post.get('region') or '').strip()
    if not region:
        errors['region'] = 'Region is required.'
    elif region not in VALID_REGIONS:
        errors['region'] = 'Invalid region selected.'
    else:
        cleaned['region'] = region

    for field in ('county', 'sub_county', 'village', 'po_box'):
        val = (post.get(field) or '').strip()
        max_len = 50 if field == 'po_box' else 100
        if len(val) > max_len:
            label = field.replace('_', ' ').title()
            errors[field] = f'{label} must not exceed {max_len} characters.'
        else:
            cleaned[field] = val

    # ── CONTACT ───────────────────────────────────────────────────────────────

    phone = (post.get('phone') or '').strip()
    if not phone:
        errors['phone'] = 'Primary phone number is required.'
    elif len(phone) > 15:
        errors['phone'] = 'Phone number must not exceed 15 characters.'
    elif not phone.replace('+', '').replace(' ', '').replace('-', '').isdigit():
        errors['phone'] = 'Phone number must contain only digits, spaces, hyphens, or a leading +.'
    else:
        cleaned['phone'] = phone

    alt_phone = (post.get('alt_phone') or '').strip()
    if alt_phone:
        if len(alt_phone) > 15:
            errors['alt_phone'] = 'Alternative phone must not exceed 15 characters.'
        elif not alt_phone.replace('+', '').replace(' ', '').replace('-', '').isdigit():
            errors['alt_phone'] = 'Alternative phone must contain only digits, spaces, hyphens, or a leading +.'
        else:
            cleaned['alt_phone'] = alt_phone
    else:
        cleaned['alt_phone'] = ''

    email = (post.get('email') or '').strip()
    if email:
        try:
            validate_email(email)
            cleaned['email'] = email
        except ValidationError:
            errors['email'] = 'Enter a valid email address.'
    else:
        cleaned['email'] = ''

    website = (post.get('website') or '').strip()
    if website:
        if not website.startswith(('http://', 'https://')):
            errors['website'] = 'Website URL must start with http:// or https://'
        elif len(website) > 200:
            errors['website'] = 'Website URL must not exceed 200 characters.'
        else:
            cleaned['website'] = website
    else:
        cleaned['website'] = ''

    # ── ACADEMIC CONFIG ───────────────────────────────────────────────────────

    cleaned['has_nursery'] = str(post.get('has_nursery', '')).strip().lower() in (
        '1', 'true', 'on', 'yes'
    )
    cleaned['has_primary'] = str(post.get('has_primary', '')).strip().lower() in (
        '1', 'true', 'on', 'yes'
    )

    if not cleaned['has_nursery'] and not cleaned['has_primary']:
        errors['has_nursery'] = (
            'The school must have at least one section — Nursery or Primary.'
        )

    cleaned['report_footer_text'] = (post.get('report_footer_text') or '').strip()

    # ── IMAGE VALIDATION (from files dict) ────────────────────────────────────

    for field, label in [
        ('school_logo',            'School Logo'),
        ('school_stamp',           'School Stamp'),
        ('head_teacher_signature', 'Head Teacher Signature'),
    ]:
        _validate_image(files.get(field), label, errors)
        # Note: actual file saving is handled in the view via instance field assignment

    return cleaned, errors


# ═══════════════════════════════════════════════════════════════════════════════
#  SETTINGS-ONLY VALIDATION  (academic config + report card section only)
# ═══════════════════════════════════════════════════════════════════════════════

def validate_and_parse_settings_only(post: dict) -> tuple[dict, dict]:
    """
    Validates only the academic configuration / settings fields.
    Used by the dedicated Settings view which edits a subset of the profile.

    Fields covered:
        has_nursery, has_primary, report_footer_text,
        school_type, curriculum, ownership
    """
    errors:  dict = {}
    cleaned: dict = {}

    ownership = (post.get('ownership') or '').strip()
    if not ownership:
        errors['ownership'] = 'Ownership type is required.'
    elif ownership not in VALID_OWNERSHIP:
        errors['ownership'] = 'Invalid ownership type selected.'
    else:
        cleaned['ownership'] = ownership

    school_type = (post.get('school_type') or '').strip()
    if not school_type:
        errors['school_type'] = 'School type is required.'
    elif school_type not in VALID_SCHOOL_TYPES:
        errors['school_type'] = 'Invalid school type.'
    else:
        cleaned['school_type'] = school_type

    curriculum = (post.get('curriculum') or '').strip()
    if not curriculum:
        errors['curriculum'] = 'Curriculum is required.'
    elif curriculum not in VALID_CURRICULA:
        errors['curriculum'] = 'Invalid curriculum.'
    else:
        cleaned['curriculum'] = curriculum

    cleaned['has_nursery'] = str(post.get('has_nursery', '')).strip().lower() in (
        '1', 'true', 'on', 'yes'
    )
    cleaned['has_primary'] = str(post.get('has_primary', '')).strip().lower() in (
        '1', 'true', 'on', 'yes'
    )

    if not cleaned['has_nursery'] and not cleaned['has_primary']:
        errors['has_nursery'] = (
            'At least one section (Nursery or Primary) must be enabled.'
        )

    cleaned['report_footer_text'] = (post.get('report_footer_text') or '').strip()

    return cleaned, errors


# ═══════════════════════════════════════════════════════════════════════════════
#  PROFILE COMPLETENESS
# ═══════════════════════════════════════════════════════════════════════════════

def get_profile_completeness(setting: SchoolSetting) -> dict:
    """
    Returns a completeness score and a list of missing/incomplete fields.
    Used on the profile and mini profile pages to nudge admins to fill gaps.

    Returns:
        {
            'score':    85,          # 0–100 integer
            'missing':  [...],       # list of human-readable missing field names
            'complete': True/False,  # True if score == 100
        }
    """
    checks = [
        (bool(setting.school_name),             'School Name'),
        (bool(setting.school_motto),            'School Motto'),
        (bool(setting.school_logo),             'School Logo'),
        (bool(setting.school_stamp),            'School Stamp'),
        (bool(setting.head_teacher_signature),  'Head Teacher Signature'),
        (bool(setting.registration_number),     'MoES Registration Number'),
        (bool(setting.establishment_year),      'Establishment Year'),
        (bool(setting.address),                 'Physical Address'),
        (bool(setting.district),                'District'),
        (bool(setting.region),                  'Region'),
        (bool(setting.county),                  'County'),
        (bool(setting.sub_county),              'Sub-County'),
        (bool(setting.phone),                   'Primary Phone'),
        (bool(setting.email),                   'Email Address'),
        (bool(setting.website),                 'Website'),
        (bool(setting.report_footer_text),      'Report Card Footer Text'),
    ]

    total   = len(checks)
    done    = sum(1 for passed, _ in checks if passed)
    missing = [label for passed, label in checks if not passed]
    score   = round((done / total) * 100)

    return {
        'score':    score,
        'missing':  missing,
        'complete': score == 100,
        'done':     done,
        'total':    total,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  DISPLAY LABEL MAPS  (passed to templates to avoid repeated get_FOO_display calls)
# ═══════════════════════════════════════════════════════════════════════════════

OWNERSHIP_LABELS = {
    'government':  'Government',
    'private':     'Private',
    'community':   'Community',
    'faith_based': 'Faith-Based / Mission',
}

SCHOOL_TYPE_LABELS = {
    'day':      'Day School',
    'boarding': 'Boarding School',
    'mixed':    'Day & Boarding',
}

REGION_LABELS = {
    'central':  'Central Region',
    'eastern':  'Eastern Region',
    'northern': 'Northern Region',
    'western':  'Western Region',
}

CURRICULUM_LABELS = {
    'uganda':  'Uganda National Curriculum (MoES)',
    'ib':      'International Baccalaureate (IB)',
    'british': 'British Curriculum',
    'mixed':   'Mixed / Custom',
}


def get_display_labels(setting: SchoolSetting) -> dict:
    """Returns human-readable display labels for all choice fields."""
    return {
        'ownership_display':    OWNERSHIP_LABELS.get(setting.ownership, setting.ownership),
        'school_type_display':  SCHOOL_TYPE_LABELS.get(setting.school_type, setting.school_type),
        'region_display':       REGION_LABELS.get(setting.region, setting.region),
        'curriculum_display':   CURRICULUM_LABELS.get(setting.curriculum, setting.curriculum),
    }
