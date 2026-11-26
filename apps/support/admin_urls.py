from django.urls import path

from apps.support.views import AdminTicketDetailView, AdminTicketListView

urlpatterns = [
    path(
        "tickets",
        AdminTicketListView.as_view(),
        name="admin-support-ticket-list",
    ),
    path(
        "tickets/<uuid:ticket_id>",
        AdminTicketDetailView.as_view(),
        name="admin-support-ticket-detail",
    ),
]
