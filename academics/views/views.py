from django.shortcuts import render, redirect
from django.urls import reverse
from academics.models import SchoolSupportedClasses, SchoolClass
from django.contrib import messages




def school_supported_classes_manage(request):

    classes = SchoolClass.objects.all()

    supported_classes = (
        SchoolSupportedClasses.objects
        .select_related("supported_class")
        .all()
    )

    # =========================
    # ADD SUPPORTED CLASSES
    # =========================

    if request.method == "POST" and request.POST.get("action") == "create":

        total_added = 0

        for c in classes:

            value = request.POST.get(
                f"class_{c.key}"
            )

            if value == c.key:

                exists = (
                    SchoolSupportedClasses.objects
                    .filter(
                        supported_class=c
                    )
                    .exists()
                )

                if not exists:

                    SchoolSupportedClasses.objects.create(
                        supported_class=c
                    )

                    total_added += 1

        messages.success(
            request,
            f"{total_added} class(es) added."
        )

        return redirect(
            reverse(
                "academics:school_supported_classes_manage"
            )
        )

    # =========================
    # UPDATE SUPPORTED CLASSES
    # =========================

    if request.method == "POST" and request.POST.get("action") == "update":

        total_updated = 0

        # Clear existing

        SchoolSupportedClasses.objects.all().delete()

        for c in classes:

            value = request.POST.get(
                f"class_{c.key}"
            )

            if value == c.key:

                SchoolSupportedClasses.objects.create(
                    supported_class=c
                )

                total_updated += 1

        messages.success(
            request,
            f"Supported classes updated ({total_updated})."
        )

        return redirect(
            reverse(
                "academics:school_supported_classes_manage"
            )
        )

    supported_class_ids = (
    SchoolSupportedClasses.objects
    .values_list(
        "supported_class_id",
        flat=True
    )
)

    return render(
        request,
        "academics/class/supported_classes_manage.html",
        {
            "classes": classes,
            "supported_classes": supported_classes,
            "supported_class_ids": supported_class_ids,
        }
    )


