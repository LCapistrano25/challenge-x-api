from django.urls import path

from apps.evaluations import views

urlpatterns = [
    path(
        "projects/<int:project_id>/stages/<int:stage_id>/evaluation",
        views.StageEvaluationView.as_view(),
        name="stage-evaluation",
    ),
]
