from django.urls import path

from apps.editions import views

urlpatterns = [
    path(
        "criteria/<int:criterion_id>",
        views.CriterionDetailView.as_view(),
        name="criterion-detail",
    ),
    path(
        "categories/<int:category_id>",
        views.CategoryDetailView.as_view(),
        name="category-detail",
    ),
    path(
        "challenges/<int:challenge_id>",
        views.ChallengeDetailView.as_view(),
        name="challenge-detail",
    ),
    path(
        "editions/<int:edition_id>/criteria",
        views.EditionCriteriaView.as_view(),
        name="edition-criteria",
    ),
    path("editions", views.EditionListView.as_view(), name="edition-list"),
    path(
        "editions/<int:edition_id>/publish",
        views.EditionPublishView.as_view(),
        name="edition-publish",
    ),
    path(
        "editions/<int:edition_id>",
        views.EditionDetailView.as_view(),
        name="edition-detail",
    ),
    path(
        "editions/<int:edition_id>/categories",
        views.EditionCategoriesView.as_view(),
        name="edition-categories",
    ),
    path(
        "editions/<int:edition_id>/challenges",
        views.EditionChallengesView.as_view(),
        name="edition-challenges",
    ),
    path(
        "editions/<int:edition_id>/sdgs",
        views.EditionSdgsView.as_view(),
        name="edition-sdgs",
    ),
    path(
        "editions/<int:edition_id>/evaluators",
        views.EditionReviewView.as_view(),
        name="edition-evaluators",
    ),
    path(
        "editions/<int:edition_id>/evaluators/<int:evaluator_id>",
        views.EditionReviewDetailView.as_view(),
        name="edition-evaluator",
    ),
]
