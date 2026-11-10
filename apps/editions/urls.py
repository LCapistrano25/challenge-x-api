# apps/editions/urls.py
from django.urls import path

from apps.editions import views

urlpatterns = [
    path(
        "<int:edition_id>/evaluators",
        views.EditionReviewView.as_view(),
        name="edition-evaluators",
    ),
]
