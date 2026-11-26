from django.urls import path

from apps.notifications.views import NotificationListView, NotificationReadView

urlpatterns = [
    path("api/notifications", NotificationListView.as_view(), name="notification-list"),
    path(
        "api/notifications/<uuid:notification_id>/read",
        NotificationReadView.as_view(),
        name="notification-read",
    ),
]
