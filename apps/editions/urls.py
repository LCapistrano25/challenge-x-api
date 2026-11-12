from django.urls import path

from apps.editions import views

urlpatterns = [
    path("editions", views.EditionListView.as_view(), name="edition-list"),
    path(
        "editions/<int:edition_id>",
        views.EditionDetailView.as_view(),
        name="edition-detail",
    ),
]
