# helpers.py
# JOKS School Connect - Helper Functions

from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import datetime, date
import re


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def log_audit(user, action, model_name, object_id, description, ip_address=None):
    """Log audit trail"""
    from .models import AuditLog
    
    try:
        AuditLog.objects.create(
            user=user,
            action=action,
            model_name=model_name,
            object_id=object_id,
            description=description,
            ip_address=ip_address
        )
    except Exception as e:
        print(f"Error logging audit: {str(e)}")


def send_notification_email(recipient_email, subject, message):
    """Send notification email"""
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [recipient_email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False


def calculate_age(birth_date):
    """Calculate age from birth date"""
    if not birth_date:
        return None
    
    today = date.today()
    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    return age


def generate_admission_number():
    """Generate unique admission number"""
    from .models import Student
    
    year = timezone.now().year
    count = Student.objects.filter(
        admission_number__startswith=str(year)
    ).count() + 1
    
    return f"{year}{count:05d}"


def generate_employee_id(prefix='EMP'):
    """Generate unique employee ID"""
    from .models import Teacher
    
    year = timezone.now().year
    count = Teacher.objects.filter(
        employee_id__startswith=f"{prefix}{year}"
    ).count() + 1
    
    return f"{prefix}{year}{count:04d}"


def validate_file_upload(file, allowed_extensions=None, max_size_mb=5):
    """Validate uploaded file"""
    if not file:
        return True, None
    
    # Check file size
    max_size = max_size_mb * 1024 * 1024  # Convert to bytes
    if file.size > max_size:
        return False, f"File size must be less than {max_size_mb}MB"
    
    # Check extension
    if allowed_extensions:
        ext = file.name.split('.')[-1].lower()
        if ext not in allowed_extensions:
            return False, f"File type must be one of: {', '.join(allowed_extensions)}"
    
    return True, None


def get_current_academic_year():
    """Get current academic year"""
    from .models import AcademicYear
    
    current_year = AcademicYear.objects.filter(is_current=True).first()
    if not current_year:
        # Fallback to most recent year
        current_year = AcademicYear.objects.order_by('-start_date').first()
    
    return current_year


def get_current_term():
    """Get current term"""
    from .models import Term
    
    current_term = Term.objects.filter(is_current=True).first()
    if not current_term:
        # Fallback to most recent term
        current_term = Term.objects.order_by('-start_date').first()
    
    return current_term


def is_admin(user):
    """Check if user is admin"""
    return user.is_authenticated and user.role == 'Admin'


def is_teacher(user):
    """Check if user is teacher"""
    return user.is_authenticated and user.role == 'Teacher'


def is_parent(user):
    """Check if user is parent"""
    return user.is_authenticated and user.role == 'Parent'


def get_user_context(user):
    """Get user-specific context data"""
    context = {
        'user': user,
        'is_admin': is_admin(user),
        'is_teacher': is_teacher(user),
        'is_parent': is_parent(user)
    }
    
    if is_teacher(user):
        from .models import Teacher
        try:
            teacher = Teacher.objects.get(user=user)
            context['teacher_profile'] = teacher
        except Teacher.DoesNotExist:
            pass
    
    if is_parent(user):
        from .models import Parent, Student
        try:
            parent = Parent.objects.get(user=user)
            context['parent_profile'] = parent
            context['children'] = Student.objects.filter(parents=parent, is_active=True)
        except Parent.DoesNotExist:
            pass
    
    return context


def format_currency(amount):
    """Format amount as currency"""
    if amount is None:
        return "UGX 0"
    return f"UGX {amount:,.0f}"


def calculate_fee_balance(student, academic_year):
    """Calculate student's fee balance"""
    from .models import FeeStructure, FeePayment
    from decimal import Decimal
    
    # Get fee structure for student's grade
    fee_structure = FeeStructure.objects.filter(
        grade_level=student.current_class.grade_level,
        academic_year=academic_year,
        is_active=True
    ).first()
    
    if not fee_structure:
        return Decimal('0.00')
    
    # Calculate total required
    total_required = fee_structure.total_amount
    
    # Calculate total paid
    total_paid = FeePayment.objects.filter(
        student=student,
        fee_structure__academic_year=academic_year,
        status='Confirmed'
    ).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    # Calculate balance
    balance = total_required - total_paid
    
    return balance


def get_attendance_percentage(student, term=None):
    """Calculate student's attendance percentage"""
    from .models import Attendance
    from django.db.models import Count, Q
    
    query = Attendance.objects.filter(student=student)
    
    if term:
        query = query.filter(
            date__gte=term.start_date,
            date__lte=term.end_date
        )
    
    total = query.count()
    if total == 0:
        return 0.0
    
    present = query.filter(status='Present').count()
    
    percentage = (present / total) * 100
    return round(percentage, 2)


def calculate_grade_average(student, term=None, subject=None):
    """Calculate student's grade average"""
    from .models import Grade
    from django.db.models import Avg
    
    query = Grade.objects.filter(student=student)
    
    if term:
        query = query.filter(term=term)
    
    if subject:
        query = query.filter(subject=subject)
    
    avg = query.aggregate(average=Avg('marks'))['average']
    
    return round(avg, 2) if avg else 0.0


def get_grade_letter(marks):
    """Convert marks to grade letter"""
    if marks >= 90:
        return 'A+'
    elif marks >= 80:
        return 'A'
    elif marks >= 70:
        return 'B'
    elif marks >= 60:
        return 'C'
    elif marks >= 50:
        return 'D'
    else:
        return 'F'


def get_performance_level(average):
    """Get performance level description"""
    if average >= 80:
        return 'Excellent'
    elif average >= 70:
        return 'Very Good'
    elif average >= 60:
        return 'Good'
    elif average >= 50:
        return 'Satisfactory'
    else:
        return 'Needs Improvement'


def validate_phone_number(phone):
    """Validate phone number format"""
    # Remove spaces and special characters
    phone = re.sub(r'[^\d+]', '', phone)
    
    # Check if it's a valid format
    if len(phone) < 10:
        return False, "Phone number is too short"
    
    return True, phone


def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if re.match(pattern, email):
        return True, email.lower()
    return False, "Invalid email format"


def get_or_create_school_settings():
    """Get or create school settings singleton"""
    from .models import SchoolSettings
    
    settings = SchoolSettings.objects.first()
    if not settings:
        settings = SchoolSettings.objects.create(
            school_name="JOKS School Connect",
            school_email="info@joksschool.com",
            school_phone="+256 700 000000",
            school_address="Kampala, Uganda"
        )
    
    return settings


def generate_report_card_data(student, term):
    """Generate report card data for a student"""
    from .models import Grade, Attendance, Behavior
    from django.db.models import Avg
    
    # Get all grades for the term
    grades = Grade.objects.filter(
        student=student,
        term=term
    ).select_related('subject')
    
    # Calculate subject-wise performance
    subject_performance = []
    total_marks = 0
    total_subjects = 0
    
    for grade in grades:
        subject_performance.append({
            'subject': grade.subject.name,
            'marks': grade.marks,
            'grade': get_grade_letter(grade.marks),
            'teacher_comment': grade.comments
        })
        total_marks += grade.marks
        total_subjects += 1
    
    # Calculate average
    average = (total_marks / total_subjects) if total_subjects > 0 else 0
    
    # Get attendance
    attendance_percentage = get_attendance_percentage(student, term)
    
    # Get behavior records
    behaviors = Behavior.objects.filter(
        student=student,
        date__gte=term.start_date,
        date__lte=term.end_date
    )
    
    return {
        'student': student,
        'term': term,
        'subject_performance': subject_performance,
        'average_marks': round(average, 2),
        'grade_letter': get_grade_letter(average),
        'performance_level': get_performance_level(average),
        'attendance_percentage': attendance_percentage,
        'behaviors': behaviors,
        'total_subjects': total_subjects
    }


def get_class_statistics(classroom, term=None):
    """Get statistics for a class"""
    from .models import Student, Grade, Attendance
    from django.db.models import Avg, Count
    
    students = Student.objects.filter(current_class=classroom, is_active=True)
    student_count = students.count()
    
    if term:
        # Get average grade for the class
        avg_grade = Grade.objects.filter(
            student__in=students,
            term=term
        ).aggregate(avg=Avg('marks'))['avg'] or 0
        
        # Get attendance statistics
        attendance_records = Attendance.objects.filter(
            student__in=students,
            date__gte=term.start_date,
            date__lte=term.end_date
        )
        
        total_attendance = attendance_records.count()
        present_count = attendance_records.filter(status='Present').count()
        attendance_rate = (present_count / total_attendance * 100) if total_attendance > 0 else 0
    else:
        avg_grade = 0
        attendance_rate = 0
    
    return {
        'student_count': student_count,
        'average_grade': round(avg_grade, 2),
        'attendance_rate': round(attendance_rate, 2)
    }


def get_dashboard_stats(user):
    """Get dashboard statistics based on user role"""
    from .models import (
        Student, Teacher, ClassRoom, Message, Event,
        AdmissionApplication, FeePayment
    )
    from django.db.models import Sum
    
    stats = {}
    
    if is_admin(user):
        stats = {
            'total_students': Student.objects.filter(is_active=True).count(),
            'total_teachers': Teacher.objects.filter(user__is_active=True).count(),
            'total_classes': ClassRoom.objects.filter(
                academic_year=get_current_academic_year()
            ).count(),
            'pending_applications': AdmissionApplication.objects.filter(
                status='Pending'
            ).count(),
            'unread_messages': Message.objects.filter(
                recipient=user,
                is_read=False
            ).count(),
            'upcoming_events': Event.objects.filter(
                date__gte=timezone.now().date()
            ).count()[:5],
        }
        
        # Fee collection stats
        current_year = get_current_academic_year()
        if current_year:
            total_collected = FeePayment.objects.filter(
                fee_structure__academic_year=current_year,
                status='Confirmed'
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            stats['total_fees_collected'] = total_collected
    
    elif is_teacher(user):
        from .models import Teacher
        teacher = Teacher.objects.get(user=user)
        
        # Get classes taught
        classes_taught = ClassRoom.objects.filter(class_teacher=user)
        
        # Count total students
        total_students = Student.objects.filter(
            current_class__in=classes_taught,
            is_active=True
        ).count()
        
        stats = {
            'classes_taught': classes_taught.count(),
            'total_students': total_students,
            'unread_messages': Message.objects.filter(
                recipient=user,
                is_read=False
            ).count(),
            'upcoming_events': Event.objects.filter(
                date__gte=timezone.now().date()
            ).count()[:5],
        }
    
    elif is_parent(user):
        from .models import Parent, Student
        try:
            parent = Parent.objects.get(user=user)
            children = Student.objects.filter(parents=parent, is_active=True)
            
            stats = {
                'children_count': children.count(),
                'children': children,
                'unread_messages': Message.objects.filter(
                    recipient=user,
                    is_read=False
                ).count(),
                'upcoming_events': Event.objects.filter(
                    date__gte=timezone.now().date()
                ).count()[:5],
            }
        except Parent.DoesNotExist:
            stats = {}
    
    return stats


def paginate_queryset(queryset, page, per_page=20):
    """Paginate a queryset"""
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    
    paginator = Paginator(queryset, per_page)
    
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    return page_obj


def export_to_csv(queryset, fields, filename):
    """Export queryset to CSV"""
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    writer = csv.writer(response)
    writer.writerow(fields)
    
    for obj in queryset:
        row = [getattr(obj, field) for field in fields]
        writer.writerow(row)
    
    return response