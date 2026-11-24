from django.urls import path

from apps.projects import views

urlpatterns = [
    path(
        "<int:version_id>/receipt",
        views.VersionReceiptView.as_view(),
        name="deliverable-version-receipt",
    ),
]
