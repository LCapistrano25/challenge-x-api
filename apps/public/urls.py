from django.urls import path

from apps.public.views import (
    ClosedEditionsListView,
    CurrentEditionView,
    EditionWinnersListView,
)

urlpatterns = [
    path("editions/current", CurrentEditionView.as_view(), name="current-edition"),
    path("editions", ClosedEditionsListView.as_view(), name="closed-editions"),
    path(
        "editions/<int:edition_id>/winners",
        EditionWinnersListView.as_view(),
        name="edition-winners",
    ),
]
