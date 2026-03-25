# school/utils/requirement_utils.py
# ─────────────────────────────────────────────────────────────────────────────
# Helpers for SchoolRequirement views:
#   - Manual field validation
#   - POST data parsing
#   - List-level and detail statistics
# ─────────────────────────────────────────────────────────────────────────────

from decimal import Decimal, InvalidOperation

from django.db.models import Count, Q, Sum

from school.models import SchoolRequirement


# ═══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

VALID_CATEGORIES = {
    'stationery', 'uniform', 'scholastic', 'sports', 'equipment', 'other'
}

CATEGORY_LABELS = {
    'stationery': 'Stationery',
    'uniform':    'School Uniform',
    'scholastic': 'Scholastic Materials / Books',
    'sports':     'Sports / P.E. Kit',
    'equipment':  'Equipment / Tools',
    'other':      'Other',
}


# ═══════════════════════════════════════════════════════════════════════════════
#  VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def validate_and_parse_requirement(
    post: dict,
    instance: SchoolRequirement | None = None
) -> tuple[dict, dict]:
    """
    Manually validate all SchoolRequirement POST fields.

    Returns:
        (cleaned_data, errors)

    cleaned_data — ready for SchoolRequirement(**cleaned) or setattr loop on edit.
                   Does NOT include FK objects — view resolves those from IDs.
    errors       — dict of field_name → error message.
                   Empty dict = validation passed.
    """
    errors:  dict = {}
    cleaned: dict = {}

    # ── title ─────────────────────────────────────────────────────────────────
    title = (post.get('title') or '').strip()
    if not title:
        errors['title'] = 'Requirement title is required.'
    elif len(title) > 200:
        errors['title'] = 'Title must not exceed 200 characters.'
    else:
        cleaned['title'] = title

    # ── description ───────────────────────────────────────────────────────────
    description = (post.get('description') or '').strip()
    if not description:
        errors['description'] = 'Description is required.'
    else:
        cleaned['description'] = description

    # ── category ──────────────────────────────────────────────────────────────
    category = (post.get('category') or '').strip()
    if not category:
        errors['category'] = 'Category is required.'
    elif category not in VALID_CATEGORIES:
        errors['category'] = (
            f'Invalid category. Choose one of: {", ".join(sorted(VALID_CATEGORIES))}.'
        )
    else:
        cleaned['category'] = category

    # ── school_class (optional FK — resolved in view) ─────────────────────────
    # Stored as raw ID string; view resolves to object or None
    school_class_id = (post.get('school_class') or '').strip()
    if school_class_id:
        try:
            cleaned['school_class_id'] = int(school_class_id)
        except ValueError:
            errors['school_class'] = 'Invalid class selected.'
    else:
        cleaned['school_class_id'] = None   # school-wide requirement

    # ── term (optional FK — resolved in view) ─────────────────────────────────
    term_id = (post.get('term') or '').strip()
    if term_id:
        try:
            cleaned['term_id'] = int(term_id)
        except ValueError:
            errors['term'] = 'Invalid term selected.'
    else:
        cleaned['term_id'] = None

    # ── estimated_cost ────────────────────────────────────────────────────────
    cost_raw = (post.get('estimated_cost') or '').strip()
    if cost_raw:
        try:
            cost_val = Decimal(cost_raw)
            if cost_val < 0:
                errors['estimated_cost'] = 'Estimated cost cannot be negative.'
            elif cost_val > Decimal('999999999.99'):
                errors['estimated_cost'] = 'Estimated cost value is too large.'
            else:
                cleaned['estimated_cost'] = cost_val
        except InvalidOperation:
            errors['estimated_cost'] = 'Estimated cost must be a valid number (e.g. 15000).'
    else:
        cleaned['estimated_cost'] = None

    # ── is_compulsory ─────────────────────────────────────────────────────────
    cleaned['is_compulsory'] = (
        str(post.get('is_compulsory', '')).strip().lower() in ('1', 'true', 'on', 'yes')
    )

    # ── is_published ──────────────────────────────────────────────────────────
    cleaned['is_published'] = (
        str(post.get('is_published', '')).strip().lower() in ('1', 'true', 'on', 'yes')
    )

    return cleaned, errors


# ═══════════════════════════════════════════════════════════════════════════════
#  LIST STATS
# ═══════════════════════════════════════════════════════════════════════════════

def get_requirement_list_stats() -> dict:
    """
    High-level statistics shown above the requirements list.
    """
    qs = SchoolRequirement.objects.all()

    total       = qs.count()
    published   = qs.filter(is_published=True).count()
    draft       = qs.filter(is_published=False).count()
    compulsory  = qs.filter(is_compulsory=True).count()
    optional    = qs.filter(is_compulsory=False).count()

    # School-wide vs class-specific
    school_wide     = qs.filter(school_class__isnull=True).count()
    class_specific  = qs.filter(school_class__isnull=False).count()

    # By category
    by_category = list(
        qs.values('category')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    for row in by_category:
        row['label'] = CATEGORY_LABELS.get(row['category'], row['category'])

    # By class
    by_class = list(
        qs.exclude(school_class__isnull=True)
        .values(
            'school_class__level',
            'school_class__stream',
            'school_class__section',
        )
        .annotate(total=Count('id'))
        .order_by('school_class__section', 'school_class__level')
    )

    # By term
    by_term = list(
        qs.exclude(term__isnull=True)
        .values(
            'term__name',
            'term__start_date',
        )
        .annotate(total=Count('id'))
        .order_by('-term__start_date')
    )

    # Total estimated cost of all published compulsory requirements
    total_cost = (
        qs.filter(is_published=True, is_compulsory=True)
        .aggregate(s=Sum('estimated_cost'))['s']
        or Decimal('0')
    )

    # Terms that have requirements — for filter dropdown
    from academics.models import Term
    terms_with_reqs = Term.objects.filter(
        requirements__isnull=False
    ).distinct().order_by('-start_date')

    return {
        'total':            total,
        'published':        published,
        'draft':            draft,
        'compulsory':       compulsory,
        'optional':         optional,
        'school_wide':      school_wide,
        'class_specific':   class_specific,
        'by_category':      by_category,
        'by_class':         by_class,
        'by_term':          by_term,
        'total_est_cost':   total_cost,
        'terms_with_reqs':  terms_with_reqs,
    }
