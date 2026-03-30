from permissions.models import Permission  # adjust import to your app

permissions = [
    ("Student Management", "manage_students", "Control all student records, profiles, and related data"),
    ("Teacher Management", "manage_teachers", "Control teacher profiles, assignments, and records"),
    ("Staff Management", "manage_staff", "Control non-teaching staff profiles and records"),
    ("Parent Management", "manage_parents", "Control parent profiles and their linked students"),
    ("Fee Structure Management", "manage_fee_structure", "Configure and manage school fee structures and categories"),
    ("Payment Management", "manage_payments", "Process and oversee all fee payments and transactions"),
    ("Assessment Management", "manage_assessments", "Create and manage exams, tests, and assessment windows"),
    ("Grade Management", "manage_grades", "Enter and manage student scores and academic grades"),
    ("Subject Management", "manage_subjects", "Manage subjects offered across classes and streams"),
    ("Class Management", "manage_classes", "Manage classes, streams, and class assignments"),
    ("Timetable Management", "manage_timetable", "Create and manage class and teacher timetables"),
    ("Attendance Management", "manage_attendance", "Record and monitor student and staff attendance"),
    ("Admissions Management", "manage_admissions", "Handle student applications and enrollment processes"),
    ("Academic Term Management", "manage_academic_terms", "Configure terms, semesters, and academic calendar windows"),
    ("Curriculum Management", "manage_curriculum", "Manage the school curriculum and syllabus content"),
    ("Announcement Management", "manage_announcements", "Post and manage school-wide announcements"),
    ("Event Management", "manage_events", "Create and manage school events and activities"),
    ("Calendar Management", "manage_calendar", "Manage the school calendar and scheduled dates"),
    ("Report Management", "manage_reports", "Generate and access academic and administrative reports"),
    ("User Account Management", "manage_user_accounts", "Create, suspend, and manage all system user accounts"),
    ("Permission Management", "manage_permissions", "Assign and revoke permissions across user types"),
    ("Role Management", "manage_roles", "Create and configure user roles and their access levels"),
    ("Payroll Management", "manage_payroll", "Process staff payroll, allowances, and deductions"),
    ("Expense Management", "manage_expenses", "Record and manage school operational expenses"),
    ("Budget Management", "manage_budgets", "Plan and monitor departmental and school-wide budgets"),
    ("Finance Overview", "manage_finance", "Access and oversee all financial summaries and balances"),
    ("Library Management", "manage_library", "Manage library books, borrowing records, and inventory"),
    ("Inventory Management", "manage_inventory", "Track and manage school assets and physical inventory"),
    ("Procurement Management", "manage_procurement", "Handle purchasing requests and vendor procurement"),
    ("Supplier Management", "manage_suppliers", "Manage supplier records and procurement contacts"),
    ("Health Records Management", "manage_health_records", "Manage student and staff medical and health records"),
    ("Transport Management", "manage_transport", "Manage school transport routes, vehicles, and schedules"),
    ("Hostel Management", "manage_hostels", "Manage boarding facilities, rooms, and hostel records"),
    ("Club & Activity Management", "manage_clubs", "Manage student clubs, societies, and extracurricular activities"),
    ("Disciplinary Management", "manage_disciplinary", "Record and manage student disciplinary cases and actions"),
    ("Examination Management", "manage_examinations", "Organise and oversee formal examination logistics"),
    ("Certificate Management", "manage_certificates", "Issue and manage academic certificates and transcripts"),
    ("Alumni Management", "manage_alumni", "Manage records and communication with former students"),
    ("Communication Management", "manage_communication", "Manage internal messaging between staff, parents, and students"),
    ("Notification Management", "manage_notifications", "Configure and send system notifications and alerts"),
    ("SMS Management", "manage_sms", "Send and manage SMS messages to parents and staff"),
    ("Email Management", "manage_email", "Send and manage email correspondence from the system"),
    ("Document Management", "manage_documents", "Upload, organise, and control access to school documents"),
    ("Portal Management", "manage_portals", "Configure and manage parent and student portal access"),
    ("Maintenance Management", "manage_maintenance", "Log and track school facility maintenance requests"),
    ("System Settings", "manage_settings", "Configure global system settings and preferences"),
    ("Audit Log Access", "manage_audit_logs", "View system audit trails and user activity logs"),
    ("Backup Management", "manage_backups", "Initiate and manage system data backups"),
    ("Integration Management", "manage_integrations", "Configure third-party integrations and API connections"),
    ("Analytics Access", "manage_analytics", "Access dashboards and data analytics across the system"),
]

for title, code, description in permissions:
    obj, created = Permission.objects.get_or_create(
        permission_code=code,
        defaults={
            "permission_title": title,
            "description": description,
            "is_active": True,
        }
    )
    if created:
        print(f"  Created: {obj}")
    else:
        print(f"  Exists:  {obj}")

print(f"\nDone. {len(permissions)} permissions processed.")