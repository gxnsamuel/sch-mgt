# school/utils/calendar_utils.py
# ─────────────────────────────────────────────────────────────────────────────
# Helpers for SchoolCalendar views:
#   - Manual field validation
#   - POST / file data parsing
#   - List-level and detail statistics
# ─────────────────────────────────────────────────────────────────────────────

import os
from datetime import date

from django.db.models import Count, Q

from school.models import SchoolCalendar


# ═══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

ALLOWED_DOCUMENT_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.docx'}
MAX_DOCUMENT_SIZE_MB         = 10
MAX_DOCUMENT_SIZE_BYTES      = MAX_DOCUMENT_SIZE_MB * 1024 * 1024


# ═══════════════════════════════════════════════════════════════════════════════
#  VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def validate_and_parse_calendar(
    post: dict,
    files: dict,
    instance: SchoolCalendar | None = None,
) -> tuple[dict, dict]:
    """
    Manually validate all SchoolCalendar POST fields.

    Returns:
        (cleaned_data, errors)

    cleaned_data — ready for setattr loop on the instance.
                   term_id stored as int; view resolves FK.
    errors       — dict of field_name → error message string.
                   Empty dict = validation passed.
    """
    errors:  dict = {}
    cleaned: dict = {}

    # ── title ─────────────────────────────────────────────────────────────────
    title = (post.get('title') or '').strip()
    if not title:
        errors['title'] = 'Calendar title is required.'
    elif len(title) > 200:
        errors['title'] = 'Title must not exceed 200 characters.'
    else:
        cleaned['title'] = title

    # ── academic_year ─────────────────────────────────────────────────────────
    # Free-text but validated to be a plausible 4-digit year string
    academic_year = (post.get('academic_year') or '').strip()
    if not academic_year:
        errors['academic_year'] = 'Academic year is required (e.g. 2025).'
    else:
        try:
            yr = int(academic_year)
            current = date.today().year
            if yr < 2000 or yr > current + 5:
                errors['academic_year'] = (
                    f'Academic year must be between 2000 and {current + 5}.'
                )
            else:
                cleaned['academic_year'] = str(yr)
        except ValueError:
            errors['academic_year'] = (
                'Academic year must be a valid year number (e.g. 2025).'
            )

    # ── term (FK — resolved in view) ──────────────────────────────────────────
    term_id = (post.get('term') or '').strip()
    if not term_id:
        errors['term'] = 'Term is required.'
    else:
        try:
            cleaned['term_id'] = int(term_id)
        except ValueError:
            errors['term'] = 'Invalid term selected.'

    # ── description ───────────────────────────────────────────────────────────
    cleaned['description'] = (post.get('description') or '').strip()

    # ── is_active ─────────────────────────────────────────────────────────────
    cleaned['is_active'] = (
        str(post.get('is_active', '')).strip().lower()
        in ('1', 'true', 'on', 'yes')
    )

    # ── is_published ──────────────────────────────────────────────────────────
    cleaned['is_published'] = (
        str(post.get('is_published', '')).strip().lower()
        in ('1', 'true', 'on', 'yes')
    )

    # ── published_at ──────────────────────────────────────────────────────────
    # Only set if publishing; left as None for drafts.
    # The view stamps it with timezone.now() when transitioning to published.
    cleaned['_publishing_now'] = cleaned['is_published']

    # ── document validation ────────────────────────────────────────────────────
    document = files.get('document')
    if document:
        ext = os.path.splitext(document.name)[1].lower()
        if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
            errors['document'] = (
                'Calendar document must be a PDF, image (JPG/PNG), '
                'or Word (.docx) file.'
            )
        elif document.size > MAX_DOCUMENT_SIZE_BYTES:
            errors['document'] = (
                f'Document must not exceed {MAX_DOCUMENT_SIZE_MB} MB '
                f'(uploaded: {document.size / (1024 * 1024):.1f} MB).'
            )

    # ── clear_document flag (handled in view) ─────────────────────────────────
    cleaned['clear_document'] = (
        str(post.get('clear_document', '')).strip().lower()
        in ('1', 'true', 'on', 'yes')
    )

    # ── Uniqueness: one calendar per term ─────────────────────────────────────
    if 'term_id' in cleaned:
        qs = SchoolCalendar.objects.filter(term_id=cleaned['term_id'])
        if instance and instance.pk:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            errors['term'] = (
                'A calendar for this term already exists. '
                'Edit the existing one instead of creating a duplicate.'
            )

    return cleaned, errors


# ═══════════════════════════════════════════════════════════════════════════════
#  LIST STATS
# ═══════════════════════════════════════════════════════════════════════════════

def get_calendar_list_stats() -> dict:
    """High-level statistics shown above the calendars list."""
    qs = SchoolCalendar.objects.all()

    total     = qs.count()
    published = qs.filter(is_published=True).count()
    draft     = qs.filter(is_published=False).count()
    active    = qs.filter(is_active=True).count()
    inactive  = qs.filter(is_active=False).count()

    # Calendars that have a document uploaded vs none
    with_document    = qs.filter(document__isnull=False).exclude(document='').count()
    without_document = total - with_document

    # By academic year
    by_year = list(
        qs.values('academic_year')
        .annotate(total=Count('id'))
        .order_by('-academic_year')
    )

    # By term number
    by_term = list(
        qs.values('term__name', 'term__start_date')
        .annotate(total=Count('id'))
        .order_by('-term__start_date')[:10]
    )

    # Current academic year calendars
    current_year = str(date.today().year)
    current_year_calendars = list(
        qs.filter(academic_year=current_year)
        .select_related('term', 'created_by')
        .order_by('term__name')
    )

    # Most recently published
    recently_published = list(
        qs.filter(is_published=True)
        .select_related('term', 'created_by')
        .order_by('-published_at')[:5]
    )

    # Available academic years for filter dropdown
    years = list(
        qs.values_list('academic_year', flat=True)
        .distinct()
        .order_by('-academic_year')
    )

    return {
        'total':                  total,
        'published':              published,
        'draft':                  draft,
        'active':                 active,
        'inactive':               inactive,
        'with_document':          with_document,
        'without_document':       without_document,
        'by_year':                by_year,
        'by_term':                by_term,
        'current_year':           current_year,
        'current_year_calendars': current_year_calendars,
        'recently_published':     recently_published,
        'years':                  years,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  DETAIL STATS
# ═══════════════════════════════════════════════════════════════════════════════

def get_calendar_detail_stats(calendar: SchoolCalendar) -> dict:
    """
    Stats and context for the single calendar detail page.
    Pulls in the linked Term's milestones and events for display.
    """
    term = calendar.term

    # Term milestone summary (reuse Term properties)
    milestones = []
    def _add(label: str, d, category: str):
        if d:
            milestones.append({
                'label':    label,
                'date':     d,
                'category': category,
                'is_past':  d < date.today(),
            })

    if term:
        _add('Term Opens',              term.start_date,           'term')
        _add('BOT Exams Begin',         term.bot_start_date,       'exam')
        _add('BOT Exams End',           term.bot_end_date,         'exam')
        _add('MOT Exams Begin',         term.mot_start_date,       'exam')
        _add('MOT Exams End',           term.mot_end_date,         'exam')
        _add('Normal Lessons End',      term.end_date,             'term')
        _add('EOT Exams Begin',         term.eot_start_date,       'exam')
        _add('EOT Exams End',           term.eot_end_date,         'exam')
        _add('School Closes',           term.closing_date,         'term')
        _add('Holiday Studies Begin',   term.holiday_study_start,  'holiday')
        _add('Holiday Studies End',     term.holiday_study_end,    'holiday')
        _add('Long Holiday Begins',     term.long_holiday_start,   'holiday')
        _add('Next Term Opens',         term.opening_date,         'term')

    milestones = sorted(
        [m for m in milestones if m['date']],
        key=lambda x: x['date']
    )

    # School events that fall within this term's date range
    from school.models import SchoolEvent
    term_events = []
    if term and term.start_date and term.end_date:
        term_events = list(
            SchoolEvent.objects.filter(
                is_published=True,
                start_date__gte=term.start_date,
                start_date__lte=term.end_date,
            )
            .select_related('organized_by')
            .order_by('start_date')
        )

    # Sibling calendars (same academic year, different terms)
    siblings = list(
        SchoolCalendar.objects
        .filter(academic_year=calendar.academic_year)
        .exclude(pk=calendar.pk)
        .select_related('term')
        .order_by('term__name')
    )

    # Prev / Next calendars by term start_date
    prev_calendar = (
        SchoolCalendar.objects
        .filter(term__start_date__lt=term.start_date if term else None)
        .exclude(pk=calendar.pk)
        .select_related('term')
        .order_by('-term__start_date')
        .first()
        if term else None
    )
    next_calendar = (
        SchoolCalendar.objects
        .filter(term__start_date__gt=term.start_date if term else None)
        .exclude(pk=calendar.pk)
        .select_related('term')
        .order_by('term__start_date')
        .first()
        if term else None
    )

    # Holiday study classes (if term has them)
    holiday_classes = (
        term.holiday_study_classes.all().order_by('section', 'level', 'stream')
        if term and term.has_holiday_studies else []
    )

    return {
        'milestones':       milestones,
        'term_events':      term_events,
        'term_events_count': len(term_events),
        'siblings':         siblings,
        'prev_calendar':    prev_calendar,
        'next_calendar':    next_calendar,
        'holiday_classes':  holiday_classes,
    }
