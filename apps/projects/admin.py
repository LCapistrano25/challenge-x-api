from django.contrib import admin

from apps.projects.models import (
    DeadlineExtension,
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


class ReadOnlyMixin:
    """Versões e itens enviados são histórico: o admin só consulta (RF31)."""

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class SubmissionVersionInline(ReadOnlyMixin, admin.TabularInline):
    model = SubmissionVersion
    extra = 0


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("project", "stage")
    list_filter = ("stage__edition",)
    list_select_related = ("project", "stage__edition")
    inlines = (SubmissionVersionInline,)


class SubmissionItemInline(ReadOnlyMixin, admin.TabularInline):
    model = SubmissionItem
    extra = 0


@admin.register(SubmissionVersion)
class SubmissionVersionAdmin(ReadOnlyMixin, admin.ModelAdmin):
    list_display = ("submission", "number", "submitted_by", "submitted_at")
    list_select_related = ("submission__project", "submitted_by__user")
    inlines = (SubmissionItemInline,)


@admin.register(SubmissionReceipt)
class SubmissionReceiptAdmin(admin.ModelAdmin):
    list_display = ("verification_code", "version", "generated_at")
    list_select_related = ("version__submission__project",)
    search_fields = ("verification_code",)


@admin.register(DeadlineExtension)
class DeadlineExtensionAdmin(admin.ModelAdmin):
    """O admin concede; depois de gravada, a prorrogação é histórico (RF14)."""

    list_display = ("project", "stage", "ends_at", "granted_by", "granted_at")
    list_filter = ("stage__edition",)
    list_select_related = ("project", "stage", "granted_by")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.granted_by = request.user
        super().save_model(request, obj, form, change)
