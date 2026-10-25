from django.contrib import admin

from apps.results.models import (
    Certificate,
    CertificateTemplate,
    ProjectResult,
    StudentScore,
)


@admin.register(ProjectResult)
class ProjectResultAdmin(admin.ModelAdmin):
    list_display = (
        "project",
        "final_score",
        "course_rank",
        "category_rank",
        "finalist",
        "award",
        "approved_at",
    )
    list_filter = ("finalist", "project__edition")
    list_select_related = ("project",)


@admin.register(StudentScore)
class StudentScoreAdmin(admin.ModelAdmin):
    list_display = ("student", "project", "term", "points", "calculated_at")
    list_filter = ("project__edition",)
    list_select_related = ("student__user", "project")


@admin.register(CertificateTemplate)
class CertificateTemplateAdmin(admin.ModelAdmin):
    list_display = ("__str__", "edition", "kind")
    list_filter = ("kind",)
    list_select_related = ("edition",)


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ("template", "user", "workload_hours", "issued_at")
    list_filter = ("template__kind",)
    list_select_related = ("template__edition", "user")
    readonly_fields = ("verification_code",)
