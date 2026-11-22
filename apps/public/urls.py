from django.urls import path

from apps.public.views import (
    ClosedEditionsListView,
    CurrentEditionView,
    EditionWinnersListView,
    PublicProjectDetailView,
    PublicProjectListView,
)

urlpatterns = [
    path("editions/current", CurrentEditionView.as_view(), name="current-edition"),
    path("editions", ClosedEditionsListView.as_view(), name="closed-editions"),
    path(
        "editions/<int:edition_id>/winners",
        EditionWinnersListView.as_view(),
        name="edition-winners",
    ),
    path("projects", PublicProjectListView.as_view(), name="public-projects"),
    path(
        "projects/<int:project_id>",
        PublicProjectDetailView.as_view(),
        name="public-project-detail",
    ),
]
