from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.accounts.models import (
    EmailDomain,
    ExternalReviewer,
    Student,
    Teacher,
    TeacherCourse,
    User,
)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    ordering = ("email",)
    list_display = ("email", "role", "email_confirmed", "is_staff", "is_active")
    list_filter = ("role", "email_confirmed", "is_staff", "is_active")
    search_fields = ("email", "first_name", "last_name")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Dados pessoais", {"fields": ("first_name", "last_name")}),
        ("Perfil", {"fields": ("role", "email_confirmed")}),
        (
            "Permissões",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Datas importantes", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "role",
                    "password1",
                    "password2",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )


@admin.register(EmailDomain)
class EmailDomainAdmin(admin.ModelAdmin):
    list_display = ("name", "role", "active")
    list_filter = ("role", "active")
    search_fields = ("name",)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("user", "registration_number", "course", "term")
    list_filter = ("course", "term")
    list_select_related = ("user", "course")
    search_fields = ("user__email", "registration_number")
    autocomplete_fields = ("user",)


class TeacherCourseInline(admin.TabularInline):
    model = TeacherCourse
    extra = 1


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ("user",)
    list_select_related = ("user",)
    search_fields = ("user__email",)
    autocomplete_fields = ("user",)
    inlines = (TeacherCourseInline,)


@admin.register(ExternalReviewer)
class ExternalReviewerAdmin(admin.ModelAdmin):
    list_display = ("user", "institution")
    list_select_related = ("user",)
    search_fields = ("user__email", "institution")
    autocomplete_fields = ("user",)
