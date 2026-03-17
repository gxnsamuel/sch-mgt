# urls.py
# JOKS School Connect - URL Configuration

from django.urls import path
from . import views, views_extended

urlpatterns = [
    # ============================================================================
    # AUTHENTICATION
    # ============================================================================
    path('signin/', views.signin_view, name='signin'),
    path('signup/', views.signup_view, name='signup'),
    path('signout/', views.signout_view, name='signout'),
    
    # ============================================================================
    # PUBLIC PAGES
    # ============================================================================
    path('', views.home_view, name='home'),
    path('about/', views.about_view, name='about'),
    path('admissions/', views.admissions_info_view, name='admissions_info'),
    path('fees/', views.fees_structure_view, name='fees_structure_public'),
    path('events/', views.events_view, name='events'),
    path('gallery/', views.gallery_view, name='gallery'),
    path('contact/', views.contact_view, name='contact'),
    
    # ============================================================================
    # ADMISSION APPLICATIONS
    # ============================================================================
    path('apply/', views.apply_admission_view, name='apply_admission'),
    path('admin/applications/', views.applications_list_view, name='applications_list'),
    path('admin/applications/<uuid:application_id>/', views.application_detail_view, name='application_detail'),
    path('admin/applications/<uuid:application_id>/update-status/', views.application_update_status_view, name='application_update_status'),
    path('admin/applications/<uuid:application_id>/convert/', views.application_convert_student_view, name='application_convert_student'),
    
    # ============================================================================
    # STUDENTS
    # ============================================================================
    path('students/', views.students_list_view, name='students_list'),
    path('students/<uuid:student_id>/', views.student_detail_view, name='student_detail'),
    path('students/add/', views.student_add_view, name='student_add'),
    path('students/<uuid:student_id>/edit/', views.student_edit_view, name='student_edit'),
    path('students/<uuid:student_id>/deactivate/', views.student_deactivate_view, name='student_deactivate'),
    path('students/<uuid:student_id>/activate/', views.student_activate_view, name='student_activate'),
    
    # ============================================================================
    # TEACHERS
    # ============================================================================
    path('teachers/', views.teachers_list_view, name='teachers_list'),
    path('teachers/<uuid:teacher_id>/', views.teacher_detail_view, name='teacher_detail'),
    path('teachers/add/', views.teacher_add_view, name='teacher_add'),
    path('teachers/<uuid:teacher_id>/edit/', views.teacher_edit_view, name='teacher_edit'),
    path('teachers/<uuid:teacher_id>/deactivate/', views.teacher_deactivate_view, name='teacher_deactivate'),
    path('teachers/<uuid:teacher_id>/activate/', views.teacher_activate_view, name='teacher_activate'),
    
    # ============================================================================
    # PARENTS
    # ============================================================================
    path('parents/', views_extended.parents_list_view, name='parents_list'),
    path('parents/<uuid:parent_id>/', views_extended.parent_detail_view, name='parent_detail'),
    
    # ============================================================================
    # CLASSROOMS
    # ============================================================================
    path('classrooms/', views_extended.classrooms_list_view, name='classrooms_list'),
    path('classrooms/<uuid:classroom_id>/', views_extended.classroom_detail_view, name='classroom_detail'),
    path('classrooms/add/', views_extended.classroom_add_view, name='classroom_add'),
    path('classrooms/<uuid:classroom_id>/edit/', views_extended.classroom_edit_view, name='classroom_edit'),
    
    # ============================================================================
    # ATTENDANCE
    # ============================================================================
    path('attendance/mark/<uuid:classroom_id>/', views_extended.attendance_mark_view, name='attendance_mark'),
    path('attendance/report/', views_extended.attendance_report_view, name='attendance_report'),
    
    # ============================================================================
    # GRADES
    # ============================================================================
    path('grades/entry/<uuid:classroom_id>/', views_extended.grades_entry_view, name='grades_entry'),
    path('grades/student/<uuid:student_id>/', views_extended.grades_view_student, name='grades_view_student'),
    
    # ============================================================================
    # FEES
    # ============================================================================
    path('fees/structures/', views_extended.fee_structures_list_view, name='fee_structures_list'),
    path('fees/structures/add/', views_extended.fee_structure_add_view, name='fee_structure_add'),
    path('fees/payments/', views_extended.fee_payments_list_view, name='fee_payments_list'),
    path('fees/payments/student/<uuid:student_id>/', views_extended.fee_payments_list_view, name='fee_payments_student'),
    path('fees/payments/add/<uuid:student_id>/', views_extended.fee_payment_add_view, name='fee_payment_add'),
    
    # ============================================================================
    # MESSAGES
    # ============================================================================
    path('messages/inbox/', views_extended.messages_inbox_view, name='messages_inbox'),
    path('messages/sent/', views_extended.messages_sent_view, name='messages_sent'),
    path('messages/compose/', views_extended.message_compose_view, name='message_compose'),
    path('messages/<uuid:message_id>/', views_extended.message_detail_view, name='message_detail'),
    
    # ============================================================================
    # ANNOUNCEMENTS
    # ============================================================================
    path('announcements/', views_extended.announcements_list_view, name='announcements_list'),
    path('announcements/add/', views_extended.announcement_add_view, name='announcement_add'),
    path('announcements/<uuid:announcement_id>/edit/', views_extended.announcement_edit_view, name='announcement_edit'),
    path('announcements/<uuid:announcement_id>/delete/', views_extended.announcement_delete_view, name='announcement_delete'),
    
    # ============================================================================
    # DASHBOARDS
    # ============================================================================
    path('dashboard/', views_extended.dashboard_redirect_view, name='dashboard'),
    path('dashboard/admin/', views_extended.admin_dashboard_view, name='admin_dashboard'),
    path('dashboard/teacher/', views_extended.teacher_dashboard_view, name='teacher_dashboard'),
    path('dashboard/parent/', views_extended.parent_dashboard_view, name='parent_dashboard'),
]