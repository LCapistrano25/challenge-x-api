from django.contrib import admin

from apps.projects.models import (
    Project,
    Submission,
    SubmissionItem,
    SubmissionReceipt,
    SubmissionVersion,
)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "team", "edition", "challenge", "status")
    list_filter = ("edition", "status")
    list_select_related = ("team", "edition", "challenge")
    search_fields = ("title", "team__name")


class SubmissionVersionInline(admin.TabularInline):
    # Versões são histórico: só leitura no admin (RF31).
    model = SubmissionVersion
    extra = 0
    can_delete = False
    readonly_fields = ("number", "submitted_by", "submitted_at", "notes")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("project", "stage")
    list_filter = ("stage__edition",)
    list_select_related = ("project", "stage__edition")
    inlines = (SubmissionVersionInline,)


class SubmissionItemInline(admin.TabularInline):
    model = SubmissionItem
    extra = 0


@admin.register(SubmissionVersion)
class SubmissionVersionAdmin(admin.ModelAdmin):
    list_display = ("submission", "number", "submitted_by", "submitted_at")
    list_select_related = ("submission__project", "submitted_by__user")
    inlines = (SubmissionItemInline,)


@admin.register(SubmissionReceipt)
class SubmissionReceiptAdmin(admin.ModelAdmin):
    list_display = ("verification_code", "version", "generated_at")
    list_select_related = ("version__submission__project",)
    search_fields = ("verification_code",)
