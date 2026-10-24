from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.accounts.models import EmailDomain, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    ordering = ("email",)
    list_display = (
        "email",
        "role",
        "registration_number",
        "course",
        "term",
        "email_confirmed",
        "is_staff",
        "is_active",
    )
    list_filter = ("role", "email_confirmed", "is_staff", "is_active")
    search_fields = ("email", "registration_number", "course")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Informações acadêmicas",
            {
                "fields": (
                    "role",
                    "registration_number",
                    "course",
                    "term",
                    "email_confirmed",
                )
            },
        ),
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
                    "registration_number",
                    "course",
                    "term",
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
