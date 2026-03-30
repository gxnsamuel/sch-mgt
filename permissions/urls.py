# permissions/urls.py
# ─────────────────────────────────────────────────────────────────────────────
# URL patterns for the permissions app.
# Namespace: 'permissions'
#
# Include in root urls.py as:
#   path('permissions/', include('permissions.urls', namespace='permissions'))
# ─────────────────────────────────────────────────────────────────────────────

from django.urls import path

from permissions.views import (
    assign_choose_roles,
    assign_confirm,
    assign_edit_roles,
    assign_review,
    assign_save_role,
    assign_summary,
    permission_add,
    permission_detail,
    permission_list,
    permission_remove_role,
    permission_toggle_active,
    permission_update_role,
)

app_name = 'permissions'

urlpatterns = [

    # ── Permission CRUD ───────────────────────────────────────────────────────
    path('',
         permission_list,
         name='permission_list'),

    path('add/',
         permission_add,
         name='permission_add'),

    path('<int:pk>/',
         permission_detail,
         name='permission_detail'),

    path('<int:pk>/toggle-active/',
         permission_toggle_active,
         name='permission_toggle_active'),

    path('<int:pk>/remove-role/',
         permission_remove_role,
         name='permission_remove_role'),

    path('<int:pk>/update-role/',
         permission_update_role,
         name='permission_update_role'),

    # ── Assignment flow ───────────────────────────────────────────────────────
    # Step 1 — choose roles
    path('assign/',
         assign_choose_roles,
         name='assign_choose_roles'),

    # Step 2 — accordion editor (GET) + save one role (POST via assign_save_role)
    path('assign/edit/',
         assign_edit_roles,
         name='assign_edit_roles'),

    # POST-only sub-action: save one role accordion
    path('assign/save-role/',
         assign_save_role,
         name='assign_save_role'),

    # Step 3 — review + password confirm
    path('assign/review/',
         assign_review,
         name='assign_review'),

    # POST-only: validate password, activate, redirect to summary
    path('assign/confirm/',
         assign_confirm,
         name='assign_confirm'),

    # Step 4 — read-only summary
    path('assign/summary/',
         assign_summary,
         name='assign_summary'),
]
