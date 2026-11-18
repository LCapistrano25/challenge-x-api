from django.urls import path

from apps.projects import views

urlpatterns = [
    path(
        "<int:item_id>/file",
        views.DeliverableItemFileView.as_view(),
        name="deliverable-item-file",
    ),
]
