from django.shortcuts import render

# Create your views here.
# views.py
# JOKS School Connect - Complete Function-Based Views
# No Class-Based Views, No Django Forms, Manual Form Handling

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import uuid

from .models import (
    User, Student, Parent, Teacher, ClassRoom, Subject, GradeLevel,
    AcademicYear, Term, Attendance, Grade, Assignment, SubmittedAssignment,
    Event, Gallery, FeeStructure, FeePayment, AdmissionApplication,
    Message, Announcement, SchoolSettings, AuditLog, Timetable,
    ProgressReport, Behavior
)
from .helpers import (
    get_client_ip, log_audit, send_notification_email,
    calculate_age, generate_admission_number, validate_file_upload,
    get_current_academic_year, get_current_term, is_admin, is_teacher, 
    is_parent, get_user_context
)


# ============================================================================
# AUTHENTICATION VIEWS
# ============================================================================

def signin_view(request):
    """User Sign In"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        
        if not email or not password:
            messages.error(request, 'Please provide both email and password')
            return render(request, 'signin.html')
        
        # Authenticate user
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            if user.is_active:
                login(request, user)
                log_audit(user, 'LOGIN', 'User', str(user.id), 
                         f'User {user.email} logged in', get_client_ip(request))
                messages.success(request, f'Welcome back, {user.get_full_name()}!')
                
                # Redirect based on role
                if user.role == 'Admin':
                    return redirect('admin_dashboard')
                elif user.role == 'Teacher':
                    return redirect('teacher_dashboard')
                else:
                    return redirect('parent_dashboard')
            else:
                messages.error(request, 'Your account has been deactivated')
        else:
            messages.error(request, 'Invalid email or password')
    
    return render(request, 'signin.html')


def signup_view(request):
    """User Sign Up (Parent Registration Only)"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        # Extract form data
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '').strip()
        password2 = request.POST.get('password2', '').strip()
        address = request.POST.get('address', '').strip()
        
        # Validation
        errors = []
        if not all([first_name, last_name, email, phone, password, password2]):
            errors.append('All fields are required')
        
        if password != password2:
            errors.append('Passwords do not match')
        
        if len(password) < 8:
            errors.append('Password must be at least 8 characters')
        
        if User.objects.filter(email=email).exists():
            errors.append('Email already registered')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'signup.html', {
                'form_data': request.POST
            })
        
        # Create user
        try:
            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                address=address,
                role='Parent'
            )
            
            # Create Parent profile
            Parent.objects.create(
                user=user,
                phone=phone,
                address=address
            )
            
            log_audit(user, 'CREATE', 'User', str(user.id), 
                     f'New parent registered: {user.email}', get_client_ip(request))
            
            messages.success(request, 'Account created successfully! Please log in.')
            return redirect('signin')
            
        except Exception as e:
            messages.error(request, f'Error creating account: {str(e)}')
    
    return render(request, 'signup.html')


def signout_view(request):
    """User Sign Out"""
    if request.user.is_authenticated:
        log_audit(request.user, 'LOGOUT', 'User', str(request.user.id), 
                 f'User {request.user.email} logged out', get_client_ip(request))
        logout(request)
        messages.success(request, 'You have been logged out successfully')
    return redirect('home')


# ============================================================================
# PUBLIC VIEWS
# ============================================================================

def home_view(request):
    """Homepage"""
    settings = SchoolSettings.objects.first()
    recent_events = Event.objects.filter(
        date__gte=timezone.now().date()
    ).order_by('date')[:3]
    
    recent_gallery = Gallery.objects.filter(
        is_featured=True
    ).order_by('-created_at')[:6]
    
    announcements = Announcement.objects.filter(
        target_audience__in=['All', 'Parents'],
        publish_date__lte=timezone.now()
    ).filter(
        Q(expiry_date__isnull=True) | Q(expiry_date__gte=timezone.now())
    ).order_by('-publish_date')[:3]
    
    context = {
        'settings': settings,
        'recent_events': recent_events,
        'gallery_items': recent_gallery,
        'announcements': announcements,
    }
    return render(request, 'home.html', context)


def about_view(request):
    """About Us Page"""
    settings = SchoolSettings.objects.first()
    context = {'settings': settings}
    return render(request, 'about.html', context)


def admissions_info_view(request):
    """Admissions Information"""
    settings = SchoolSettings.objects.first()
    grade_levels = GradeLevel.objects.all().order_by('order')
    current_year = get_current_academic_year()
    
    context = {
        'settings': settings,
        'grade_levels': grade_levels,
        'current_year': current_year,
        'admissions_open': settings.admissions_open if settings else True
    }
    return render(request, 'admissions_info.html', context)


def fees_structure_view(request):
    """Fees Structure"""
    current_year = get_current_academic_year()
    fee_structures = FeeStructure.objects.filter(
        academic_year=current_year,
        is_active=True
    ).select_related('grade_level').order_by('grade_level__order')
    
    context = {
        'fee_structures': fee_structures,
        'current_year': current_year
    }
    return render(request, 'fees_structure.html', context)


def events_view(request):
    """Events Calendar"""
    upcoming_events = Event.objects.filter(
        date__gte=timezone.now().date()
    ).order_by('date')
    
    past_events = Event.objects.filter(
        date__lt=timezone.now().date()
    ).order_by('-date')[:10]
    
    context = {
        'upcoming_events': upcoming_events,
        'past_events': past_events
    }
    return render(request, 'events.html', context)


def gallery_view(request):
    """Photo Gallery"""
    gallery_items = Gallery.objects.all().order_by('-created_at')
    
    # Filter by category if provided
    category = request.GET.get('category')
    if category:
        gallery_items = gallery_items.filter(category=category)
    
    context = {
        'gallery_items': gallery_items,
        'categories': Gallery.CATEGORY_CHOICES,
        'selected_category': category
    }
    return render(request, 'gallery.html', context)


def contact_view(request):
    """Contact Page"""
    settings = SchoolSettings.objects.first()
    
    if request.method == 'POST':
        # Handle contact form submission
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message_body = request.POST.get('message', '').strip()
        
        if all([name, email, subject, message_body]):
            # Send email notification to admin
            try:
                admin_users = User.objects.filter(role='Admin', is_active=True)
                for admin in admin_users:
                    send_notification_email(
                        admin.email,
                        f'Contact Form: {subject}',
                        f'From: {name} ({email})\n\n{message_body}'
                    )
                messages.success(request, 'Thank you! Your message has been sent.')
            except Exception as e:
                messages.error(request, 'Error sending message. Please try again.')
        else:
            messages.error(request, 'Please fill in all fields')
    
    context = {'settings': settings}
    return render(request, 'contact.html', context)


# ============================================================================
# ADMISSION APPLICATION VIEWS
# ============================================================================

def apply_admission_view(request):
    """Public Admission Application Form"""
    grade_levels = GradeLevel.objects.all().order_by('order')
    academic_years = AcademicYear.objects.filter(
        end_date__gte=timezone.now().date()
    ).order_by('start_date')
    
    if request.method == 'POST':
        # Extract form data
        data = {
            'first_name': request.POST.get('first_name', '').strip(),
            'last_name': request.POST.get('last_name', '').strip(),
            'middle_name': request.POST.get('middle_name', '').strip(),
            'date_of_birth': request.POST.get('date_of_birth'),
            'gender': request.POST.get('gender'),
            'desired_grade_level_id': request.POST.get('grade_level'),
            'desired_academic_year_id': request.POST.get('academic_year'),
            'parent_name': request.POST.get('parent_name', '').strip(),
            'parent_email': request.POST.get('parent_email', '').strip(),
            'parent_phone': request.POST.get('parent_phone', '').strip(),
            'parent_address': request.POST.get('parent_address', '').strip(),
            'previous_school': request.POST.get('previous_school', '').strip(),
        }
        
        # File uploads
        files = {
            'birth_certificate': request.FILES.get('birth_certificate'),
            'passport_photos': request.FILES.get('passport_photos'),
            'previous_report': request.FILES.get('previous_report'),
        }
        
        # Validation
        errors = []
        required_fields = ['first_name', 'last_name', 'date_of_birth', 'gender',
                          'desired_grade_level_id', 'desired_academic_year_id',
                          'parent_name', 'parent_email', 'parent_phone', 'parent_address']
        
        for field in required_fields:
            if not data.get(field):
                errors.append(f'{field.replace("_", " ").title()} is required')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'apply_admission.html', {
                'grade_levels': grade_levels,
                'academic_years': academic_years,
                'form_data': data
            })
        
        try:
            # Create application
            application = AdmissionApplication.objects.create(
                application_number=f"APP{timezone.now().year}{AdmissionApplication.objects.count() + 1:04d}",
                first_name=data['first_name'],
                last_name=data['last_name'],
                middle_name=data['middle_name'],
                date_of_birth=data['date_of_birth'],
                gender=data['gender'],
                desired_grade_level_id=data['desired_grade_level_id'],
                desired_academic_year_id=data['desired_academic_year_id'],
                parent_name=data['parent_name'],
                parent_email=data['parent_email'],
                parent_phone=data['parent_phone'],
                parent_address=data['parent_address'],
                previous_school=data['previous_school'],
                birth_certificate=files['birth_certificate'],
                passport_photos=files['passport_photos'],
                previous_report=files['previous_report'],
                status='Pending'
            )
            
            # Send confirmation email
            try:
                send_notification_email(
                    data['parent_email'],
                    'Application Received',
                    f'Dear {data["parent_name"]},\n\nYour application for {data["first_name"]} {data["last_name"]} has been received. Application Number: {application.application_number}\n\nWe will contact you soon.'
                )
            except:
                pass
            
            messages.success(request, f'Application submitted successfully! Application Number: {application.application_number}')
            return redirect('home')
            
        except Exception as e:
            messages.error(request, f'Error submitting application: {str(e)}')
    
    context = {
        'grade_levels': grade_levels,
        'academic_years': academic_years
    }
    return render(request, 'apply_admission.html', context)


@login_required
@user_passes_test(is_admin)
def applications_list_view(request):
    """Admin: List all applications"""
    status = request.GET.get('status', 'all')
    
    applications = AdmissionApplication.objects.all()
    if status != 'all':
        applications = applications.filter(status=status)
    
    applications = applications.order_by('-submitted_at')
    
    context = {
        'applications': applications,
        'selected_status': status,
        'status_choices': AdmissionApplication.STATUS_CHOICES
    }
    return render(request, 'admin/applications_list.html', context)


@login_required
@user_passes_test(is_admin)
def application_detail_view(request, application_id):
    """Admin: View application details"""
    application = get_object_or_404(AdmissionApplication, id=application_id)
    
    context = {'application': application}
    return render(request, 'admin/application_detail.html', context)


@login_required
@user_passes_test(is_admin)
def application_update_status_view(request, application_id):
    """Admin: Update application status"""
    application = get_object_or_404(AdmissionApplication, id=application_id)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        notes = request.POST.get('notes', '').strip()
        
        if new_status in dict(AdmissionApplication.STATUS_CHOICES):
            application.status = new_status
            application.reviewer_notes = notes
            application.reviewed_by = request.user
            application.save()
            
            log_audit(request.user, 'UPDATE', 'AdmissionApplication', 
                     str(application.id), f'Status changed to {new_status}', 
                     get_client_ip(request))
            
            # Send email notification
            try:
                send_notification_email(
                    application.parent_email,
                    f'Application Status Update - {application.application_number}',
                    f'Dear {application.parent_name},\n\nYour application status has been updated to: {new_status}\n\n{notes}'
                )
            except:
                pass
            
            messages.success(request, 'Application status updated successfully')
            
            # If approved, redirect to convert to student
            if new_status == 'Approved':
                return redirect('application_convert_student', application_id=application.id)
        else:
            messages.error(request, 'Invalid status')
    
    return redirect('application_detail', application_id=application.id)


@login_required
@user_passes_test(is_admin)
def application_convert_student_view(request, application_id):
    """Admin: Convert approved application to student"""
    application = get_object_or_404(AdmissionApplication, id=application_id)
    
    if application.status != 'Approved':
        messages.error(request, 'Only approved applications can be converted')
        return redirect('application_detail', application_id=application.id)
    
    if application.converted_to_student:
        messages.warning(request, 'This application has already been converted')
        return redirect('student_detail', student_id=application.converted_to_student.id)
    
    classrooms = ClassRoom.objects.filter(
        grade_level=application.desired_grade_level,
        academic_year=application.desired_academic_year
    )
    
    if request.method == 'POST':
        classroom_id = request.POST.get('classroom')
        
        if not classroom_id:
            messages.error(request, 'Please select a classroom')
            return render(request, 'admin/application_convert.html', {
                'application': application,
                'classrooms': classrooms
            })
        
        try:
            classroom = ClassRoom.objects.get(id=classroom_id)
            
            # Generate admission number
            admission_number = generate_admission_number()
            
            # Create student
            student = Student.objects.create(
                admission_number=admission_number,
                first_name=application.first_name,
                last_name=application.last_name,
                middle_name=application.middle_name,
                date_of_birth=application.date_of_birth,
                gender=application.gender,
                current_class=classroom,
                emergency_contact=application.parent_phone,
                emergency_contact_name=application.parent_name,
                emergency_contact_relationship='Parent',
                passport_photo=application.passport_photos,
                birth_certificate=application.birth_certificate,
                admission_date=timezone.now().date(),
                is_active=True
            )
            
            # Link application to student
            application.converted_to_student = student
            application.save()
            
            # Create or link parent
            parent_user = User.objects.filter(email=application.parent_email).first()
            if not parent_user:
                # Create new parent user
                parent_user = User.objects.create_user(
                    username=application.parent_email,
                    email=application.parent_email,
                    password=User.objects.make_random_password(),
                    first_name=application.parent_name.split()[0],
                    last_name=' '.join(application.parent_name.split()[1:]),
                    phone=application.parent_phone,
                    address=application.parent_address,
                    role='Parent'
                )
                
                # Create parent profile
                parent = Parent.objects.create(
                    user=parent_user,
                    phone=application.parent_phone,
                    address=application.parent_address
                )
            else:
                parent = parent_user.parent_profile
            
            # Link student to parent
            student.parents.add(parent)
            
            log_audit(request.user, 'CREATE', 'Student', str(student.id),
                     f'Student created from application {application.application_number}',
                     get_client_ip(request))
            
            # Send welcome email with credentials
            try:
                send_notification_email(
                    application.parent_email,
                    'Welcome to JOKS School',
                    f'Dear {application.parent_name},\n\nCongratulations! {application.first_name} has been enrolled.\n\nAdmission Number: {admission_number}\nClass: {classroom.name}\n\nPlease log in to the parent portal to access more information.'
                )
            except:
                pass
            
            messages.success(request, f'Student created successfully! Admission Number: {admission_number}')
            return redirect('student_detail', student_id=student.id)
            
        except Exception as e:
            messages.error(request, f'Error creating student: {str(e)}')
    
    context = {
        'application': application,
        'classrooms': classrooms
    }
    return render(request, 'admin/application_convert.html', context)


# ============================================================================
# STUDENT VIEWS
# ============================================================================

@login_required
@user_passes_test(lambda u: is_admin(u) or is_teacher(u))
def students_list_view(request):
    """List all students"""
    grade_filter = request.GET.get('grade')
    class_filter = request.GET.get('class')
    search = request.GET.get('search', '').strip()
    
    students = Student.objects.filter(is_active=True).select_related('current_class', 'current_class__grade_level')
    
    if grade_filter:
        students = students.filter(current_class__grade_level__id=grade_filter)
    
    if class_filter:
        students = students.filter(current_class__id=class_filter)
    
    if search:
        students = students.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(admission_number__icontains=search)
        )
    
    students = students.order_by('current_class__grade_level__order', 'last_name', 'first_name')
    
    grade_levels = GradeLevel.objects.all()
    classrooms = ClassRoom.objects.filter(academic_year=get_current_academic_year())
    
    context = {
        'students': students,
        'grade_levels': grade_levels,
        'classrooms': classrooms,
        'selected_grade': grade_filter,
        'selected_class': class_filter,
        'search_query': search
    }
    return render(request, 'students/students_list.html', context)


@login_required
def student_detail_view(request, student_id):
    """View student details"""
    student = get_object_or_404(Student, id=student_id)
    
    # Permission check
    if request.user.role == 'Parent':
        if not student.parents.filter(user=request.user).exists():
            return HttpResponseForbidden('You do not have permission to view this student')
    
    # Get additional information
    recent_attendance = Attendance.objects.filter(student=student).order_by('-date')[:10]
    recent_grades = Grade.objects.filter(student=student).order_by('-date_recorded')[:10]
    recent_behaviors = Behavior.objects.filter(student=student).order_by('-date')[:5]
    
    # Fee payments
    current_year = get_current_academic_year()
    fee_payments = FeePayment.objects.filter(
        student=student,
        fee_structure__academic_year=current_year
    ).order_by('-payment_date')
    
    context = {
        'student': student,
        'recent_attendance': recent_attendance,
        'recent_grades': recent_grades,
        'recent_behaviors': recent_behaviors,
        'fee_payments': fee_payments
    }
    return render(request, 'students/student_detail.html', context)


@login_required
@user_passes_test(is_admin)
def student_add_view(request):
    """Add new student"""
    if request.method == 'POST':
        # Extract form data
        data = {
            'first_name': request.POST.get('first_name', '').strip(),
            'last_name': request.POST.get('last_name', '').strip(),
            'middle_name': request.POST.get('middle_name', '').strip(),
            'date_of_birth': request.POST.get('date_of_birth'),
            'gender': request.POST.get('gender'),
            'blood_group': request.POST.get('blood_group', ''),
            'current_class_id': request.POST.get('current_class'),
            'emergency_contact': request.POST.get('emergency_contact', '').strip(),
            'emergency_contact_name': request.POST.get('emergency_contact_name', '').strip(),
            'emergency_contact_relationship': request.POST.get('emergency_contact_relationship', '').strip(),
            'medical_conditions': request.POST.get('medical_conditions', '').strip(),
        }
        
        # Validation
        errors = []
        required_fields = ['first_name', 'last_name', 'date_of_birth', 'gender',
                          'current_class_id', 'emergency_contact', 'emergency_contact_name',
                          'emergency_contact_relationship']
        
        for field in required_fields:
            if not data.get(field):
                errors.append(f'{field.replace("_", " ").title()} is required')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                # Generate admission number
                admission_number = generate_admission_number()
                
                # Create student
                student = Student.objects.create(
                    admission_number=admission_number,
                    first_name=data['first_name'],
                    last_name=data['last_name'],
                    middle_name=data['middle_name'],
                    date_of_birth=data['date_of_birth'],
                    gender=data['gender'],
                    blood_group=data['blood_group'],
                    current_class_id=data['current_class_id'],
                    emergency_contact=data['emergency_contact'],
                    emergency_contact_name=data['emergency_contact_name'],
                    emergency_contact_relationship=data['emergency_contact_relationship'],
                    medical_conditions=data['medical_conditions'],
                    passport_photo=request.FILES.get('passport_photo'),
                    birth_certificate=request.FILES.get('birth_certificate'),
                    admission_date=timezone.now().date(),
                    is_active=True
                )
                
                log_audit(request.user, 'CREATE', 'Student', str(student.id),
                         f'Student {student.admission_number} created', get_client_ip(request))
                
                messages.success(request, f'Student added successfully! Admission Number: {admission_number}')
                return redirect('student_detail', student_id=student.id)
                
            except Exception as e:
                messages.error(request, f'Error creating student: {str(e)}')
    
    classrooms = ClassRoom.objects.filter(academic_year=get_current_academic_year())
    context = {
        'classrooms': classrooms,
        'blood_groups': Student.BLOOD_GROUP_CHOICES,
        'genders': Student.GENDER_CHOICES
    }
    return render(request, 'students/student_add.html', context)


@login_required
@user_passes_test(lambda u: is_admin(u) or is_teacher(u))
def student_edit_view(request, student_id):
    """Edit student information"""
    student = get_object_or_404(Student, id=student_id)
    
    if request.method == 'POST':
        # Update student fields
        student.first_name = request.POST.get('first_name', '').strip()
        student.last_name = request.POST.get('last_name', '').strip()
        student.middle_name = request.POST.get('middle_name', '').strip()
        student.date_of_birth = request.POST.get('date_of_birth')
        student.gender = request.POST.get('gender')
        student.blood_group = request.POST.get('blood_group', '')
        student.emergency_contact = request.POST.get('emergency_contact', '').strip()
        student.emergency_contact_name = request.POST.get('emergency_contact_name', '').strip()
        student.emergency_contact_relationship = request.POST.get('emergency_contact_relationship', '').strip()
        student.medical_conditions = request.POST.get('medical_conditions', '').strip()
        
        # Only admin can change class
        if is_admin(request.user):
            class_id = request.POST.get('current_class')
            if class_id:
                student.current_class_id = class_id
        
        # Handle file uploads
        if 'passport_photo' in request.FILES:
            student.passport_photo = request.FILES['passport_photo']
        if 'birth_certificate' in request.FILES:
            student.birth_certificate = request.FILES['birth_certificate']
        
        try:
            student.save()
            log_audit(request.user, 'UPDATE', 'Student', str(student.id),
                     f'Student {student.admission_number} updated', get_client_ip(request))
            messages.success(request, 'Student information updated successfully')
            return redirect('student_detail', student_id=student.id)
        except Exception as e:
            messages.error(request, f'Error updating student: {str(e)}')
    
    classrooms = ClassRoom.objects.filter(academic_year=get_current_academic_year())
    context = {
        'student': student,
        'classrooms': classrooms,
        'blood_groups': Student.BLOOD_GROUP_CHOICES,
        'genders': Student.GENDER_CHOICES
    }
    return render(request, 'students/student_edit.html', context)


@login_required
@user_passes_test(is_admin)
def student_deactivate_view(request, student_id):
    """Deactivate student"""
    student = get_object_or_404(Student, id=student_id)
    
    if request.method == 'POST':
        student.is_active = False
        student.save()
        
        log_audit(request.user, 'UPDATE', 'Student', str(student.id),
                 f'Student {student.admission_number} deactivated', get_client_ip(request))
        
        messages.success(request, 'Student deactivated successfully')
        return redirect('students_list')
    
    context = {'student': student}
    return render(request, 'students/student_deactivate.html', context)


@login_required
@user_passes_test(is_admin)
def student_activate_view(request, student_id):
    """Activate student"""
    student = get_object_or_404(Student, id=student_id)
    
    student.is_active = True
    student.save()
    
    log_audit(request.user, 'UPDATE', 'Student', str(student.id),
             f'Student {student.admission_number} activated', get_client_ip(request))
    
    messages.success(request, 'Student activated successfully')
    return redirect('student_detail', student_id=student.id)


# ============================================================================
# TEACHER VIEWS
# ============================================================================

@login_required
@user_passes_test(is_admin)
def teachers_list_view(request):
    """List all teachers"""
    teachers = Teacher.objects.select_related('user').filter(user__is_active=True)
    
    context = {'teachers': teachers}
    return render(request, 'teachers/teachers_list.html', context)


@login_required
@user_passes_test(is_admin)
def teacher_detail_view(request, teacher_id):
    """View teacher details"""
    teacher = get_object_or_404(Teacher, id=teacher_id)
    
    # Get classes taught
    classes = ClassRoom.objects.filter(class_teacher=teacher.user)
    subjects_taught = teacher.subjects_taught.all()
    
    context = {
        'teacher': teacher,
        'classes': classes,
        'subjects_taught': subjects_taught
    }
    return render(request, 'teachers/teacher_detail.html', context)


@login_required
@user_passes_test(is_admin)
def teacher_add_view(request):
    """Add new teacher"""
    if request.method == 'POST':
        # Extract form data
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        date_of_birth = request.POST.get('date_of_birth')
        address = request.POST.get('address', '').strip()
        qualification = request.POST.get('qualification', '').strip()
        specialization = request.POST.get('specialization', '').strip()
        join_date = request.POST.get('join_date')
        subject_ids = request.POST.getlist('subjects')
        
        # Validation
        errors = []
        if not all([first_name, last_name, email, phone, join_date]):
            errors.append('Please fill in all required fields')
        
        if User.objects.filter(email=email).exists():
            errors.append('Email already exists')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                # Create user
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=User.objects.make_random_password(),
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                    date_of_birth=date_of_birth,
                    address=address,
                    role='Teacher'
                )
                
                # Create teacher profile
                teacher = Teacher.objects.create(
                    user=user,
                    employee_id=f"TCH{timezone.now().year}{Teacher.objects.count() + 1:04d}",
                    phone=phone,
                    address=address,
                    qualification=qualification,
                    specialization=specialization,
                    join_date=join_date
                )
                
                # Add subjects
                if subject_ids:
                    teacher.subjects_taught.set(subject_ids)
                
                log_audit(request.user, 'CREATE', 'Teacher', str(teacher.id),
                         f'Teacher {teacher.employee_id} created', get_client_ip(request))
                
                messages.success(request, 'Teacher added successfully')
                return redirect('teacher_detail', teacher_id=teacher.id)
                
            except Exception as e:
                messages.error(request, f'Error creating teacher: {str(e)}')
    
    subjects = Subject.objects.filter(is_active=True)
    context = {'subjects': subjects}
    return render(request, 'teachers/teacher_add.html', context)


@login_required
@user_passes_test(is_admin)
def teacher_edit_view(request, teacher_id):
    """Edit teacher information"""
    teacher = get_object_or_404(Teacher, id=teacher_id)
    
    if request.method == 'POST':
        # Update user fields
        teacher.user.first_name = request.POST.get('first_name', '').strip()
        teacher.user.last_name = request.POST.get('last_name', '').strip()
        teacher.user.phone = request.POST.get('phone', '').strip()
        teacher.user.date_of_birth = request.POST.get('date_of_birth')
        teacher.user.address = request.POST.get('address', '').strip()
        teacher.user.save()
        
        # Update teacher fields
        teacher.phone = request.POST.get('phone', '').strip()
        teacher.address = request.POST.get('address', '').strip()
        teacher.qualification = request.POST.get('qualification', '').strip()
        teacher.specialization = request.POST.get('specialization', '').strip()
        teacher.join_date = request.POST.get('join_date')
        
        # Update subjects
        subject_ids = request.POST.getlist('subjects')
        if subject_ids:
            teacher.subjects_taught.set(subject_ids)
        
        try:
            teacher.save()
            log_audit(request.user, 'UPDATE', 'Teacher', str(teacher.id),
                     f'Teacher {teacher.employee_id} updated', get_client_ip(request))
            messages.success(request, 'Teacher information updated successfully')
            return redirect('teacher_detail', teacher_id=teacher.id)
        except Exception as e:
            messages.error(request, f'Error updating teacher: {str(e)}')
    
    subjects = Subject.objects.filter(is_active=True)
    context = {
        'teacher': teacher,
        'subjects': subjects
    }
    return render(request, 'teachers/teacher_edit.html', context)


@login_required
@user_passes_test(is_admin)
def teacher_deactivate_view(request, teacher_id):
    """Deactivate teacher"""
    teacher = get_object_or_404(Teacher, id=teacher_id)
    
    if request.method == 'POST':
        teacher.user.is_active = False
        teacher.user.save()
        
        log_audit(request.user, 'UPDATE', 'Teacher', str(teacher.id),
                 f'Teacher {teacher.employee_id} deactivated', get_client_ip(request))
        
        messages.success(request, 'Teacher deactivated successfully')
        return redirect('teachers_list')
    
    context = {'teacher': teacher}
    return render(request, 'teachers/teacher_deactivate.html', context)


@login_required
@user_passes_test(is_admin)
def teacher_activate_view(request, teacher_id):
    """Activate teacher"""
    teacher = get_object_or_404(Teacher, id=teacher_id)
    
    teacher.user.is_active = True
    teacher.user.save()
    
    log_audit(request.user, 'UPDATE', 'Teacher', str(teacher.id),
             f'Teacher {teacher.employee_id} activated', get_client_ip(request))
    
    messages.success(request, 'Teacher activated successfully')
    return redirect('teacher_detail', teacher_id=teacher.id)


# Continuing in next file...