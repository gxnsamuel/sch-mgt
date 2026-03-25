from django.urls import path
from . import views 





urlpatterns = [
    # ── Public / Auth ──────────────────────────────────────────────────────
    path("",                    views.home,              name="home"),
    path("register/",           views.create_account,    name="create_account"),
    path("activate/",           views.activate_account,  name="activate_account"),
    path("add-password/",       views.add_password,      name="add_password"),
    path("login/",              views.user_login,        name="login"),
    
    path("logout/",             views.user_logout,       name="logout"),

    # ── Dashboard ──────────────────────────────────────────────────────────
    path("dashboard/",          views.dashboard,         name="dashboard"),

    # ── Profile ────────────────────────────────────────────────────────────
    path("profile/",            views.profile,           name="profile"),
    path("profile/edit/",       views.profile_edit,      name="profile_edit"),
    path("profile/updated/",    views.profile_updated,   name="profile_updated"),

    # ── Change Password ────────────────────────────────────────────────────
    path("profile/change-password/", views.change_password, name="change_password"),

    # ── Change Email ───────────────────────────────────────────────────────
    path("profile/change-email/",          views.change_email,             name="change_email"),
    path("profile/change-email/verify/",   views.verify_change_email_otp,  name="verify_change_email_otp"),
    path("profile/change-email/success/",  views.email_change_success,     name="email_change_success"),
    path("profile/change-email/failed/",   views.email_change_failed,      name="email_change_failed"),

    # ── Forgot / reset password flow ───────────────────────────────────────
    path("forgot-password/",           views.forgot_password,    name="forgot_password"),
    path("forgot-password/verify/",    views.fp_verify_identity, name="fp_verify_identity"),
    path("forgot-password/otp/",       views.fp_enter_otp,       name="fp_enter_otp"),
    path("forgot-password/reset/",     views.fp_reset_password,  name="fp_reset_password"),
    path("forgot-password/failed/",    views.fp_recovery_failed, name="fp_recovery_failed"),
]