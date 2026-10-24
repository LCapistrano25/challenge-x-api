from django.contrib import admin

from apps.core.models import Course, Sdg


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("name", "term_count", "active")
    list_filter = ("active", "term_count")
    search_fields = ("name",)


@admin.register(Sdg)
class SdgAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "active")
    list_filter = ("active",)
    search_fields = ("title",)
