# fees/utils/pending_fees_utils.py
# =============================================================================
# PURPOSE
# ─────────────────────────────────────────────────────────────────────────────
# Two public functions:
#
#   get_student_pending_fees(student, payment_date=None)
#       Returns every unpaid / partially-paid fee, assessment fee, and
#       scholastic requirement that a student owes from the day they enrolled
#       up to today (or payment_date if supplied).
#       The list is ordered chronologically — oldest debt first.
#       Used in the payment form (Step 2) to present the fees list.
#
#   record_payment_status(student, fee_type, fee_pk, amount_paid,
#                         school_class, term, handled_by, payment_date)
#       Called immediately after a FeesPayment row is saved.
#       Creates the StudentFeesPaymentsStatus row if it doesn't exist yet,
#       then updates amount_paid, amount_balance, fully_paid, fully_paid_on.
#       Wrapped in transaction.atomic() by the calling view — do not wrap here.
#
#   record_scholastic_payment(student, requirement_pk, quantity_brought,
#                             cash_paid, school_class, recorded_by, event_date)
#       Called when a student brings items or pays cash toward a scholastic
#       requirement.
#       Creates the StudentScholasticRequirementStatus row if missing, then
#       recomputes balance using the hybrid formula and saves.
#
# RULES
# ─────────────────────────────────────────────────────────────────────────────
#   • No Django Forms, no CBVs, no JSON responses.
#   • No database writes — get_student_pending_fees is read-only.
#   • All writes go through record_payment_status / record_scholastic_payment.
#   • transaction.atomic() belongs in the calling view, not here.
#   • django.contrib.messages belongs in the calling view, not here.
#   • Every function returns either a value or raises ValueError with a
#     human-readable message the view can pass to messages.error().
# =============================================================================

from datetime import date
from decimal import Decimal

from academics.models import Term
from fees.models import (
    AssessmentFees,
    FeesClass,
    FeesPayment,
    SchoolFees,
    SchoolScholasticRequirements,
    ScholasticRequirementClass,
    StudentClassPromotion,
    StudentFeesPaymentsStatus,
    StudentScholasticRequirementStatus,
)


# ─────────────────────────────────────────────────────────────────────────────
# PRIVATE HELPER — build the student's full class/year timeline
# ─────────────────────────────────────────────────────────────────────────────

def _build_class_year_timeline(student):
    """
    Reconstructs every (SchoolSupportedClasses, year_str) pair
    the student has been enrolled in, from their first year to their
    current class, ordered oldest first.

    Logic
    ──────
    Walk StudentClassPromotion ordered by from_year.
    Each promotion contributes its from_class + from_year.
    The last promotion's to_class + to_year is the current placement.

    If the student has never been promoted yet (brand new enrollment),
    we fall back to (student.current_class, date_enrolled.year).

    Repeated class (student failed and repeated):
        Two promotion rows will share the same from_class with consecutive
        from_year values — both are included; that is correct.

    Example for Nakato:
        Promotion rows:
            P1/2020 → P2/2021
            P2/2021 → P3/2022
            P3/2022 → P4/2023

        Timeline produced:
            (P1, '2020'), (P2, '2021'), (P3, '2022'), (P4, '2023')

    Returns:
        list of (SchoolSupportedClasses instance, year_str '2022')
    """
    promotions = (
        StudentClassPromotion.objects
        .filter(student=student)
        .select_related('from_class', 'to_class',
                        'from_class__supported_class',
                        'to_class__supported_class')
        .order_by('from_year')
    )

    if not promotions.exists():
        # Student enrolled but never promoted yet
        year = str(student.date_enrolled.year)
        return [(student.current_class, year)]

    pairs = []
    for promotion in promotions:
        pairs.append((promotion.from_class, promotion.from_year))

    # The current class is the to_class of the most recent promotion
    last = promotions.last()
    pairs.append((last.to_class, last.to_year))

    return pairs


# ─────────────────────────────────────────────────────────────────────────────
# PRIVATE HELPER — fetch pending school fees for one (class, term)
# ─────────────────────────────────────────────────────────────────────────────

def _get_pending_school_fees(student, school_class, term, year):
    """
    Returns a list of pending-fee dicts for SchoolFees that:
        • are linked to school_class via FeesClass
        • belong to this term
        • are active
        • are NOT fully paid by this student

    If no StudentFeesPaymentsStatus row exists for a fee,
    the student owes the full amount (status has never been created).
    """
    # Get SchoolFees PKs that apply to this class in this term
    fee_pks = (
        FeesClass.objects
        .filter(
            school_class=school_class,
            fees__isnull=False,
            fees__term=term,
            fees__is_active=True,
        )
        .values_list('fees_id', flat=True)
    )

    fees = SchoolFees.objects.filter(pk__in=fee_pks).select_related('term')

    # Fetch all existing status rows for this student for these fees in one query
    status_map = {
        s.school_fees_id: s
        for s in StudentFeesPaymentsStatus.objects.filter(
            student=student,
            school_fees__in=fees,
        )
    }

    pending = []
    for fee in fees:
        status = status_map.get(fee.pk)

        # Skip if fully paid
        if status and status.fully_paid:
            continue

        amount_paid    = status.amount_paid   if status else Decimal('0')
        amount_balance = status.amount_balance if status else fee.amount

        pending.append({
            'type':            'school',
            'fee_id':          fee.pk,
            'label':           fee.title or fee.get_fees_type_display(),
            'fees_type':       fee.fees_type,
            'term':            term,
            'term_label':      str(term),
            'year':            year,
            'school_class':    school_class,
            'class_label':     str(school_class),
            'amount_required': fee.amount,
            'amount_paid':     amount_paid,
            'amount_balance':  amount_balance,
            # status_pk: used by record_payment_status to decide create vs update
            'status_pk':       status.pk if status else None,
        })

    return pending


# ─────────────────────────────────────────────────────────────────────────────
# PRIVATE HELPER — fetch pending assessment fees for one (class, term)
# ─────────────────────────────────────────────────────────────────────────────

def _get_pending_assessment_fees(student, school_class, term, year):
    """
    Returns a list of pending-fee dicts for AssessmentFees that:
        • are linked to school_class via FeesClass
        • belong to this term
        • are NOT fully paid by this student

    NOTE: AssessmentClass.school_class will point to SchoolSupportedClasses
    after the planned update. Until then the FeesClass bridge is the sole
    source of class assignment for assessment fees.
    """
    fee_pks = (
        FeesClass.objects
        .filter(
            school_class=school_class,
            assessment_fee__isnull=False,
            assessment_fee__term=term,
        )
        .values_list('assessment_fee_id', flat=True)
    )

    fees = AssessmentFees.objects.filter(pk__in=fee_pks).select_related(
        'term', 'assessment'
    )

    status_map = {
        s.assessment_fees_id: s
        for s in StudentFeesPaymentsStatus.objects.filter(
            student=student,
            assessment_fees__in=fees,
        )
    }

    pending = []
    for fee in fees:
        status = status_map.get(fee.pk)

        if status and status.fully_paid:
            continue

        fee_amount     = fee.amount or Decimal('0')
        amount_paid    = status.amount_paid    if status else Decimal('0')
        amount_balance = status.amount_balance if status else fee_amount

        label = (
            str(fee.assessment)
            if fee.assessment
            else f"Assessment Fee — {term}"
        )

        pending.append({
            'type':            'assessment',
            'fee_id':          fee.pk,
            'label':           label,
            'fees_type':       'assessment',
            'term':            term,
            'term_label':      str(term),
            'year':            year,
            'school_class':    school_class,
            'class_label':     str(school_class),
            'amount_required': fee_amount,
            'amount_paid':     amount_paid,
            'amount_balance':  amount_balance,
            'status_pk':       status.pk if status else None,
        })

    return pending


# ─────────────────────────────────────────────────────────────────────────────
# PRIVATE HELPER — fetch pending scholastic requirements for one (class, term)
# ─────────────────────────────────────────────────────────────────────────────

def _get_pending_scholastic(student, school_class, term, year):
    """
    Returns a list of pending-requirement dicts for SchoolScholasticRequirements
    that:
        • are linked to school_class via ScholasticRequirementClass
        • belong to this term
        • are active
        • are NOT fully met by this student

    Includes both the cash side and the physical side so the template can
    display the full hybrid picture.
    """
    req_pks = (
        ScholasticRequirementClass.objects
        .filter(
            school_class=school_class,
            requirement__term=term,
            requirement__is_active=True,
        )
        .values_list('requirement_id', flat=True)
    )

    requirements = SchoolScholasticRequirements.objects.filter(pk__in=req_pks)

    status_map = {
        s.requirement_id: s
        for s in StudentScholasticRequirementStatus.objects.filter(
            student=student,
            requirement__in=requirements,
        )
    }

    pending = []
    for req in requirements:
        status = status_map.get(req.pk)

        if status and status.fully_met:
            continue

        amount_paid      = status.amount_paid_ugx    if status else Decimal('0')
        quantity_brought = status.quantity_brought    if status else 0
        amount_balance   = status.amount_balance_ugx if status else req.monetary_value

        pending.append({
            'type':              'scholastic',
            'fee_id':            req.pk,
            'label':             f"{req.quantity} {req.get_unit_display()} of {req.item_name}",
            'fees_type':         'scholastic',
            'term':              term,
            'term_label':        str(term),
            'year':              year,
            'school_class':      school_class,
            'class_label':       str(school_class),
            # Cash side
            'amount_required':   req.monetary_value,
            'amount_paid':       amount_paid,
            'amount_balance':    amount_balance,
            # Physical side
            'quantity_required': req.quantity,
            'quantity_brought':  quantity_brought,
            'unit':              req.get_unit_display(),
            'unit_price':        req.unit_price,
            'status_pk':         status.pk if status else None,
        })

    return pending


# =============================================================================
# PUBLIC — get_student_pending_fees
# =============================================================================

def get_student_pending_fees(student, payment_date=None):
    """
    Returns every fee, assessment fee, and scholastic requirement that
    the student has not fully paid, covering their entire school history
    from enrollment date up to today (or payment_date).

    The result is a flat list of dicts ordered chronologically —
    oldest outstanding item first.

    Each dict always contains:
        type            str   — 'school' | 'assessment' | 'scholastic'
        fee_id          int   — PK of the fee / requirement row
        label           str   — human-readable name
        fees_type       str   — internal type key
        term            Term  — Term ORM instance
        term_label      str   — str(term)
        year            str   — '2022'
        school_class    SchoolSupportedClasses
        class_label     str   — str(school_class)
        amount_required Decimal
        amount_paid     Decimal
        amount_balance  Decimal
        status_pk       int | None  — PK of existing status row, or None

    Scholastic dicts additionally contain:
        quantity_required  int
        quantity_brought   int
        unit               str
        unit_price         Decimal

    Usage in view:
        fees_list = get_student_pending_fees(student)
        # Store serialisable version in session for Step 2/3
        request.session['pending_fees'] = [
            {k: str(v) if not isinstance(v, (int, str, type(None))) else v
             for k, v in item.items()
             if k not in ('term', 'school_class')}
            for item in fees_list
        ]
    """
    today = payment_date or date.today()

    # ── Step 1: reconstruct the student's full class/year history ─────────────
    timeline = _build_class_year_timeline(student)

    all_pending = []

    # ── Step 2: walk each (class, year) pair ──────────────────────────────────
    for school_class, year in timeline:

        # Get every term in this year whose start_date is on or before today.
        # This prevents fetching fees for a future term that hasn't started yet.
        terms = Term.objects.filter(
            start_date__year=int(year),
            start_date__lte=today,
        ).order_by('name')

        # ── Step 3: for each term, gather all three fee types ─────────────────
        for term in terms:

            all_pending.extend(
                _get_pending_school_fees(student, school_class, term, year)
            )
            all_pending.extend(
                _get_pending_assessment_fees(student, school_class, term, year)
            )
            all_pending.extend(
                _get_pending_scholastic(student, school_class, term, year)
            )

    # Result is already chronologically ordered because timeline is oldest-first
    # and terms within each year are ordered by term.name (1, 2, 3).
    return all_pending


# =============================================================================
# PUBLIC — record_payment_status
# =============================================================================

def record_payment_status(student, payment_type, fee_pk, amount_paid,
                           school_class, term, handled_by, payment_date=None):
    """
    Creates or updates the StudentFeesPaymentsStatus row after a payment.
    Call this immediately after FeesPayment is saved, inside the same
    transaction.atomic() block in the view.

    Parameters
    ──────────
    student       Student instance
    payment_type  'school' or 'assessment'
    fee_pk        PK of SchoolFees or AssessmentFees being paid
    amount_paid   Decimal — amount of THIS single payment (not cumulative)
    school_class  SchoolSupportedClasses instance (student's class right now)
    term          Term instance
    handled_by    CustomUser instance (staff recording the payment)
    payment_date  date or None (defaults to today)

    Returns
    ───────
    StudentFeesPaymentsStatus instance (saved)

    Raises
    ──────
    ValueError — if payment_type is invalid or fee not found
    ValueError — if amount_paid exceeds the remaining balance
    """
    today = payment_date or date.today()

    if payment_type not in ('school', 'assessment'):
        raise ValueError(f"Invalid payment_type '{payment_type}'. Must be 'school' or 'assessment'.")

    amount_paid = Decimal(str(amount_paid))

    if payment_type == 'school':
        try:
            fee = SchoolFees.objects.get(pk=fee_pk)
        except SchoolFees.DoesNotExist:
            raise ValueError(f"SchoolFees with pk={fee_pk} does not exist.")

        full_amount = fee.amount

        status, created = StudentFeesPaymentsStatus.objects.get_or_create(
            student=student,
            school_fees=fee,
            defaults={
                'payment_type':   'school',
                'assessment_fees': None,
                'school_class':   school_class,
                'amount_paid':    Decimal('0'),
                'amount_balance': full_amount,
                'fully_paid':     False,
            }
        )

    else:  # assessment
        try:
            fee = AssessmentFees.objects.get(pk=fee_pk)
        except AssessmentFees.DoesNotExist:
            raise ValueError(f"AssessmentFees with pk={fee_pk} does not exist.")

        full_amount = fee.amount or Decimal('0')

        status, created = StudentFeesPaymentsStatus.objects.get_or_create(
            student=student,
            assessment_fees=fee,
            defaults={
                'payment_type': 'assessment',
                'school_fees':  None,
                'school_class': school_class,
                'amount_paid':    Decimal('0'),
                'amount_balance': full_amount,
                'fully_paid':     False,
            }
        )

    # Guard: do not allow overpayment
    if amount_paid > status.amount_balance:
        raise ValueError(
            f"Amount paid (UGX {amount_paid:,.0f}) exceeds the remaining balance "
            f"(UGX {status.amount_balance:,.0f}) for this fee."
        )

    # Update running totals
    status.amount_paid    += amount_paid
    status.amount_balance  = full_amount - status.amount_paid

    # Clamp to zero — floating point safety
    if status.amount_balance < Decimal('0'):
        status.amount_balance = Decimal('0')

    if status.amount_balance == Decimal('0'):
        status.fully_paid    = True
        status.fully_paid_on = today

    status.save()
    return status


# =============================================================================
# PUBLIC — record_scholastic_payment
# =============================================================================

def record_scholastic_payment(student, requirement_pk, quantity_brought,
                               cash_paid, school_class, recorded_by,
                               event_date=None):
    """
    Creates or updates a StudentScholasticRequirementStatus row.
    Call inside the same transaction.atomic() block in the view.

    A student can bring physical items, pay cash, or both in one event.
    Pass 0 for quantity_brought or cash_paid if only one side applies.

    Parameters
    ──────────
    student           Student instance
    requirement_pk    PK of SchoolScholasticRequirements
    quantity_brought  int  — units brought IN THIS EVENT (not cumulative)
    cash_paid         Decimal — cash paid IN THIS EVENT (not cumulative)
    school_class      SchoolSupportedClasses instance
    recorded_by       CustomUser instance
    event_date        date or None (defaults to today)

    Returns
    ───────
    StudentScholasticRequirementStatus instance (saved)

    Raises
    ──────
    ValueError — if requirement not found
    ValueError — if nothing was provided (both zero)
    ValueError — if combined contribution would overshoot the requirement
    """
    today = event_date or date.today()
    cash_paid        = Decimal(str(cash_paid))
    quantity_brought = int(quantity_brought)

    if quantity_brought == 0 and cash_paid == Decimal('0'):
        raise ValueError(
            "Nothing was recorded. Provide at least one unit brought or a cash amount."
        )

    try:
        requirement = SchoolScholasticRequirements.objects.get(pk=requirement_pk)
    except SchoolScholasticRequirements.DoesNotExist:
        raise ValueError(f"SchoolScholasticRequirements with pk={requirement_pk} does not exist.")

    status, created = StudentScholasticRequirementStatus.objects.get_or_create(
        student=student,
        requirement=requirement,
        defaults={
            'school_class':       school_class,
            'quantity_brought':   0,
            'amount_paid_ugx':    Decimal('0'),
            'amount_balance_ugx': requirement.monetary_value,
            'fully_met':          False,
            'recorded_by':        recorded_by,
        }
    )

    # Accumulate
    new_quantity = status.quantity_brought + quantity_brought
    new_cash     = status.amount_paid_ugx  + cash_paid

    # Guard: quantity cannot exceed the requirement
    if new_quantity > requirement.quantity:
        raise ValueError(
            f"Total quantity brought ({new_quantity} {requirement.get_unit_display()}) "
            f"would exceed the requirement ({requirement.quantity} {requirement.get_unit_display()})."
        )

    # Hybrid balance formula:
    #   physical_credit = quantity_brought_so_far × unit_price
    #   balance         = monetary_value − physical_credit − cash_paid_so_far
    physical_credit = Decimal(str(new_quantity)) * requirement.unit_price
    new_balance     = requirement.monetary_value - physical_credit - new_cash

    # Clamp to zero
    if new_balance < Decimal('0'):
        new_balance = Decimal('0')

    # Guard: do not allow overpayment on the cash side beyond what is owed
    if new_balance < Decimal('0'):
        raise ValueError(
            f"Combined physical + cash contribution (UGX {physical_credit + new_cash:,.0f}) "
            f"exceeds the requirement value (UGX {requirement.monetary_value:,.0f})."
        )

    # Save updated values
    status.quantity_brought   = new_quantity
    status.amount_paid_ugx    = new_cash
    status.amount_balance_ugx = new_balance
    status.recorded_by        = recorded_by

    if quantity_brought > 0:
        status.last_brought_on = today
    if cash_paid > Decimal('0'):
        status.last_paid_on = today

    if new_balance == Decimal('0'):
        status.fully_met    = True
        status.fully_met_on = today

    status.save()
    return status
