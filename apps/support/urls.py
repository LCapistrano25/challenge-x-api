from django.urls import path

from apps.support.views import MyTicketDetailView, MyTicketListCreateView

urlpatterns = [
    path("tickets", MyTicketListCreateView.as_view(), name="support-ticket-list"),
    path(
        "tickets/<uuid:ticket_id>",
        MyTicketDetailView.as_view(),
        name="support-ticket-detail",
    ),
]
