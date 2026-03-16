from django.db import models

# Create your models here.
"""
JOKS School Connect - Complete Django Models
Extracted from the entire frontend project structure
"""

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid


# ============================================================================
# USER & AUTHENTICATION MODELS
# ============================================================================

class User(AbstractUser):
    """
    Custom User Model extending Django's AbstractUser
    Supports Parent, Teacher, and Admin roles
    """
    ROLE_CHOICES = [
        ('Parent', 'Parent'),
        ('Teacher', 'Teacher'),
        ('Admin', 'Admin'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Parent')
    phone = models.CharField(max_length=20, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"


# ============================================================================
# ACADEMIC STRUCTURE MODELS
# ============================================================================

class AcademicYear(models.Model):
    """Academic Year/Session"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)  # e.g., "2024-2025"
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'academic_years'
        ordering = ['-start_date']
    
    def __str__(self):
        return self.name


class Term(models.Model):
    """School Terms (3 per academic year)"""
    TERM_CHOICES = [
        (1, 'Term 1'),
        (2, 'Term 2'),
        (3, 'Term 3'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='terms')
    term_number = models.IntegerField(choices=TERM_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'terms'
        unique_together = ['academic_year', 'term_number']
        ordering = ['academic_year', 'term_number']
    
    def __str__(self):
        return f"{self.academic_year.name} - Term {self.term_number}"


class GradeLevel(models.Model):
    """
    Grade Levels: Playgroup, PP1, PP2, Grade 1-8
    """
    CATEGORY_CHOICES = [
        ('Nursery', 'Nursery'),
        ('Primary', 'Primary'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50)  # e.g., "Grade 1", "PP1", "Playgroup"
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    min_age = models.IntegerField(help_text="Minimum age in years")
    max_age = models.IntegerField(help_text="Maximum age in years")
    order = models.IntegerField(unique=True, help_text="Display order")
    description = models.TextField(blank=True)
    
    class Meta:
        db_table = 'grade_levels'
        ordering = ['order']
    
    def __str__(self):
        return self.name


class Subject(models.Model):
    """Academic Subjects"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    grade_levels = models.ManyToManyField(GradeLevel, related_name='subjects')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'subjects'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class ClassRoom(models.Model):
    """Classes/Sections"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)  # e.g., "Grade 1A", "PP1 Blue"
    grade_level = models.ForeignKey(GradeLevel, on_delete=models.CASCADE, related_name='classrooms')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='classrooms')
    class_teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                      related_name='classes_as_teacher', limit_choices_to={'role': 'Teacher'})
    capacity = models.IntegerField(default=30)
    room_number = models.CharField(max_length=20, blank=True)
    
    class Meta:
        db_table = 'classrooms'
        unique_together = ['name', 'academic_year']
        ordering = ['grade_level__order', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.academic_year.name})"


# ============================================================================
# STUDENT & PARENT MODELS
# ============================================================================

class Student(models.Model):
    """Student Information"""
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admission_number = models.CharField(max_length=50, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES, blank=True)
    
    # Current Class Assignment
    current_class = models.ForeignKey(ClassRoom, on_delete=models.SET_NULL, null=True, 
                                      related_name='students')
    
    # Medical Information
    medical_conditions = models.TextField(blank=True, help_text="Any medical conditions or allergies")
    emergency_contact = models.CharField(max_length=20)
    emergency_contact_name = models.CharField(max_length=100)
    emergency_contact_relationship = models.CharField(max_length=50)
    
    # Documents
    birth_certificate = models.FileField(upload_to='student_docs/birth_certificates/', blank=True, null=True)
    passport_photo = models.ImageField(upload_to='student_photos/', blank=True, null=True)
    previous_school_report = models.FileField(upload_to='student_docs/reports/', blank=True, null=True)
    leaving_certificate = models.FileField(upload_to='student_docs/leaving_certs/', blank=True, null=True)
    medical_form = models.FileField(upload_to='student_docs/medical/', blank=True, null=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    admission_date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'students'
        ordering = ['first_name', 'last_name']
    
    def __str__(self):
        return f"{self.admission_number} - {self.get_full_name()}"
    
    def get_full_name(self):
        return f"{self.first_name} {self.middle_name} {self.last_name}".replace('  ', ' ')


class Parent(models.Model):
    """Parent/Guardian Information"""
    RELATIONSHIP_CHOICES = [
        ('Father', 'Father'),
        ('Mother', 'Mother'),
        ('Guardian', 'Guardian'),
        ('Other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='parent_profile', 
                                limit_choices_to={'role': 'Parent'})
    students = models.ManyToManyField(Student, related_name='parents', through='StudentParent')
    occupation = models.CharField(max_length=100, blank=True)
    employer = models.CharField(max_length=200, blank=True)
    office_address = models.TextField(blank=True)
    
    class Meta:
        db_table = 'parents'
    
    def __str__(self):
        return f"{self.user.get_full_name()}"


class StudentParent(models.Model):
    """Link between Students and Parents with relationship type"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    parent = models.ForeignKey(Parent, on_delete=models.CASCADE)
    relationship = models.CharField(max_length=20, choices=Parent.RELATIONSHIP_CHOICES)
    is_primary_contact = models.BooleanField(default=False)
    can_pickup = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'student_parents'
        unique_together = ['student', 'parent']
    
    def __str__(self):
        return f"{self.parent.user.get_full_name()} - {self.student.get_full_name()} ({self.relationship})"


# ============================================================================
# TEACHER MODELS
# ============================================================================

class Teacher(models.Model):
    """Teacher Profile"""
    EMPLOYMENT_TYPE_CHOICES = [
        ('Full-Time', 'Full-Time'),
        ('Part-Time', 'Part-Time'),
        ('Contract', 'Contract'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile',
                                limit_choices_to={'role': 'Teacher'})
    employee_id = models.CharField(max_length=50, unique=True)
    
    # Professional Details
    qualification = models.CharField(max_length=200)
    specialization = models.CharField(max_length=200, blank=True)
    subjects = models.ManyToManyField(Subject, related_name='teachers')
    
    # Employment Details
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES)
    date_joined = models.DateField()
    date_left = models.DateField(blank=True, null=True)
    salary = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    # Emergency Contact
    emergency_contact = models.CharField(max_length=20)
    emergency_contact_name = models.CharField(max_length=100)
    emergency_contact_relationship = models.CharField(max_length=50)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'teachers'
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.employee_id}"


class TeacherAssignment(models.Model):
    """Teacher Subject Assignment to Classes"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='assignments')
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, related_name='teacher_assignments')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'teacher_assignments'
        unique_together = ['teacher', 'classroom', 'subject', 'academic_year']
    
    def __str__(self):
        return f"{self.teacher} - {self.subject} - {self.classroom}"


# ============================================================================
# ATTENDANCE MODELS
# ============================================================================

class Attendance(models.Model):
    """Daily Student Attendance"""
    STATUS_CHOICES = [
        ('Present', 'Present'),
        ('Absent', 'Absent'),
        ('Late', 'Late'),
        ('Excused', 'Excused'),
        ('Sick', 'Sick'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_records')
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE)
    date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    remarks = models.TextField(blank=True)
    marked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='attendance_marked')
    marked_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'attendance'
        unique_together = ['student', 'date']
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.student.get_full_name()} - {self.date} - {self.status}"


# ============================================================================
# GRADES & ASSESSMENT MODELS
# ============================================================================

class GradingScale(models.Model):
    """Grading Scale Configuration"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    min_score = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    max_score = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    grade = models.CharField(max_length=5)  # A, B+, B, C, etc.
    description = models.CharField(max_length=100)  # Excellent, Good, Fair, etc.
    grade_point = models.DecimalField(max_digits=3, decimal_places=2, blank=True, null=True)
    
    class Meta:
        db_table = 'grading_scales'
        ordering = ['-min_score']
    
    def __str__(self):
        return f"{self.grade} ({self.min_score}-{self.max_score})"


class Assessment(models.Model):
    """Assessments/Exams"""
    ASSESSMENT_TYPE_CHOICES = [
        ('CAT', 'Continuous Assessment Test'),
        ('MID_TERM', 'Mid-Term Exam'),
        ('END_TERM', 'End of Term Exam'),
        ('ASSIGNMENT', 'Assignment'),
        ('PROJECT', 'Project'),
        ('QUIZ', 'Quiz'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    assessment_type = models.CharField(max_length=20, choices=ASSESSMENT_TYPE_CHOICES)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='assessments')
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, related_name='assessments')
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='assessments')
    
    date = models.DateField()
    max_marks = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=100, 
                                 help_text="Percentage weight in final grade")
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'assessments'
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.name} - {self.subject.name} - {self.classroom.name}"


class StudentGrade(models.Model):
    """Individual Student Grades"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='grades')
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='student_grades')
    marks_obtained = models.DecimalField(max_digits=5, decimal_places=2, 
                                        validators=[MinValueValidator(0)])
    grade = models.CharField(max_length=5, blank=True)  # Auto-calculated
    remarks = models.TextField(blank=True)
    
    graded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='grades_assigned')
    graded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'student_grades'
        unique_together = ['student', 'assessment']
    
    def __str__(self):
        return f"{self.student.get_full_name()} - {self.assessment.name} - {self.marks_obtained}/{self.assessment.max_marks}"
    
    def save(self, *args, **kwargs):
        # Auto-calculate grade based on percentage
        if self.marks_obtained is not None and self.assessment.max_marks:
            percentage = (self.marks_obtained / self.assessment.max_marks) * 100
            grading_scale = GradingScale.objects.filter(
                min_score__lte=percentage,
                max_score__gte=percentage
            ).first()
            if grading_scale:
                self.grade = grading_scale.grade
        super().save(*args, **kwargs)


class ReportCard(models.Model):
    """Term Report Cards"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='report_cards')
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE)
    
    overall_average = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    overall_grade = models.CharField(max_length=5, blank=True)
    position_in_class = models.IntegerField(blank=True, null=True)
    
    attendance_days = models.IntegerField(default=0)
    attendance_present = models.IntegerField(default=0)
    
    class_teacher_remarks = models.TextField(blank=True)
    principal_remarks = models.TextField(blank=True)
    
    generated_at = models.DateTimeField(auto_now_add=True)
    published = models.BooleanField(default=False)
    published_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'report_cards'
        unique_together = ['student', 'term']
        ordering = ['-term__start_date']
    
    def __str__(self):
        return f"{self.student.get_full_name()} - {self.term}"


# ============================================================================
# FEES MANAGEMENT MODELS
# ============================================================================

class FeeStructure(models.Model):
    """Fee Structure per Grade Level and Term"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    grade_level = models.ForeignKey(GradeLevel, on_delete=models.CASCADE, related_name='fee_structures')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    
    # Fee Components
    tuition_per_term = models.DecimalField(max_digits=10, decimal_places=2)
    meals_per_term = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    transport_per_term = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Other possible fees
    books_and_materials = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    uniform = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    activities = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'fee_structures'
        unique_together = ['grade_level', 'academic_year']
    
    def __str__(self):
        return f"{self.grade_level.name} - {self.academic_year.name}"
    
    def get_total_per_term(self, include_meals=False, include_transport=False):
        total = self.tuition_per_term + self.books_and_materials + self.uniform + self.activities
        if include_meals:
            total += self.meals_per_term
        if include_transport:
            total += self.transport_per_term
        return total


class FeeInvoice(models.Model):
    """Fee Invoices for Students"""
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Partial', 'Partially Paid'),
        ('Paid', 'Fully Paid'),
        ('Overdue', 'Overdue'),
        ('Cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_number = models.CharField(max_length=50, unique=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fee_invoices')
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    
    # Fee Breakdown
    tuition_amount = models.DecimalField(max_digits=10, decimal_places=2)
    meals_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    transport_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_fees = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=10, decimal_places=2)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    due_date = models.DateField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'fee_invoices'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.invoice_number} - {self.student.get_full_name()}"
    
    def save(self, *args, **kwargs):
        self.balance = self.total_amount - self.amount_paid
        if self.balance <= 0:
            self.status = 'Paid'
        elif self.amount_paid > 0:
            self.status = 'Partial'
        elif timezone.now().date() > self.due_date:
            self.status = 'Overdue'
        super().save(*args, **kwargs)


class FeePayment(models.Model):
    """Fee Payments"""
    PAYMENT_METHOD_CHOICES = [
        ('Cash', 'Cash'),
        ('Bank_Transfer', 'Bank Transfer'),
        ('M-Pesa', 'M-Pesa'),
        ('Cheque', 'Cheque'),
        ('Card', 'Debit/Credit Card'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receipt_number = models.CharField(max_length=50, unique=True)
    invoice = models.ForeignKey(FeeInvoice, on_delete=models.CASCADE, related_name='payments')
    
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    payment_date = models.DateField(default=timezone.now)
    
    # Payment Details
    reference_number = models.CharField(max_length=100, blank=True, help_text="Bank ref, M-Pesa code, etc.")
    remarks = models.TextField(blank=True)
    
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='payments_received')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'fee_payments'
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"{self.receipt_number} - {self.amount}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update invoice amounts
        self.invoice.amount_paid = self.invoice.payments.aggregate(
            total=models.Sum('amount'))['total'] or 0
        self.invoice.save()


# ============================================================================
# EVENTS & ACTIVITIES MODELS
# ============================================================================

class Event(models.Model):
    """School Events"""
    CATEGORY_CHOICES = [
        ('Academic', 'Academic'),
        ('Cultural', 'Cultural'),
        ('Sports', 'Sports'),
        ('Meeting', 'Meeting'),
        ('Entertainment', 'Entertainment'),
        ('Holiday', 'Holiday'),
        ('Other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    location = models.CharField(max_length=200)
    
    image = models.ImageField(upload_to='events/', blank=True, null=True)
    
    # Visibility
    is_public = models.BooleanField(default=True, help_text="Visible on public website")
    target_audience = models.CharField(max_length=100, blank=True, 
                                      help_text="e.g., 'All Students', 'Grade 4-6', 'Parents'")
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'events'
        ordering = ['-date', '-start_time']
    
    def __str__(self):
        return f"{self.title} - {self.date}"


# ============================================================================
# GALLERY & MEDIA MODELS
# ============================================================================

class GalleryImage(models.Model):
    """Gallery Images"""
    CATEGORY_CHOICES = [
        ('Academics', 'Academics'),
        ('Sports', 'Sports'),
        ('Culture', 'Culture'),
        ('Events', 'Events'),
        ('Facilities', 'Facilities'),
        ('Creativity', 'Creativity'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    image = models.ImageField(upload_to='gallery/')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    description = models.TextField(blank=True)
    
    event = models.ForeignKey(Event, on_delete=models.SET_NULL, null=True, blank=True, 
                             related_name='gallery_images')
    
    is_featured = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'gallery_images'
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return self.title


# ============================================================================
# TIMETABLE MODELS
# ============================================================================

class TimeSlot(models.Model):
    """Time Slots for Timetable"""
    DAYS_OF_WEEK = [
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    day_of_week = models.CharField(max_length=10, choices=DAYS_OF_WEEK)
    start_time = models.TimeField()
    end_time = models.TimeField()
    period_number = models.IntegerField()
    is_break = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'time_slots'
        ordering = ['day_of_week', 'start_time']
        unique_together = ['day_of_week', 'period_number']
    
    def __str__(self):
        return f"{self.day_of_week} - Period {self.period_number} ({self.start_time}-{self.end_time})"


class Timetable(models.Model):
    """Class Timetable"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, related_name='timetables')
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, null=True, blank=True)
    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True)
    room_number = models.CharField(max_length=20, blank=True)
    
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'timetables'
        unique_together = ['classroom', 'time_slot', 'academic_year']
    
    def __str__(self):
        return f"{self.classroom} - {self.time_slot} - {self.subject}"


# ============================================================================
# ADMISSIONS MODELS
# ============================================================================

class AdmissionApplication(models.Model):
    """Admission Applications"""
    STATUS_CHOICES = [
        ('Pending', 'Pending Review'),
        ('Under_Review', 'Under Review'),
        ('Assessment_Scheduled', 'Assessment Scheduled'),
        ('Accepted', 'Accepted'),
        ('Rejected', 'Rejected'),
        ('Waitlisted', 'Waitlisted'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application_number = models.CharField(max_length=50, unique=True)
    
    # Student Details
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=Student.GENDER_CHOICES)
    
    # Desired Grade
    desired_grade_level = models.ForeignKey(GradeLevel, on_delete=models.CASCADE)
    desired_academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    
    # Parent/Guardian Information
    parent_name = models.CharField(max_length=200)
    parent_email = models.EmailField()
    parent_phone = models.CharField(max_length=20)
    parent_address = models.TextField()
    
    # Previous School (if applicable)
    previous_school = models.CharField(max_length=200, blank=True)
    
    # Documents
    birth_certificate = models.FileField(upload_to='applications/birth_certs/', blank=True, null=True)
    passport_photos = models.ImageField(upload_to='applications/photos/', blank=True, null=True)
    previous_report = models.FileField(upload_to='applications/reports/', blank=True, null=True)
    leaving_certificate = models.FileField(upload_to='applications/leaving_certs/', blank=True, null=True)
    medical_form = models.FileField(upload_to='applications/medical/', blank=True, null=True)
    
    # Application Status
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='Pending')
    assessment_date = models.DateField(blank=True, null=True)
    assessment_score = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    
    # Admin Notes
    reviewer_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='applications_reviewed')
    
    # Conversion to Student
    converted_to_student = models.OneToOneField(Student, on_delete=models.SET_NULL, 
                                                null=True, blank=True, related_name='application')
    
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'admission_applications'
        ordering = ['-submitted_at']
    
    def __str__(self):
        return f"{self.application_number} - {self.first_name} {self.last_name}"


# ============================================================================
# MESSAGING & COMMUNICATION MODELS
# ============================================================================

class Message(models.Model):
    """Messages between Teachers, Parents, and Admins"""
    MESSAGE_TYPE_CHOICES = [
        ('General', 'General'),
        ('Academic', 'Academic'),
        ('Disciplinary', 'Disciplinary'),
        ('Fees', 'Fees'),
        ('Attendance', 'Attendance'),
        ('Other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject = models.CharField(max_length=200)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, default='General')
    body = models.TextField()
    
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    
    # Optional: Link to student context
    student = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='related_messages')
    
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)
    
    sent_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'messages'
        ordering = ['-sent_at']
    
    def __str__(self):
        return f"{self.sender} to {self.recipient}: {self.subject}"


class Announcement(models.Model):
    """School-wide Announcements"""
    TARGET_CHOICES = [
        ('All', 'Everyone'),
        ('Parents', 'Parents Only'),
        ('Teachers', 'Teachers Only'),
        ('Students', 'Students Only'),
        ('Grade_Specific', 'Specific Grade Level'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    content = models.TextField()
    target_audience = models.CharField(max_length=20, choices=TARGET_CHOICES, default='All')
    grade_level = models.ForeignKey(GradeLevel, on_delete=models.SET_NULL, null=True, blank=True,
                                   help_text="Only if target is Grade_Specific")
    
    is_urgent = models.BooleanField(default=False)
    publish_date = models.DateTimeField(default=timezone.now)
    expiry_date = models.DateTimeField(blank=True, null=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'announcements'
        ordering = ['-publish_date']
    
    def __str__(self):
        return self.title


# ============================================================================
# STATISTICS & SETTINGS MODELS
# ============================================================================

class SchoolSettings(models.Model):
    """School Configuration and Settings"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school_name = models.CharField(max_length=200, default="JOKS School Connect")
    school_motto = models.CharField(max_length=200, blank=True)
    school_email = models.EmailField()
    school_phone = models.CharField(max_length=20)
    school_address = models.TextField()
    
    # Social Media
    facebook_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)
    
    # Bank Details for Fees
    bank_name = models.CharField(max_length=100, blank=True)
    account_name = models.CharField(max_length=200, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    mpesa_paybill = models.CharField(max_length=20, blank=True)
    
    # Academic Settings
    student_teacher_ratio = models.CharField(max_length=20, default="1:15")
    total_students_display = models.IntegerField(default=400)
    total_teachers_display = models.IntegerField(default=20)
    years_of_excellence = models.IntegerField(default=10)
    awards_won = models.IntegerField(default=10)
    
    # Admissions
    admissions_open = models.BooleanField(default=True)
    
    logo = models.ImageField(upload_to='school/', blank=True, null=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'school_settings'
        verbose_name = 'School Settings'
        verbose_name_plural = 'School Settings'
    
    def __str__(self):
        return self.school_name


# ============================================================================
# AUDIT LOG MODEL
# ============================================================================

class AuditLog(models.Model):
    """Audit Trail for Important Actions"""
    ACTION_CHOICES = [
        ('CREATE', 'Created'),
        ('UPDATE', 'Updated'),
        ('DELETE', 'Deleted'),
        ('LOGIN', 'Logged In'),
        ('LOGOUT', 'Logged Out'),
        ('PAYMENT', 'Payment Received'),
        ('GRADE', 'Grade Assigned'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'audit_logs'
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.user} - {self.action} - {self.model_name} - {self.timestamp}"