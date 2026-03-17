# views_extended.py
# Additional views for remaining models

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Sum, Avg, Count
from django.utils import timezone
from decimal import Decimal

from .models import *
from .helpers import *


# ============================================================================
# PARENT VIEWS
# ============================================================================

@login_required
@user_passes_test(is_admin)
def parents_list_view(request):
    """List all parents"""
    search = request.GET.get('search', '').strip()
    
    parents = Parent.objects.select_related('user').filter(user__is_active=True)
    
    if search:
        parents = parents.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__email__icontains=search) |
            Q(phone__icontains=search)
        )
    
    parents = parents.order_by('user__last_name', 'user__first_name')
    
    context = {
        'parents': parents,
        'search_query': search
    }
    return render(request, 'parents/parents_list.html', context)


@login_required
def parent_detail_view(request, parent_id):
    """View parent details"""
    parent = get_object_or_404(Parent, id=parent_id)
    
    # Permission check
    if request.user.role == 'Parent' and parent.user != request.user:
        return HttpResponseForbidden()
    
    # Get children
    children = Student.objects.filter(parents=parent, is_active=True)
    
    context = {
        'parent': parent,
        'children': children
    }
    return render(request, 'parents/parent_detail.html', context)


# ============================================================================
# CLASS VIEWS
# ============================================================================

@login_required
@user_passes_test(lambda u: is_admin(u) or is_teacher(u))
def classrooms_list_view(request):
    """List all classrooms"""
    current_year = get_current_academic_year()
    
    classrooms = ClassRoom.objects.filter(
        academic_year=current_year
    ).select_related('grade_level', 'class_teacher').annotate(
        student_count=Count('students')
    ).order_by('grade_level__order', 'name')
    
    context = {
        'classrooms': classrooms,
        'current_year': current_year
    }
    return render(request, 'classes/classrooms_list.html', context)


@login_required
@user_passes_test(lambda u: is_admin(u) or is_teacher(u))
def classroom_detail_view(request, classroom_id):
    """View classroom details"""
    classroom = get_object_or_404(ClassRoom, id=classroom_id)
    
    # Get students in this class
    students = Student.objects.filter(
        current_class=classroom,
        is_active=True
    ).order_by('last_name', 'first_name')
    
    # Get class statistics
    current_term = get_current_term()
    stats = get_class_statistics(classroom, current_term)
    
    # Get subjects taught in this class
    subjects = classroom.grade_level.subjects.filter(is_active=True)
    
    context = {
        'classroom': classroom,
        'students': students,
        'stats': stats,
        'subjects': subjects,
        'current_term': current_term
    }
    return render(request, 'classes/classroom_detail.html', context)


@login_required
@user_passes_test(is_admin)
def classroom_add_view(request):
    """Add new classroom"""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        grade_level_id = request.POST.get('grade_level')
        academic_year_id = request.POST.get('academic_year')
        class_teacher_id = request.POST.get('class_teacher')
        capacity = request.POST.get('capacity', 30)
        room_number = request.POST.get('room_number', '').strip()
        
        if not all([name, grade_level_id, academic_year_id]):
            messages.error(request, 'Please fill in required fields')
        else:
            try:
                classroom = ClassRoom.objects.create(
                    name=name,
                    grade_level_id=grade_level_id,
                    academic_year_id=academic_year_id,
                    class_teacher_id=class_teacher_id if class_teacher_id else None,
                    capacity=capacity,
                    room_number=room_number
                )
                
                log_audit(request.user, 'CREATE', 'ClassRoom', str(classroom.id),
                         f'Classroom {classroom.name} created', get_client_ip(request))
                
                messages.success(request, 'Classroom created successfully')
                return redirect('classroom_detail', classroom_id=classroom.id)
            except Exception as e:
                messages.error(request, f'Error creating classroom: {str(e)}')
    
    grade_levels = GradeLevel.objects.all().order_by('order')
    academic_years = AcademicYear.objects.all().order_by('-start_date')
    teachers = User.objects.filter(role='Teacher', is_active=True)
    
    context = {
        'grade_levels': grade_levels,
        'academic_years': academic_years,
        'teachers': teachers
    }
    return render(request, 'classes/classroom_add.html', context)


@login_required
@user_passes_test(is_admin)
def classroom_edit_view(request, classroom_id):
    """Edit classroom"""
    classroom = get_object_or_404(ClassRoom, id=classroom_id)
    
    if request.method == 'POST':
        classroom.name = request.POST.get('name', '').strip()
        classroom.grade_level_id = request.POST.get('grade_level')
        classroom.class_teacher_id = request.POST.get('class_teacher') or None
        classroom.capacity = request.POST.get('capacity', 30)
        classroom.room_number = request.POST.get('room_number', '').strip()
        
        try:
            classroom.save()
            log_audit(request.user, 'UPDATE', 'ClassRoom', str(classroom.id),
                     f'Classroom {classroom.name} updated', get_client_ip(request))
            messages.success(request, 'Classroom updated successfully')
            return redirect('classroom_detail', classroom_id=classroom.id)
        except Exception as e:
            messages.error(request, f'Error updating classroom: {str(e)}')
    
    grade_levels = GradeLevel.objects.all().order_by('order')
    teachers = User.objects.filter(role='Teacher', is_active=True)
    
    context = {
        'classroom': classroom,
        'grade_levels': grade_levels,
        'teachers': teachers
    }
    return render(request, 'classes/classroom_edit.html', context)


# ============================================================================
# ATTENDANCE VIEWS
# ============================================================================

@login_required
@user_passes_test(lambda u: is_admin(u) or is_teacher(u))
def attendance_mark_view(request, classroom_id):
    """Mark attendance for a class"""
    classroom = get_object_or_404(ClassRoom, id=classroom_id)
    
    # Permission check for teachers
    if is_teacher(request.user) and classroom.class_teacher != request.user:
        messages.error(request, 'You can only mark attendance for your own class')
        return redirect('classrooms_list')
    
    students = Student.objects.filter(
        current_class=classroom,
        is_active=True
    ).order_by('last_name', 'first_name')
    
    if request.method == 'POST':
        attendance_date = request.POST.get('date', timezone.now().date())
        
        # Delete existing attendance for this date
        Attendance.objects.filter(
            student__in=students,
            date=attendance_date
        ).delete()
        
        # Create new attendance records
        for student in students:
            status = request.POST.get(f'status_{student.id}', 'Absent')
            remarks = request.POST.get(f'remarks_{student.id}', '').strip()
            
            Attendance.objects.create(
                student=student,
                date=attendance_date,
                status=status,
                marked_by=request.user,
                remarks=remarks
            )
        
        log_audit(request.user, 'CREATE', 'Attendance', str(classroom.id),
                 f'Attendance marked for {classroom.name} on {attendance_date}',
                 get_client_ip(request))
        
        messages.success(request, 'Attendance marked successfully')
        return redirect('classroom_detail', classroom_id=classroom.id)
    
    # Get today's date
    today = timezone.now().date()
    
    # Check if attendance already marked for today
    existing_attendance = Attendance.objects.filter(
        student__in=students,
        date=today
    ).select_related('student')
    
    # Create dict for easy lookup
    attendance_dict = {att.student.id: att for att in existing_attendance}
    
    context = {
        'classroom': classroom,
        'students': students,
        'today': today,
        'attendance_dict': attendance_dict,
        'status_choices': Attendance.STATUS_CHOICES
    }
    return render(request, 'attendance/mark_attendance.html', context)


@login_required
@user_passes_test(lambda u: is_admin(u) or is_teacher(u))
def attendance_report_view(request):
    """Attendance reports"""
    classroom_id = request.GET.get('classroom')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    attendance_records = Attendance.objects.all()
    
    if classroom_id:
        attendance_records = attendance_records.filter(student__current_class__id=classroom_id)
    
    if start_date:
        attendance_records = attendance_records.filter(date__gte=start_date)
    
    if end_date:
        attendance_records = attendance_records.filter(date__lte=end_date)
    
    attendance_records = attendance_records.select_related('student', 'marked_by').order_by('-date', 'student__last_name')
    
    current_year = get_current_academic_year()
    classrooms = ClassRoom.objects.filter(academic_year=current_year)
    
    context = {
        'attendance_records': attendance_records,
        'classrooms': classrooms,
        'selected_classroom': classroom_id,
        'start_date': start_date,
        'end_date': end_date
    }
    return render(request, 'attendance/attendance_report.html', context)


# ============================================================================
# GRADES VIEWS
# ============================================================================

@login_required
@user_passes_test(lambda u: is_admin(u) or is_teacher(u))
def grades_entry_view(request, classroom_id):
    """Enter grades for a class"""
    classroom = get_object_or_404(ClassRoom, id=classroom_id)
    
    # Get subjects for this grade level
    subjects = classroom.grade_level.subjects.filter(is_active=True)
    current_term = get_current_term()
    
    students = Student.objects.filter(
        current_class=classroom,
        is_active=True
    ).order_by('last_name', 'first_name')
    
    if request.method == 'POST':
        subject_id = request.POST.get('subject')
        exam_type = request.POST.get('exam_type')
        date_recorded = request.POST.get('date', timezone.now().date())
        
        if not all([subject_id, exam_type]):
            messages.error(request, 'Please select subject and exam type')
        else:
            # Save grades for each student
            for student in students:
                marks = request.POST.get(f'marks_{student.id}', '').strip()
                comments = request.POST.get(f'comments_{student.id}', '').strip()
                
                if marks:
                    # Check if grade already exists
                    grade, created = Grade.objects.get_or_create(
                        student=student,
                        subject_id=subject_id,
                        term=current_term,
                        exam_type=exam_type,
                        defaults={
                            'marks': Decimal(marks),
                            'comments': comments,
                            'date_recorded': date_recorded,
                            'recorded_by': request.user
                        }
                    )
                    
                    if not created:
                        grade.marks = Decimal(marks)
                        grade.comments = comments
                        grade.recorded_by = request.user
                        grade.save()
            
            log_audit(request.user, 'CREATE', 'Grade', str(classroom.id),
                     f'Grades entered for {classroom.name}', get_client_ip(request))
            
            messages.success(request, 'Grades entered successfully')
            return redirect('classroom_detail', classroom_id=classroom.id)
    
    context = {
        'classroom': classroom,
        'students': students,
        'subjects': subjects,
        'current_term': current_term,
        'exam_types': Grade.EXAM_TYPE_CHOICES
    }
    return render(request, 'grades/grades_entry.html', context)


@login_required
def grades_view_student(request, student_id):
    """View grades for a specific student"""
    student = get_object_or_404(Student, id=student_id)
    
    # Permission check
    if request.user.role == 'Parent':
        if not student.parents.filter(user=request.user).exists():
            return HttpResponseForbidden()
    
    current_term = get_current_term()
    
    # Get grades for current term
    grades = Grade.objects.filter(
        student=student,
        term=current_term
    ).select_related('subject', 'recorded_by').order_by('subject__name', 'exam_type')
    
    # Calculate average
    if grades.exists():
        total_marks = sum(grade.marks for grade in grades)
        average = total_marks / len(grades)
    else:
        average = 0
    
    context = {
        'student': student,
        'grades': grades,
        'current_term': current_term,
        'average': round(average, 2),
        'grade_letter': get_grade_letter(average)
    }
    return render(request, 'grades/student_grades.html', context)


# ============================================================================
# FEES VIEWS
# ============================================================================

@login_required
@user_passes_test(is_admin)
def fee_structures_list_view(request):
    """List fee structures"""
    current_year = get_current_academic_year()
    
    fee_structures = FeeStructure.objects.filter(
        academic_year=current_year
    ).select_related('grade_level').order_by('grade_level__order')
    
    context = {
        'fee_structures': fee_structures,
        'current_year': current_year
    }
    return render(request, 'fees/fee_structures_list.html', context)


@login_required
@user_passes_test(is_admin)
def fee_structure_add_view(request):
    """Add fee structure"""
    if request.method == 'POST':
        grade_level_id = request.POST.get('grade_level')
        academic_year_id = request.POST.get('academic_year')
        tuition = Decimal(request.POST.get('tuition', 0))
        transport = Decimal(request.POST.get('transport', 0))
        lunch = Decimal(request.POST.get('lunch', 0))
        uniform = Decimal(request.POST.get('uniform', 0))
        books = Decimal(request.POST.get('books', 0))
        activities = Decimal(request.POST.get('activities', 0))
        other_fees = Decimal(request.POST.get('other_fees', 0))
        
        if not all([grade_level_id, academic_year_id]):
            messages.error(request, 'Please fill in required fields')
        else:
            try:
                total = tuition + transport + lunch + uniform + books + activities + other_fees
                
                fee_structure = FeeStructure.objects.create(
                    grade_level_id=grade_level_id,
                    academic_year_id=academic_year_id,
                    tuition_fee=tuition,
                    transport_fee=transport,
                    lunch_fee=lunch,
                    uniform_fee=uniform,
                    books_fee=books,
                    activities_fee=activities,
                    other_fees=other_fees,
                    total_amount=total,
                    is_active=True
                )
                
                log_audit(request.user, 'CREATE', 'FeeStructure', str(fee_structure.id),
                         'Fee structure created', get_client_ip(request))
                
                messages.success(request, 'Fee structure created successfully')
                return redirect('fee_structures_list')
            except Exception as e:
                messages.error(request, f'Error creating fee structure: {str(e)}')
    
    grade_levels = GradeLevel.objects.all().order_by('order')
    academic_years = AcademicYear.objects.all().order_by('-start_date')
    
    context = {
        'grade_levels': grade_levels,
        'academic_years': academic_years
    }
    return render(request, 'fees/fee_structure_add.html', context)


@login_required
def fee_payments_list_view(request, student_id=None):
    """List fee payments"""
    if student_id:
        student = get_object_or_404(Student, id=student_id)
        
        # Permission check
        if request.user.role == 'Parent':
            if not student.parents.filter(user=request.user).exists():
                return HttpResponseForbidden()
        
        payments = FeePayment.objects.filter(student=student)
    else:
        # Admin view - all payments
        if not is_admin(request.user):
            return HttpResponseForbidden()
        
        student = None
        payments = FeePayment.objects.all()
    
    payments = payments.select_related('student', 'fee_structure').order_by('-payment_date')
    
    context = {
        'payments': payments,
        'student': student
    }
    return render(request, 'fees/payments_list.html', context)


@login_required
@user_passes_test(is_admin)
def fee_payment_add_view(request, student_id):
    """Record fee payment"""
    student = get_object_or_404(Student, id=student_id)
    
    current_year = get_current_academic_year()
    fee_structure = FeeStructure.objects.filter(
        grade_level=student.current_class.grade_level,
        academic_year=current_year,
        is_active=True
    ).first()
    
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount', 0))
        payment_method = request.POST.get('payment_method')
        payment_date = request.POST.get('payment_date', timezone.now().date())
        reference_number = request.POST.get('reference_number', '').strip()
        remarks = request.POST.get('remarks', '').strip()
        
        if not all([amount, payment_method]):
            messages.error(request, 'Please fill in required fields')
        else:
            try:
                payment = FeePayment.objects.create(
                    student=student,
                    fee_structure=fee_structure,
                    amount=amount,
                    payment_method=payment_method,
                    payment_date=payment_date,
                    reference_number=reference_number,
                    remarks=remarks,
                    status='Confirmed',
                    recorded_by=request.user
                )
                
                log_audit(request.user, 'PAYMENT', 'FeePayment', str(payment.id),
                         f'Payment of {amount} recorded for {student.admission_number}',
                         get_client_ip(request))
                
                messages.success(request, 'Payment recorded successfully')
                return redirect('student_detail', student_id=student.id)
            except Exception as e:
                messages.error(request, f'Error recording payment: {str(e)}')
    
    # Calculate balance
    balance = calculate_fee_balance(student, current_year)
    
    context = {
        'student': student,
        'fee_structure': fee_structure,
        'balance': balance,
        'payment_methods': FeePayment.PAYMENT_METHOD_CHOICES
    }
    return render(request, 'fees/payment_add.html', context)


# ============================================================================
# MESSAGING VIEWS
# ============================================================================

@login_required
def messages_inbox_view(request):
    """View inbox messages"""
    messages_list = Message.objects.filter(
        recipient=request.user
    ).select_related('sender', 'student').order_by('-sent_at')
    
    # Mark as read when clicked
    msg_id = request.GET.get('read')
    if msg_id:
        try:
            msg = Message.objects.get(id=msg_id, recipient=request.user)
            if not msg.is_read:
                msg.is_read = True
                msg.read_at = timezone.now()
                msg.save()
        except Message.DoesNotExist:
            pass
    
    context = {'messages_list': messages_list}
    return render(request, 'messages/inbox.html', context)


@login_required
def messages_sent_view(request):
    """View sent messages"""
    messages_list = Message.objects.filter(
        sender=request.user
    ).select_related('recipient', 'student').order_by('-sent_at')
    
    context = {'messages_list': messages_list}
    return render(request, 'messages/sent.html', context)


@login_required
def message_compose_view(request):
    """Compose new message"""
    if request.method == 'POST':
        recipient_id = request.POST.get('recipient')
        subject = request.POST.get('subject', '').strip()
        message_type = request.POST.get('message_type', 'General')
        body = request.POST.get('body', '').strip()
        student_id = request.POST.get('student') or None
        
        if not all([recipient_id, subject, body]):
            messages.error(request, 'Please fill in all fields')
        else:
            try:
                message = Message.objects.create(
                    sender=request.user,
                    recipient_id=recipient_id,
                    subject=subject,
                    message_type=message_type,
                    body=body,
                    student_id=student_id
                )
                
                # Send email notification
                try:
                    recipient = User.objects.get(id=recipient_id)
                    send_notification_email(
                        recipient.email,
                        f'New Message: {subject}',
                        f'You have a new message from {request.user.get_full_name()}\n\n{body}'
                    )
                except:
                    pass
                
                messages.success(request, 'Message sent successfully')
                return redirect('messages_sent')
            except Exception as e:
                messages.error(request, f'Error sending message: {str(e)}')
    
    # Get recipients based on user role
    if is_admin(request.user):
        recipients = User.objects.filter(is_active=True).exclude(id=request.user.id)
    elif is_teacher(request.user):
        # Teachers can message admins and parents of their students
        teacher = Teacher.objects.get(user=request.user)
        classes = ClassRoom.objects.filter(class_teacher=request.user)
        students = Student.objects.filter(current_class__in=classes)
        parent_users = User.objects.filter(parent_profile__students__in=students).distinct()
        admin_users = User.objects.filter(role='Admin', is_active=True)
        recipients = (parent_users | admin_users).exclude(id=request.user.id)
    else:  # Parent
        # Parents can message teachers and admins
        recipients = User.objects.filter(
            Q(role='Teacher') | Q(role='Admin'),
            is_active=True
        )
    
    # Get students (for context)
    if is_parent(request.user):
        parent = Parent.objects.get(user=request.user)
        students = Student.objects.filter(parents=parent, is_active=True)
    else:
        students = Student.objects.filter(is_active=True)
    
    context = {
        'recipients': recipients,
        'students': students,
        'message_types': Message.MESSAGE_TYPE_CHOICES
    }
    return render(request, 'messages/compose.html', context)


@login_required
def message_detail_view(request, message_id):
    """View message detail"""
    message = get_object_or_404(Message, id=message_id)
    
    # Permission check
    if message.sender != request.user and message.recipient != request.user:
        return HttpResponseForbidden()
    
    # Mark as read if recipient
    if message.recipient == request.user and not message.is_read:
        message.is_read = True
        message.read_at = timezone.now()
        message.save()
    
    context = {'message': message}
    return render(request, 'messages/message_detail.html', context)


# ============================================================================
# ANNOUNCEMENT VIEWS
# ============================================================================

@login_required
@user_passes_test(is_admin)
def announcements_list_view(request):
    """List all announcements"""
    announcements = Announcement.objects.all().order_by('-publish_date')
    
    context = {'announcements': announcements}
    return render(request, 'announcements/announcements_list.html', context)


@login_required
@user_passes_test(is_admin)
def announcement_add_view(request):
    """Add new announcement"""
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        target_audience = request.POST.get('target_audience', 'All')
        grade_level_id = request.POST.get('grade_level') or None
        is_urgent = request.POST.get('is_urgent') == 'on'
        expiry_date = request.POST.get('expiry_date') or None
        
        if not all([title, content]):
            messages.error(request, 'Please fill in required fields')
        else:
            try:
                announcement = Announcement.objects.create(
                    title=title,
                    content=content,
                    target_audience=target_audience,
                    grade_level_id=grade_level_id,
                    is_urgent=is_urgent,
                    expiry_date=expiry_date,
                    created_by=request.user
                )
                
                log_audit(request.user, 'CREATE', 'Announcement', str(announcement.id),
                         f'Announcement created: {title}', get_client_ip(request))
                
                messages.success(request, 'Announcement created successfully')
                return redirect('announcements_list')
            except Exception as e:
                messages.error(request, f'Error creating announcement: {str(e)}')
    
    grade_levels = GradeLevel.objects.all().order_by('order')
    
    context = {
        'grade_levels': grade_levels,
        'target_choices': Announcement.TARGET_CHOICES
    }
    return render(request, 'announcements/announcement_add.html', context)


@login_required
@user_passes_test(is_admin)
def announcement_edit_view(request, announcement_id):
    """Edit announcement"""
    announcement = get_object_or_404(Announcement, id=announcement_id)
    
    if request.method == 'POST':
        announcement.title = request.POST.get('title', '').strip()
        announcement.content = request.POST.get('content', '').strip()
        announcement.target_audience = request.POST.get('target_audience', 'All')
        announcement.grade_level_id = request.POST.get('grade_level') or None
        announcement.is_urgent = request.POST.get('is_urgent') == 'on'
        announcement.expiry_date = request.POST.get('expiry_date') or None
        
        try:
            announcement.save()
            log_audit(request.user, 'UPDATE', 'Announcement', str(announcement.id),
                     'Announcement updated', get_client_ip(request))
            messages.success(request, 'Announcement updated successfully')
            return redirect('announcements_list')
        except Exception as e:
            messages.error(request, f'Error updating announcement: {str(e)}')
    
    grade_levels = GradeLevel.objects.all().order_by('order')
    
    context = {
        'announcement': announcement,
        'grade_levels': grade_levels,
        'target_choices': Announcement.TARGET_CHOICES
    }
    return render(request, 'announcements/announcement_edit.html', context)


@login_required
@user_passes_test(is_admin)
def announcement_delete_view(request, announcement_id):
    """Delete announcement"""
    announcement = get_object_or_404(Announcement, id=announcement_id)
    
    if request.method == 'POST':
        announcement.delete()
        log_audit(request.user, 'DELETE', 'Announcement', str(announcement_id),
                 'Announcement deleted', get_client_ip(request))
        messages.success(request, 'Announcement deleted successfully')
        return redirect('announcements_list')
    
    context = {'announcement': announcement}
    return render(request, 'announcements/announcement_delete.html', context)


# ============================================================================
# DASHBOARD VIEWS
# ============================================================================

@login_required
def dashboard_redirect_view(request):
    """Redirect to appropriate dashboard based on role"""
    if request.user.role == 'Admin':
        return redirect('admin_dashboard')
    elif request.user.role == 'Teacher':
        return redirect('teacher_dashboard')
    else:
        return redirect('parent_dashboard')


@login_required
@user_passes_test(is_admin)
def admin_dashboard_view(request):
    """Admin Dashboard"""
    stats = get_dashboard_stats(request.user)
    
    # Recent applications
    recent_applications = AdmissionApplication.objects.filter(
        status='Pending'
    ).order_by('-submitted_at')[:5]
    
    # Recent payments
    recent_payments = FeePayment.objects.all().order_by('-payment_date')[:10]
    
    # Upcoming events
    upcoming_events = Event.objects.filter(
        date__gte=timezone.now().date()
    ).order_by('date')[:5]
    
    context = {
        **stats,
        'recent_applications': recent_applications,
        'recent_payments': recent_payments,
        'upcoming_events': upcoming_events
    }
    return render(request, 'dashboards/admin_dashboard.html', context)


@login_required
@user_passes_test(is_teacher)
def teacher_dashboard_view(request):
    """Teacher Dashboard"""
    stats = get_dashboard_stats(request.user)
    
    # Get classes taught
    classes = ClassRoom.objects.filter(class_teacher=request.user)
    
    # Recent messages
    recent_messages = Message.objects.filter(
        recipient=request.user,
        is_read=False
    ).order_by('-sent_at')[:5]
    
    # Upcoming events
    upcoming_events = Event.objects.filter(
        date__gte=timezone.now().date()
    ).order_by('date')[:5]
    
    context = {
        **stats,
        'classes': classes,
        'recent_messages': recent_messages,
        'upcoming_events': upcoming_events
    }
    return render(request, 'dashboards/teacher_dashboard.html', context)


@login_required
@user_passes_test(is_parent)
def parent_dashboard_view(request):
    """Parent Dashboard"""
    stats = get_dashboard_stats(request.user)
    
    try:
        parent = Parent.objects.get(user=request.user)
        children = Student.objects.filter(parents=parent, is_active=True)
        
        # Get fee balances for each child
        current_year = get_current_academic_year()
        children_with_fees = []
        for child in children:
            balance = calculate_fee_balance(child, current_year)
            children_with_fees.append({
                'student': child,
                'fee_balance': balance
            })
        
    except Parent.DoesNotExist:
        children_with_fees = []
    
    # Recent messages
    recent_messages = Message.objects.filter(
        recipient=request.user
    ).order_by('-sent_at')[:5]
    
    # Upcoming events
    upcoming_events = Event.objects.filter(
        date__gte=timezone.now().date()
    ).order_by('date')[:5]
    
    context = {
        **stats,
        'children_with_fees': children_with_fees,
        'recent_messages': recent_messages,
        'upcoming_events': upcoming_events
    }
    return render(request, 'dashboards/parent_dashboard.html', context)