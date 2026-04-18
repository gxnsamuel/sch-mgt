# fees/views/add_payment_view.py
# Multi-step Add Payment — school / assessment / scholastic
# Rules: FBV only, no forms.py, no CBV, no JSON, messages for feedback,
#        login_required on every view, transaction.atomic on all saves.

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render

from fees.models import (
    AssessmentFees, FeesClass, FeesPayment, SchoolFees,
    SchoolScholasticRequirements, ScholasticRequirementClass,
    StudentFeesPaymentsStatus, StudentScholasticRequirementStatus,
)
from fees.utils.payment_utils import generate_receipt_number
from students.models import Student

_T = 'fees/payments/'

PAYMENT_TYPE_CHOICES = [
    ("school",     "School Fees Payment"),
    ("assessment", "Assessment Fees Payment"),
    ("scholastic", "Scholastic Requirements"),
]

_ALL_KEYS = [
    "payment_part1_done", "payment_part2_done",
    "payment_part3_done", "payment_part4_done",
    "payment_type", "student_id", "student_mini", "class_id",
    "fees_list", "payment_amounts", "selected_fees",
    "selected_fee_ids", "skipped_fees",
]


def _clear_session(request):
    for key in _ALL_KEYS:
        request.session.pop(key, None)
    request.session.modified = True


@login_required
def add_payment(request):

    # ── RESET ─────────────────────────────────────────────────────────────
    if request.GET.get("reset") == "1":
        _clear_session(request)
        messages.info(request, "Payment process reset.")
        return redirect("fees:add_payment")

    # ── CANCEL ────────────────────────────────────────────────────────────
    if request.method == "POST" and request.POST.get("action") == "cancel_payment":
        _clear_session(request)
        messages.info(request, "Payment process cancelled.")
        return redirect("fees:add_payment")

    # =========================================================================
    # PART 1 — Student + payment type
    # =========================================================================
    if request.method == "POST" and not request.session.get("payment_part1_done"):
        student_id   = request.POST.get("student", "").strip()
        payment_type = request.POST.get("payment_type", "").strip()
        errors = {}

        if not student_id:
            errors["student"] = "Student is required."
        else:
            try:
                student = (
                    Student.objects.select_related("current_class")
                    .filter(student_id=student_id, is_active=True).first()
                )
                if not student:
                    errors["student"] = "No active student found with that ID."
            except Exception:
                errors["student"] = "Student lookup failed."

        if payment_type not in [t[0] for t in PAYMENT_TYPE_CHOICES]:
            errors["payment_type"] = "Select a valid payment type."

        if errors:
            return render(request, f'{_T}form.html', {
                "errors": errors,
                "payment_type_choices": PAYMENT_TYPE_CHOICES,
                "students": Student.objects.filter(is_active=True),
            })

        current_class = student.current_class
        if not current_class:
            messages.error(request, "This student has no class assigned.")
            return redirect("fees:add_payment")

        student_mini = {
            "id":         student.pk,
            "student_id": student.student_id,
            "name":       student.full_name,
            "class":      current_class.supported_class.name,
        }

        fees_list = []

        if payment_type == "school":
            qs = FeesClass.objects.filter(
                school_class=current_class,
                fees__isnull=False,
                fees__is_active=True,
            ).select_related("fees", "fees__term")
            for fc in qs:
                fee_type = (
                    fc.fees.get_fees_type_display()
                    if fc.fees.fees_type != "other"
                    else (fc.fees.title or fc.fees.get_fees_type_display())
                )
                fees_list.append({
                    "id":     fc.fees.pk,
                    "type":   fee_type,
                    "term":   fc.fees.term.name,
                    "amount": float(fc.fees.amount),
                })

        elif payment_type == "assessment":
            qs = FeesClass.objects.filter(
                school_class=current_class,
                assessment_fee__isnull=False,
            ).select_related("assessment_fee", "assessment_fee__assessment", "assessment_fee__term")
            fees_list = [
                {
                    "id":     fc.assessment_fee.pk,
                    "name":   fc.assessment_fee.assessment.title,
                    "term":   fc.assessment_fee.term.name,
                    "amount": float(fc.assessment_fee.amount),
                }
                for fc in qs if fc.assessment_fee.amount is not None
            ]

        elif payment_type == "scholastic":
            qs = ScholasticRequirementClass.objects.filter(
                school_class=current_class,
                requirement__is_active=True,
            ).select_related("requirement", "requirement__term")
            fees_list = [
                {
                    "id":              rc.requirement.pk,
                    "name":            rc.requirement.item_name,
                    "term":            rc.requirement.term.name,
                    "quantity_needed": rc.requirement.quantity,
                    "unit":            rc.requirement.get_unit_display(),
                    "monetary_value":  float(rc.requirement.monetary_value),
                    "unit_price":      float(rc.requirement.unit_price),
                }
                for rc in qs
            ]

        request.session["payment_part1_done"] = True
        request.session["payment_type"]       = payment_type
        request.session["student_id"]         = student.pk
        request.session["class_id"]           = current_class.pk
        request.session["student_mini"]       = student_mini
        request.session["fees_list"]          = fees_list
        request.session.modified = True

        messages.success(request, "Step 1 complete.")
        return redirect("fees:add_payment")

    # =========================================================================
    # PART 2 — Select fees / requirements
    # =========================================================================
    if request.method == "POST" and request.POST.get("step") == "part2":
        if not request.session.get("payment_part1_done"):
            messages.error(request, "Complete Step 1 first.")
            return redirect("fees:add_payment")

        selected_ids = [
            request.POST[key] for key in request.POST if key.startswith("fee_")
        ]
        if not selected_ids:
            messages.error(request, "Select at least one item to continue.")
            return redirect("fees:add_payment")

        fees_list     = request.session.get("fees_list", [])
        selected_fees = [f for f in fees_list if str(f.get("id")) in selected_ids]
        skipped_fees  = [f for f in fees_list if str(f.get("id")) not in selected_ids]

        if not selected_fees:
            messages.error(request, "Invalid selection.")
            return redirect("fees:add_payment")

        request.session["payment_part2_done"] = True
        request.session["selected_fee_ids"]   = selected_ids
        request.session["selected_fees"]      = selected_fees
        request.session["skipped_fees"]       = skipped_fees
        request.session.modified = True

        messages.success(request, "Selection saved.")
        return redirect("fees:add_payment")

    # =========================================================================
    # PART 3 — Collect amounts / quantities
    # =========================================================================
    if request.method == "POST" and request.POST.get("step") == "part3":
        if not request.session.get("payment_part2_done"):
            messages.error(request, "Complete Step 2 first.")
            return redirect("fees:add_payment")

        selected_fees   = request.session.get("selected_fees", [])
        payment_type    = request.session.get("payment_type")
        payment_amounts = {}
        errors          = []

        if payment_type == "scholastic":
            for item in selected_fees:
                req_id          = item.get("id")
                monetary_value  = float(item.get("monetary_value", 0))
                unit_price      = float(item.get("unit_price", 0))
                quantity_needed = int(item.get("quantity_needed", 0))
                item_name       = item.get("name", "")

                raw_qty  = request.POST.get(f"qty_{req_id}",  "").strip()
                raw_cash = request.POST.get(f"cash_{req_id}", "").strip()

                qty_brought = 0
                cash_amount = 0.0

                if raw_qty:
                    try:
                        qty_brought = int(raw_qty)
                        if qty_brought < 0:
                            errors.append(f"Quantity cannot be negative for {item_name}.")
                            continue
                        qty_brought = min(qty_brought, quantity_needed)
                    except (ValueError, TypeError):
                        errors.append(f"Invalid quantity for {item_name}.")
                        continue

                if raw_cash:
                    try:
                        cash_amount = float(raw_cash)
                        if cash_amount < 0:
                            errors.append(f"Cash amount cannot be negative for {item_name}.")
                            continue
                    except (ValueError, TypeError):
                        errors.append(f"Invalid cash amount for {item_name}.")
                        continue

                if qty_brought == 0 and cash_amount == 0:
                    errors.append(f"Enter a quantity or cash amount for {item_name}.")
                    continue

                physical_credit = qty_brought * unit_price
                balance = max(0.0, monetary_value - physical_credit - cash_amount)
                status  = "Fully Met" if balance == 0 else "Partially Met"

                payment_amounts[str(req_id)] = {
                    "name":            item_name,
                    "term":            item.get("term"),
                    "unit":            item.get("unit"),
                    "quantity_needed": quantity_needed,
                    "qty_brought":     qty_brought,
                    "monetary_value":  monetary_value,
                    "cash_amount":     cash_amount,
                    "balance":         balance,
                    "status":          status,
                }

        else:
            for fee in selected_fees:
                fee_id     = fee.get("id")
                fee_amount = float(fee.get("amount", 0))
                label      = fee.get("name") or fee.get("type") or "Fee"
                raw_amount = request.POST.get(f"amount_{fee_id}", "").strip()

                if not raw_amount:
                    errors.append(f"Amount required for {label}.")
                    continue
                try:
                    amount = float(raw_amount)
                    if amount <= 0:
                        errors.append(f"Amount must be > 0 for {label}.")
                        continue
                except (ValueError, TypeError):
                    errors.append(f"Invalid amount for {label}.")
                    continue

                if amount >= fee_amount:
                    balance = 0.0
                    status  = "Fully Paid"
                else:
                    balance = round(fee_amount - amount, 2)
                    status  = "Partially Paid"

                payment_amounts[str(fee_id)] = {
                    "type":    fee.get("type") or fee.get("name"),
                    "term":    fee.get("term"),
                    "amount":  amount,
                    "balance": balance,
                    "status":  status,
                }

        if errors:
            for err in errors:
                messages.error(request, err)
            return redirect("fees:add_payment")

        request.session["payment_amounts"]    = payment_amounts
        request.session["payment_part3_done"] = True
        request.session.modified = True

        messages.success(request, "Amounts captured.")
        return redirect("fees:add_payment")

    # =========================================================================
    # PART 4 — Verify password, save to DB, clear session
    # =========================================================================
    if request.method == "POST" and request.POST.get("step") == "part4":
        if not request.session.get("payment_part3_done"):
            messages.error(request, "Complete Step 3 first.")
            return redirect("fees:add_payment")

        handler_password = request.POST.get("handler_password", "")
        if not handler_password or not request.user.check_password(handler_password):
            messages.error(request, "Incorrect password. Payment was not recorded.")
            return redirect("fees:add_payment")

        student_id      = request.session.get("student_id")
        payment_type    = request.session.get("payment_type")
        payment_amounts = request.session.get("payment_amounts", {})
        today           = date.today()

        try:
            student       = Student.objects.get(pk=student_id)
            current_class = student.current_class
        except Student.DoesNotExist:
            messages.error(request, "Student not found. Please start again.")
            _clear_session(request)
            return redirect("fees:add_payment")

        try:
            with transaction.atomic():

                # ── Scholastic ────────────────────────────────────────────
                if payment_type == "scholastic":
                    for req_id_str, data in payment_amounts.items():
                        req_obj = SchoolScholasticRequirements.objects.get(pk=int(req_id_str))

                        status_row, _ = StudentScholasticRequirementStatus.objects.get_or_create(
                            student     = student,
                            requirement = req_obj,
                            defaults={
                                "school_class":       current_class,
                                "quantity_brought":   0,
                                "amount_paid_ugx":    0,
                                "amount_balance_ugx": req_obj.monetary_value,
                                "fully_met":          False,
                            }
                        )

                        qty_brought = int(data.get("qty_brought", 0))
                        cash_amount = float(data.get("cash_amount", 0))

                        status_row.quantity_brought += qty_brought
                        status_row.amount_paid_ugx   = float(status_row.amount_paid_ugx) + cash_amount

                        physical_credit = status_row.quantity_brought * float(req_obj.unit_price)
                        new_balance = max(
                            0.0,
                            float(req_obj.monetary_value)
                            - physical_credit
                            - float(status_row.amount_paid_ugx)
                        )
                        status_row.amount_balance_ugx = new_balance
                        status_row.fully_met          = new_balance <= 0

                        if qty_brought > 0:
                            status_row.last_brought_on = today
                        if cash_amount > 0:
                            status_row.last_paid_on = today
                        if status_row.fully_met and not status_row.fully_met_on:
                            status_row.fully_met_on = today

                        status_row.recorded_by = request.user
                        status_row.save()

                # ── School Fees ───────────────────────────────────────────
                elif payment_type == "school":
                    for fee_id_str, data in payment_amounts.items():
                        fee_obj = SchoolFees.objects.get(pk=int(fee_id_str))
                        amount  = float(data.get("amount", 0))

                        FeesPayment.objects.create(
                            receipt_number = generate_receipt_number(),
                            student        = student,
                            term           = fee_obj.term,
                            school_fees    = fee_obj,
                            school_class   = current_class,
                            amount         = amount,
                            payment_date   = today,
                            handled_by     = request.user,
                        )

                        status_row, _ = StudentFeesPaymentsStatus.objects.get_or_create(
                            student     = student,
                            school_fees = fee_obj,
                            defaults={
                                "payment_type":   "school",
                                "school_class":   current_class,
                                "amount_paid":    0,
                                "amount_balance": fee_obj.amount,
                            }
                        )
                        status_row.amount_paid    = float(status_row.amount_paid) + amount
                        new_balance               = float(status_row.amount_balance) - amount
                        status_row.amount_balance = max(0.0, new_balance)
                        status_row.fully_paid     = status_row.amount_balance <= 0
                        if status_row.fully_paid and not status_row.fully_paid_on:
                            status_row.fully_paid_on = today
                        status_row.save()

                # ── Assessment Fees ───────────────────────────────────────
                elif payment_type == "assessment":
                    for fee_id_str, data in payment_amounts.items():
                        fee_obj = AssessmentFees.objects.get(pk=int(fee_id_str))
                        amount  = float(data.get("amount", 0))

                        FeesPayment.objects.create(
                            receipt_number  = generate_receipt_number(),
                            student         = student,
                            term            = fee_obj.term,
                            assessment_fees = fee_obj,
                            school_class    = current_class,
                            amount          = amount,
                            payment_date    = today,
                            handled_by      = request.user,
                        )

                        status_row, _ = StudentFeesPaymentsStatus.objects.get_or_create(
                            student         = student,
                            assessment_fees = fee_obj,
                            defaults={
                                "payment_type":   "assessment",
                                "school_class":   current_class,
                                "amount_paid":    0,
                                "amount_balance": fee_obj.amount,
                            }
                        )
                        status_row.amount_paid    = float(status_row.amount_paid) + amount
                        new_balance               = float(status_row.amount_balance) - amount
                        status_row.amount_balance = max(0.0, new_balance)
                        status_row.fully_paid     = status_row.amount_balance <= 0
                        if status_row.fully_paid and not status_row.fully_paid_on:
                            status_row.fully_paid_on = today
                        status_row.save()

        except Exception as exc:
            messages.error(request, f"Payment failed: {exc}")
            return redirect("fees:add_payment")

        _clear_session(request)
        messages.success(request, "Payment recorded successfully.")
        return redirect("fees:payment_list")

    # =========================================================================
    # GET — render based on session state
    # =========================================================================
    steps = {
        "payment_part1_done": request.session.get("payment_part1_done", False),
        "payment_part2_done": request.session.get("payment_part2_done", False),
        "payment_part3_done": request.session.get("payment_part3_done", False),
        "payment_part4_done": request.session.get("payment_part4_done", False),
    }

    context = {
        "payment_type_choices": PAYMENT_TYPE_CHOICES,
        "students":             Student.objects.filter(is_active=True),
        "student_mini":         request.session.get("student_mini"),
        "fees_list":            request.session.get("fees_list", []),
        "selected_fees":        request.session.get("selected_fees", []),
        "payment_amounts":      request.session.get("payment_amounts", {}),
        "payment_type":         request.session.get("payment_type"),
        "today_str":            date.today().strftime("%d %b %Y"),
        **steps,
    }

    return render(request, f'{_T}form.html', context)
