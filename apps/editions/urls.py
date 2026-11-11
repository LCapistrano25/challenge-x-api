from django.urls import path

from apps.editions import views

urlpatterns = [
    path(
        "<int:edition_id>/evaluators",
        views.EditionReviewView.as_view(),
        name="edition-evaluators",
    ),
    path(
        "<int:edition_id>/evaluators/<int:evaluator_id>",
        views.EditionReviewDetailView.as_view(),
        name="edition-evaluator",
    ),
]
