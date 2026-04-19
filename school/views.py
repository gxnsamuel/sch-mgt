from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import datetime
import os

from .models import SchoolAnnouncement
from academics.models import SchoolSupportedClasses

@login_required
def announcement_add(request):
    """
    Add a new announcement without using Django forms.
    Validates fields manually and uses django.contrib.messages for feedback.
    """
    # ── CHOICES ──────────────────────────────────────────────────────────────
    AUDIENCE_CHOICES = [
        ('all',      'Everyone'),
        ('teachers', 'Teachers & Staff'),
        ('parents',  'Parents & Guardians'),
        ('students', 'Students'),
    ]
    PRIORITY_CHOICES = [
        ('normal',  'Normal'),
        ('urgent',  'Urgent'),
        ('critical','Critical'),
    ]
    VALID_AUDIENCES = [c[0] for c in AUDIENCE_CHOICES]
    VALID_PRIORITIES = [c[0] for c in PRIORITY_CHOICES]

    # ── LOOKUPS ──────────────────────────────────────────────────────────────
    # We use SchoolSupportedClasses because that's what SchoolAnnouncement.school_class points to.
    supported_classes_qs = SchoolSupportedClasses.objects.select_related('supported_class').all()
    all_classes = []
    for sc in supported_classes_qs:
        # We add display_name attribute to match what the template expects
        sc.display_name = sc.supported_class.name
        all_classes.append(sc)
    
    # Sort all_classes by the order of the supported_class
    all_classes.sort(key=lambda x: x.supported_class.order if x.supported_class else 0)

    context = {
        'form_title': 'New Announcement',
        'action': 'add',
        'audience_choices': AUDIENCE_CHOICES,
        'priority_choices': PRIORITY_CHOICES,
        'all_classes': all_classes,
        'now_str': timezone.now().strftime('%Y-%m-%dT%H:%M'),
        'post': {},
        'errors': {},
    }

    if request.method == 'POST':
        errors = {}
        post_data = request.POST
        files_data = request.FILES

        # ── MANUAL VALIDATION ────────────────────────────────────────────────
        title = post_data.get('title', '').strip()
        if not title:
            errors['title'] = 'Announcement title is required.'
        elif len(title) > 200:
            errors['title'] = 'Title must not exceed 200 characters.'

        content = post_data.get('content', '').strip()
        if not content:
            errors['content'] = 'Announcement content is required.'

        audience = post_data.get('audience', '').strip()
        if not audience:
            errors['audience'] = 'Target audience is required.'
        elif audience not in VALID_AUDIENCES:
            errors['audience'] = 'Invalid audience selected.'

        priority = post_data.get('priority', '').strip()
        if not priority:
            errors['priority'] = 'Priority level is required.'
        elif priority not in VALID_PRIORITIES:
            errors['priority'] = 'Invalid priority selected.'

        school_class_id = post_data.get('school_class', '').strip()
        school_class = None
        if school_class_id:
            try:
                school_class = SchoolSupportedClasses.objects.get(pk=school_class_id)
            except (ValueError, SchoolSupportedClasses.DoesNotExist):
                errors['school_class'] = 'Invalid class selected.'

        is_published = post_data.get('is_published') == '1'
        
        published_at = None
        published_at_str = post_data.get('published_at', '').strip()
        if published_at_str:
            for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
                try:
                    naive_dt = datetime.strptime(published_at_str, fmt)
                    published_at = timezone.make_aware(naive_dt)
                    break
                except ValueError:
                    continue
            if not published_at:
                errors['published_at'] = 'Invalid publish date format.'

        expires_at = None
        expires_at_str = post_data.get('expires_at', '').strip()
        if expires_at_str:
            for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
                try:
                    naive_dt = datetime.strptime(expires_at_str, fmt)
                    expires_at = timezone.make_aware(naive_dt)
                    break
                except ValueError:
                    continue
            if not expires_at:
                errors['expires_at'] = 'Invalid expiry date format.'

        if published_at and expires_at and expires_at <= published_at:
            errors['expires_at'] = 'Expiry date must be after the publish date.'

        attachment = files_data.get('attachment')
        if attachment:
            if attachment.size > 5 * 1024 * 1024:
                errors['attachment'] = 'Attachment size must be less than 5MB.'
            allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.docx', '.doc']
            ext = os.path.splitext(attachment.name)[1].lower()
            if ext not in allowed_extensions:
                errors['attachment'] = f'Unsupported file extension {ext}.'

        if errors:
            context['post'] = post_data
            context['errors'] = errors
            messages.error(request, "Please correct the errors below.")
            return render(request, 'school/announcements/form.html', context)

        # ── SAVE ─────────────────────────────────────────────────────────────
        try:
            # Handle published_at logic: if published and no date given, use now.
            if is_published and not published_at:
                published_at = timezone.now()

            announcement = SchoolAnnouncement(
                title=title,
                content=content,
                audience=audience,
                priority=priority,
                school_class=school_class,
                is_published=is_published,
                published_at=published_at,
                expires_at=expires_at,
                attachment=attachment,
                posted_by=request.user
            )
            announcement.save()
            
            messages.success(request, f'Announcement "{title}" created successfully.')
            return redirect('school:announcement_detail', pk=announcement.pk)
        except Exception as e:
            messages.error(request, f'Error saving announcement: {str(e)}')
            context['post'] = post_data
            return render(request, 'school/announcements/form.html', context)

    return render(request, 'school/announcements/form.html', context)
