from django.urls import path

from apps.results import views

urlpatterns = [
    path(
        "<int:edition_id>/results/calculate",
        views.ResultsCalculateView.as_view(),
        name="results-calculate",
    ),
    path(
        "<int:edition_id>/finalists",
        views.FinalistsView.as_view(),
        name="results-finalists",
    ),
    path(
        "<int:edition_id>/awards/calculate",
        views.AwardsCalculateView.as_view(),
        name="results-awards-calculate",
    ),
    path(
        "<int:edition_id>/results/homologate",
        views.ResultsApproveView.as_view(),
        name="results-homologate",
    ),
]
