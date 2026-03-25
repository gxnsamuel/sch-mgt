# students/urls.py
# ─────────────────────────────────────────────────────────────────────────────
# URL patterns for the students app.
# Namespace: 'students'
#
# Include in root urls.py as:
#   path('students/', include('students.urls', namespace='students'))
# ─────────────────────────────────────────────────────────────────────────────

from django.urls import path

from students.views.admission_views import (
    admission_list,
    admission_add,
    admission_edit,
    admission_delete,
    admission_detail,
    admission_update_status,
    admission_enrol,
)

app_name = 'students'

urlpatterns = [

    # ── Admissions ────────────────────────────────────────────────────────────
    #
    #   /students/admissions/                         → list + stats
    #   /students/admissions/add/                     → new application form
    #   /students/admissions/<pk>/                    → detail page
    #   /students/admissions/<pk>/edit/               → edit application
    #   /students/admissions/<pk>/delete/             → confirm + delete
    #   /students/admissions/<pk>/update-status/      → GET form / POST update
    #   /students/admissions/<pk>/enrol/              → GET form / POST enrol → Student
    #
    path('admissions/',                            admission_list,          name='admission_list'),
    path('admissions/add/',                        admission_add,           name='admission_add'),
    path('admissions/<int:pk>/',                   admission_detail,        name='admission_detail'),
    path('admissions/<int:pk>/edit/',              admission_edit,          name='admission_edit'),
    path('admissions/<int:pk>/delete/',            admission_delete,        name='admission_delete'),
    path('admissions/<int:pk>/update-status/',     admission_update_status, name='admission_update_status'),
    path('admissions/<int:pk>/enrol/',             admission_enrol,         name='admission_enrol'),

    # ── Placeholder for Student views (to be added next) ─────────────────────
    # student_list, student_add, student_edit, student_detail, student_delete
    # will be registered here once built.
]
