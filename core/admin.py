from django.contrib import admin

# Register your models here.
"""
JOKS School Connect - Django Admin Configuration
Register and configure all models in the admin interface
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import *


# ============================================================================
# USER & AUTHENTICATION ADMIN
# ============================================================================

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'get_full_name', 'role', 'is_active', 'date_joined']
    list_filter = ['role', 'is_active', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    fieldsets = (
        ('Basic Info', {'fields': ('username', 'email', 'first_name', 'last_name', 'role')}),
        ('Contact', {'fields': ('phone', 'address', 'date_of_birth')}),
        ('Profile', {'fields': ('profile_picture',)}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
    )


# ============================================================================
# ACADEMIC STRUCTURE ADMIN
# ============================================================================

@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'end_date', 'is_current']
    list_filter = ['is_current']
    actions = ['set_as_current']
    
    def set_as_current(self, request, queryset):
        AcademicYear.objects.update(is_current=False)
        queryset.update(is_current=True)
    set_as_current.short_description = "Set selected as current academic year"


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'academic_year', 'term_number', 'start_date', 'end_date', 'is_current']
    list_filter = ['academic_year', 'term_number', 'is_current']
    ordering = ['-academic_year__start_date', 'term_number']


@admin.register(GradeLevel)
class GradeLevelAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'min_age', 'max_age', 'order']
    list_filter = ['category']
    ordering = ['order']


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code']
    filter_horizontal = ['grade_levels']


@admin.register(ClassRoom)
class ClassRoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'grade_level', 'academic_year', 'class_teacher', 'capacity', 'room_number']
    list_filter = ['academic_year', 'grade_level']
    search_fields = ['name', 'room_number']
    raw_id_fields = ['class_teacher']


# ============================================================================
# STUDENT & PARENT ADMIN
# ============================================================================

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['admission_number', 'get_full_name', 'current_class', 'gender', 'is_active', 'admission_date']
    list_filter = ['gender', 'is_active', 'current_class__grade_level', 'admission_date']
    search_fields = ['admission_number', 'first_name', 'last_name', 'email']
    readonly_fields = ['admission_number']
    fieldsets = (
        ('Basic Information', {
            'fields': ('admission_number', 'first_name', 'middle_name', 'last_name', 
                      'date_of_birth', 'gender', 'blood_group')
        }),
        ('Current Assignment', {
            'fields': ('current_class',)
        }),
        ('Medical Information', {
            'fields': ('medical_conditions', 'emergency_contact', 'emergency_contact_name', 
                      'emergency_contact_relationship')
        }),
        ('Documents', {
            'fields': ('birth_certificate', 'passport_photo', 'previous_school_report', 
                      'leaving_certificate', 'medical_form'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active', 'admission_date')
        })
    )
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    get_full_name.short_description = 'Full Name'


@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    list_display = ['user', 'occupation', 'employer', 'student_count']
    search_fields = ['user__first_name', 'user__last_name', 'user__email']
    raw_id_fields = ['user']
    filter_horizontal = ['students']
    
    def student_count(self, obj):
        return obj.students.count()
    student_count.short_description = 'Number of Children'


@admin.register(StudentParent)
class StudentParentAdmin(admin.ModelAdmin):
    list_display = ['student', 'parent', 'relationship', 'is_primary_contact', 'can_pickup']
    list_filter = ['relationship', 'is_primary_contact', 'can_pickup']
    search_fields = ['student__first_name', 'student__last_name', 'parent__user__first_name']
    raw_id_fields = ['student', 'parent']


# ============================================================================
# TEACHER ADMIN
# ============================================================================

@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ['employee_id', 'user', 'qualification', 'employment_type', 'date_joined', 'is_active']
    list_filter = ['employment_type', 'is_active', 'date_joined']
    search_fields = ['employee_id', 'user__first_name', 'user__last_name']
    raw_id_fields = ['user']
    filter_horizontal = ['subjects']
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'employee_id')
        }),
        ('Professional Details', {
            'fields': ('qualification', 'specialization', 'subjects')
        }),
        ('Employment', {
            'fields': ('employment_type', 'date_joined', 'date_left', 'salary')
        }),
        ('Emergency Contact', {
            'fields': ('emergency_contact', 'emergency_contact_name', 'emergency_contact_relationship')
        }),
        ('Status', {
            'fields': ('is_active',)
        })
    )


@admin.register(TeacherAssignment)
class TeacherAssignmentAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'subject', 'classroom', 'academic_year', 'is_active']
    list_filter = ['academic_year', 'is_active', 'subject']
    raw_id_fields = ['teacher', 'classroom']


# ============================================================================
# ATTENDANCE ADMIN
# ============================================================================

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['student', 'classroom', 'date', 'status', 'marked_by', 'marked_at']
    list_filter = ['status', 'date', 'classroom']
    search_fields = ['student__first_name', 'student__last_name', 'student__admission_number']
    date_hierarchy = 'date'
    raw_id_fields = ['student', 'marked_by']


# ============================================================================
# GRADES & ASSESSMENT ADMIN
# ============================================================================

@admin.register(GradingScale)
class GradingScaleAdmin(admin.ModelAdmin):
    list_display = ['grade', 'min_score', 'max_score', 'description', 'grade_point']
    ordering = ['-min_score']


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'assessment_type', 'subject', 'classroom', 'term', 'date', 'max_marks']
    list_filter = ['assessment_type', 'subject', 'term', 'date']
    search_fields = ['name']
    date_hierarchy = 'date'
    raw_id_fields = ['created_by']


@admin.register(StudentGrade)
class StudentGradeAdmin(admin.ModelAdmin):
    list_display = ['student', 'assessment', 'marks_obtained', 'grade', 'graded_by', 'graded_at']
    list_filter = ['grade', 'assessment__subject', 'graded_at']
    search_fields = ['student__first_name', 'student__last_name', 'student__admission_number']
    raw_id_fields = ['student', 'assessment', 'graded_by']
    readonly_fields = ['grade']


@admin.register(ReportCard)
class ReportCardAdmin(admin.ModelAdmin):
    list_display = ['student', 'term', 'classroom', 'overall_average', 'overall_grade', 
                   'position_in_class', 'published', 'published_at']
    list_filter = ['term', 'published', 'classroom__grade_level']
    search_fields = ['student__first_name', 'student__last_name', 'student__admission_number']
    raw_id_fields = ['student']
    readonly_fields = ['generated_at']


# ============================================================================
# FEES MANAGEMENT ADMIN
# ============================================================================

@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ['grade_level', 'academic_year', 'tuition_per_term', 'meals_per_term', 
                   'transport_per_term', 'total_per_term']
    list_filter = ['academic_year', 'grade_level']
    
    def total_per_term(self, obj):
        return obj.get_total_per_term(include_meals=True, include_transport=True)
    total_per_term.short_description = 'Total (All Inclusive)'


@admin.register(FeeInvoice)
class FeeInvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'student', 'term', 'total_amount', 'amount_paid', 
                   'balance', 'status', 'due_date']
    list_filter = ['status', 'term', 'due_date']
    search_fields = ['invoice_number', 'student__first_name', 'student__last_name', 
                    'student__admission_number']
    readonly_fields = ['balance']
    raw_id_fields = ['student']
    date_hierarchy = 'created_at'


@admin.register(FeePayment)
class FeePaymentAdmin(admin.ModelAdmin):
    list_display = ['receipt_number', 'invoice', 'amount', 'payment_method', 'payment_date', 
                   'reference_number', 'received_by']
    list_filter = ['payment_method', 'payment_date']
    search_fields = ['receipt_number', 'reference_number', 'invoice__invoice_number']
    raw_id_fields = ['invoice', 'received_by']
    date_hierarchy = 'payment_date'


# ============================================================================
# EVENTS & ACTIVITIES ADMIN
# ============================================================================

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'date', 'start_time', 'end_time', 'location', 'is_public']
    list_filter = ['category', 'is_public', 'date']
    search_fields = ['title', 'description']
    date_hierarchy = 'date'
    raw_id_fields = ['created_by']
    
    fieldsets = (
        ('Event Details', {
            'fields': ('title', 'description', 'category', 'image')
        }),
        ('Date & Time', {
            'fields': ('date', 'start_time', 'end_time', 'location')
        }),
        ('Visibility', {
            'fields': ('is_public', 'target_audience')
        })
    )


# ============================================================================
# GALLERY ADMIN
# ============================================================================

@admin.register(GalleryImage)
class GalleryImageAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'image_preview', 'is_featured', 'uploaded_at']
    list_filter = ['category', 'is_featured', 'uploaded_at']
    search_fields = ['title', 'description']
    raw_id_fields = ['event', 'uploaded_by']
    date_hierarchy = 'uploaded_at'
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" height="100" />', obj.image.url)
        return '-'
    image_preview.short_description = 'Preview'


# ============================================================================
# TIMETABLE ADMIN
# ============================================================================

@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ['day_of_week', 'period_number', 'start_time', 'end_time', 'is_break']
    list_filter = ['day_of_week', 'is_break']
    ordering = ['day_of_week', 'period_number']


@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    list_display = ['classroom', 'time_slot', 'subject', 'teacher', 'room_number', 'is_active']
    list_filter = ['academic_year', 'is_active', 'classroom__grade_level']
    raw_id_fields = ['classroom', 'teacher']
    search_fields = ['classroom__name']


# ============================================================================
# ADMISSIONS ADMIN
# ============================================================================

@admin.register(AdmissionApplication)
class AdmissionApplicationAdmin(admin.ModelAdmin):
    list_display = ['application_number', 'get_applicant_name', 'desired_grade_level', 
                   'status', 'submitted_at', 'assessment_date']
    list_filter = ['status', 'desired_grade_level', 'submitted_at']
    search_fields = ['application_number', 'first_name', 'last_name', 'parent_email']
    readonly_fields = ['application_number', 'submitted_at']
    date_hierarchy = 'submitted_at'
    raw_id_fields = ['reviewed_by', 'converted_to_student']
    
    fieldsets = (
        ('Application Info', {
            'fields': ('application_number', 'status', 'submitted_at')
        }),
        ('Student Details', {
            'fields': ('first_name', 'middle_name', 'last_name', 'date_of_birth', 'gender')
        }),
        ('Desired Placement', {
            'fields': ('desired_grade_level', 'desired_academic_year')
        }),
        ('Parent/Guardian', {
            'fields': ('parent_name', 'parent_email', 'parent_phone', 'parent_address')
        }),
        ('Previous School', {
            'fields': ('previous_school',),
            'classes': ('collapse',)
        }),
        ('Documents', {
            'fields': ('birth_certificate', 'passport_photos', 'previous_report', 
                      'leaving_certificate', 'medical_form'),
            'classes': ('collapse',)
        }),
        ('Assessment', {
            'fields': ('assessment_date', 'assessment_score')
        }),
        ('Review', {
            'fields': ('reviewer_notes', 'reviewed_by', 'converted_to_student')
        })
    )
    
    def get_applicant_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    get_applicant_name.short_description = 'Applicant Name'


# ============================================================================
# MESSAGING ADMIN
# ============================================================================

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['subject', 'message_type', 'sender', 'recipient', 'student', 'is_read', 'sent_at']
    list_filter = ['message_type', 'is_read', 'sent_at']
    search_fields = ['subject', 'body', 'sender__username', 'recipient__username']
    raw_id_fields = ['sender', 'recipient', 'student']
    date_hierarchy = 'sent_at'
    readonly_fields = ['sent_at']


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'target_audience', 'grade_level', 'is_urgent', 'publish_date', 
                   'expiry_date', 'created_by']
    list_filter = ['target_audience', 'is_urgent', 'publish_date']
    search_fields = ['title', 'content']
    raw_id_fields = ['created_by', 'grade_level']
    date_hierarchy = 'publish_date'


# ============================================================================
# SCHOOL SETTINGS ADMIN
# ============================================================================

@admin.register(SchoolSettings)
class SchoolSettingsAdmin(admin.ModelAdmin):
    list_display = ['school_name', 'school_email', 'school_phone', 'admissions_open']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('school_name', 'school_motto', 'logo')
        }),
        ('Contact Details', {
            'fields': ('school_email', 'school_phone', 'school_address')
        }),
        ('Social Media', {
            'fields': ('facebook_url', 'twitter_url', 'instagram_url', 'youtube_url')
        }),
        ('Banking Details', {
            'fields': ('bank_name', 'account_name', 'account_number', 'mpesa_paybill')
        }),
        ('Statistics Display', {
            'fields': ('student_teacher_ratio', 'total_students_display', 'total_teachers_display',
                      'years_of_excellence', 'awards_won')
        }),
        ('Admissions', {
            'fields': ('admissions_open',)
        })
    )
    
    def has_add_permission(self, request):
        # Only allow one settings instance
        return not SchoolSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        return False


# ============================================================================
# AUDIT LOG ADMIN
# ============================================================================

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'model_name', 'object_id', 'timestamp', 'ip_address']
    list_filter = ['action', 'model_name', 'timestamp']
    search_fields = ['user__username', 'description', 'object_id']
    readonly_fields = ['user', 'action', 'model_name', 'object_id', 'description', 
                      'ip_address', 'timestamp']
    date_hierarchy = 'timestamp'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False