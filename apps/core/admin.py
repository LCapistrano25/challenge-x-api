from django.contrib import admin

from apps.core.models import Course, Sdg


class ReadOnlyMixin:
    """Histórico ou dado derivado: o admin só consulta (versões RF31, notas RF14)."""

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "term_count", "active")
    list_filter = ("active", "term_count")
    search_fields = ("name",)


@admin.register(Sdg)
class SdgAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "active")
    list_filter = ("active",)
    search_fields = ("title",)
