from django.contrib import admin

from assessments.models import Assessment,AssessmentClass,AssessmentSubject,AssessmentTeacher,AssessmentTotalMark

admin.site.register(Assessment)
admin.site.register(AssessmentSubject)
admin.site.register(AssessmentClass)
admin.site.register(AssessmentTotalMark)
# admin.site.register(A)


