import re
from datetime import date
from django.utils import timezone
from .models import ParentsRequest


# ─────────────────────────────────────────────────────────────────────────────
# Reference number
# ─────────────────────────────────────────────────────────────────────────────

def generate_reference_number():
    """
    Generates a unique reference number in the format REQ{YEAR}{3-digit-seq}.
    Example: REQ2025001, REQ2025002 …
    Pads to 4 digits once count exceeds 999: REQ20251000.
    """
    year = date.today().year
    prefix = f"REQ{year}"

    last = (
        ParentsRequest.objects
        .filter(reference_number__startswith=prefix)
        .order_by('-reference_number')
        .first()
    )

    if last:
        # Extract the numeric suffix after the year portion
        try:
            seq = int(last.reference_number[len(prefix):]) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1

    return f"{prefix}{seq:03d}"


# ─────────────────────────────────────────────────────────────────────────────
# Role helpers
# ─────────────────────────────────────────────────────────────────────────────

def is_staff_user(user):
    """
    Returns True if the user is a school staff member (not a parent).
    Adjust the field/role check to match your accounts.User model.
    """
    return user.is_staff or getattr(user, 'role', None) in ('admin', 'teacher', 'staff')


def is_parent_user(user):
    """Returns True if the user has a linked Parent profile."""
    return hasattr(user, 'parent_profile')


def get_parent_profile(user):
    """Returns the Parent instance linked to this user, or None."""
    return getattr(user, 'parent_profile', None)


# ─────────────────────────────────────────────────────────────────────────────
# Validation – ParentsRequest
# ─────────────────────────────────────────────────────────────────────────────

VALID_REQUEST_TYPES = [choice[0] for choice in ParentsRequest.REQUEST_TYPE_CHOICES]
VALID_STATUSES      = [choice[0] for choice in ParentsRequest.STATUS_CHOICES]

ALLOWED_ATTACHMENT_EXTENSIONS = {
    '.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.webp'
}
MAX_ATTACHMENT_MB = 5


def validate_parent_request(data, files=None):
    """
    Validates POST data for creating a ParentsRequest.

    Args:
        data  : request.POST
        files : request.FILES  (optional)

    Returns:
        errors (dict)  – empty dict means valid
        cleaned (dict) – cleaned/coerced values ready for model creation
    """
    errors  = {}
    cleaned = {}

    # ── request_type ─────────────────────────────────────────────────────────
    request_type = data.get('request_type', '').strip()
    if not request_type:
        errors['request_type'] = 'Please select a request type.'
    elif request_type not in VALID_REQUEST_TYPES:
        errors['request_type'] = 'Invalid request type selected.'
    else:
        cleaned['request_type'] = request_type

    # ── subject ───────────────────────────────────────────────────────────────
    subject = data.get('subject', '').strip()
    if not subject:
        errors['subject'] = 'Subject is required.'
    elif len(subject) < 5:
        errors['subject'] = 'Subject must be at least 5 characters.'
    elif len(subject) > 200:
        errors['subject'] = 'Subject cannot exceed 200 characters.'
    else:
        cleaned['subject'] = subject

    # ── message ───────────────────────────────────────────────────────────────
    message = data.get('message', '').strip()
    if not message:
        errors['message'] = 'Message body is required.'
    elif len(message) < 10:
        errors['message'] = 'Message must be at least 10 characters.'
    else:
        cleaned['message'] = message

    # ── is_urgent ─────────────────────────────────────────────────────────────
    cleaned['is_urgent'] = data.get('is_urgent') == 'on'

    # ── attachment (optional) ─────────────────────────────────────────────────
    if files:
        attachment = files.get('attachment')
        if attachment:
            ext = '.' + attachment.name.rsplit('.', 1)[-1].lower() if '.' in attachment.name else ''
            if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
                errors['attachment'] = (
                    f'Invalid file type. Allowed: '
                    f'{", ".join(sorted(ALLOWED_ATTACHMENT_EXTENSIONS))}'
                )
            elif attachment.size > MAX_ATTACHMENT_MB * 1024 * 1024:
                errors['attachment'] = f'File must not exceed {MAX_ATTACHMENT_MB} MB.'
            else:
                cleaned['attachment'] = attachment

    return errors, cleaned


# ─────────────────────────────────────────────────────────────────────────────
# Validation – ParentsRequestReply
# ─────────────────────────────────────────────────────────────────────────────

def validate_request_reply(data, files=None, is_staff=False):
    """
    Validates POST data for adding a ParentsRequestReply.

    Args:
        data     : request.POST
        files    : request.FILES
        is_staff : bool – True allows is_internal and status change

    Returns:
        errors (dict), cleaned (dict)
    """
    errors  = {}
    cleaned = {}

    # ── message ───────────────────────────────────────────────────────────────
    message = data.get('message', '').strip()
    if not message:
        errors['message'] = 'Reply message cannot be empty.'
    elif len(message) < 5:
        errors['message'] = 'Reply must be at least 5 characters.'
    else:
        cleaned['message'] = message

    # ── is_internal (staff only) ──────────────────────────────────────────────
    if is_staff:
        cleaned['is_internal'] = data.get('is_internal') == 'on'
    else:
        cleaned['is_internal'] = False

    # ── status change (staff only) ────────────────────────────────────────────
    if is_staff:
        new_status = data.get('status', '').strip()
        if new_status:
            if new_status not in VALID_STATUSES:
                errors['status'] = 'Invalid status selected.'
            else:
                cleaned['new_status'] = new_status

    # ── attachment (optional) ─────────────────────────────────────────────────
    if files:
        attachment = files.get('attachment')
        if attachment:
            ext = '.' + attachment.name.rsplit('.', 1)[-1].lower() if '.' in attachment.name else ''
            if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
                errors['attachment'] = (
                    f'Invalid file type. Allowed: '
                    f'{", ".join(sorted(ALLOWED_ATTACHMENT_EXTENSIONS))}'
                )
            elif attachment.size > MAX_ATTACHMENT_MB * 1024 * 1024:
                errors['attachment'] = f'File must not exceed {MAX_ATTACHMENT_MB} MB.'
            else:
                cleaned['attachment'] = attachment

    return errors, cleaned


# ─────────────────────────────────────────────────────────────────────────────
# Access control helper
# ─────────────────────────────────────────────────────────────────────────────

def user_can_access_request(user, parent_request):
    """
    Returns True if the user is allowed to view/reply to this request.
    - Staff always have access.
    - A parent may only access their own requests.
    """
    if is_staff_user(user):
        return True
    parent = get_parent_profile(user)
    if parent and parent_request.parent_id == parent.pk:
        return True
    return False
