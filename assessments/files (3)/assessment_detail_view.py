@login_required
def assessment_detail(request, pk):
    assessment = get_object_or_404(
        Assessment.objects.select_related('term', 'term__academic_year', 'created_by'),
        pk=pk,
    )

    classes = assessment.assessment_classes.select_related(
        'school_class__supported_class'
    ).order_by('school_class__supported_class__order')

    subjects = assessment.assessment_subjects.select_related(
        'subject'
    ).order_by('subject__name')

    teachers = assessment.assessment_teachers.select_related(
        'teacher', 'subject', 'school_class'
    ).order_by('teacher__last_name')

    performances = assessment.performances.select_related(
        'student', 'subject', 'school_class',
        'entered_by', 'verified_by',
    ).order_by('student__last_name', 'student__first_name')

    summary = build_performance_summary(assessment)

    return render(request, 'assessments/assessment_detail.html', {
        'assessment':   assessment,
        'classes':      classes,
        'subjects':     subjects,
        'teachers':     teachers,
        'performances': performances,
        'summary':      summary,
    })
