# views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.dateparse import parse_date
from django.core.exceptions import ValidationError

from academics.models import AcademicYear


# =========================
# LIST ACADEMIC YEARS
# =========================

def academic_year_list(request):

    years = AcademicYear.objects.all()

    context = {
        "years": years,
        "current_year": AcademicYear.objects.current(),
    }

    return render(
        request,
        "academics/academic_year/list.html",
        context
    )


# =========================
# ADD ACADEMIC YEAR
# =========================

def academic_year_create(request):

    if request.method == "POST":

        name = request.POST.get("name")
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")
        is_active = request.POST.get("is_active")

        try:

            year = AcademicYear(
                name=name,
                start_date=parse_date(start_date),
                end_date=parse_date(end_date),
                is_active=True if is_active else False
            )

            year.save()

            messages.success(
                request,
                "Academic year created successfully."
            )

            return redirect(
                "academics:academic_year_list"
            )

        except ValidationError as e:

            messages.error(
                request,
                e.message
            )

        except Exception:

            messages.error(
                request,
                "Something went wrong."
            )

    return render(
        request,
        "academics/academic_year/create.html"
    )


# =========================
# UPDATE ACADEMIC YEAR
# =========================

def academic_year_update(request, pk):

    year = get_object_or_404(
        AcademicYear,
        pk=pk
    )

    if request.method == "POST":

        name = request.POST.get("name")
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")
        is_active = request.POST.get("is_active")

        try:

            year.name = name
            year.start_date = parse_date(start_date)
            year.end_date = parse_date(end_date)
            year.is_active = True if is_active else False

            year.save()

            messages.success(
                request,
                "Academic year updated successfully."
            )

            return redirect(
                "academics:academic_year_list"
            )

        except ValidationError as e:

            messages.error(
                request,
                e.message
            )

        except Exception:

            messages.error(
                request,
                "Update failed."
            )

    context = {
        "year": year
    }

    return render(
        request,
        "academics/academic_year/update.html",
        context
    )


# =========================
# DELETE ACADEMIC YEAR
# =========================

def academic_year_delete(request, pk):

    year = get_object_or_404(
        AcademicYear,
        pk=pk
    )

    if request.method == "POST":

        year.delete()

        messages.success(
            request,
            "Academic year deleted successfully."
        )

        return redirect(
            "academics:academic_year_list"
        )

    context = {
        "year": year
    }

    return render(
        request,
        "academics/academic_year/delete.html",
        context
    )
