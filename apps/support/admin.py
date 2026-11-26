from django.contrib import admin

from apps.support.models import SupportTicket


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "requester",
        "status",
        "priority",
        "assigned_to",
        "created_at",
        "resolved_at",
    )
    list_filter = ("status", "priority")
    search_fields = ("title", "description", "requester__name", "requester__email")
    readonly_fields = ("id", "created_at", "updated_at")
