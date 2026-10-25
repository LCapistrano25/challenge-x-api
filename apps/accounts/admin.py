from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin

from apps.accounts.enums import UserRole
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
    list_display = ("email", "name", "role", "email_confirmed", "is_active")
    list_filter = ("role", "email_confirmed", "is_staff", "is_active")
    search_fields = ("email", "name")

    # Acesso ao painel vem do papel ADMIN (User.save); grupos não são usados.
    readonly_fields = ("is_staff", "is_superuser")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Dados pessoais", {"fields": ("name",)}),
        ("Perfil", {"fields": ("role", "email_confirmed")}),
        ("Acesso", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Datas importantes", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "name",
                    "role",
                    "password1",
                    "password2",
                    "is_active",
                ),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change:
            return
        # O papel precisa do perfil; o do aluno exige matrícula e curso.
        if obj.role == UserRole.TEACHER:
            Teacher.objects.get_or_create(user=obj)
        elif obj.role == UserRole.EXTERNAL_REVIEWER:
            ExternalReviewer.objects.get_or_create(user=obj)
        elif obj.role == UserRole.STUDENT:
            messages.warning(
                request,
                "Complete o cadastro em Acadêmicos (matrícula, curso e período).",
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
