# accounts/urls.py  (updated — register_parent removed)
# ─────────────────────────────────────────────────────────────────────────────

from django.urls import path

from accounts.views import (
    user_list,
    register_staff,
    user_detail,
    user_toggle_active,
)

app_name = 'accounts'

urlpatterns = [

    # ── User management ───────────────────────────────────────────────────────
    path('users/',                          user_list,          name='user_list'),
    path('users/<int:pk>/',                 user_detail,        name='user_detail'),
    path('users/<int:pk>/toggle-active/',   user_toggle_active, name='user_toggle_active'),

    # ── Registration ──────────────────────────────────────────────────────────
    # NOTE: register_parent is removed.
    # Parents are created automatically during student enrolment
    # (students/enrol/ or students/admissions/<pk>/verify/parents/).
    path('register/staff/', register_staff, name='register_staff'),
]
