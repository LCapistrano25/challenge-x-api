from django.urls import path

from apps.evaluations import views

urlpatterns = [
    path(
        "evaluator/finalists",
        views.FinalistListView.as_view(),
        name="finalists",
    ),
    path(
        "evaluator/finalists/<int:project_id>/final-evaluation",
        views.FinalEvaluationView.as_view(),
        name="final-evaluation",
    ),
    path(
        "admin/editions/<int:edition_id>/final-form",
        views.FinalFormView.as_view(),
        name="final-form",
    ),
    path(
        "admin/editions/<int:edition_id>/final-form/publish",
        views.FinalFormPublishView.as_view(),
        name="final-form-publish",
    ),
    path(
        "admin/evaluations/<int:evaluation_id>/rectifications",
        views.RectificationCreateView.as_view(),
        name="rectification-create",
    ),
    path(
        "projects/<int:project_id>/scores",
        views.ProjectScoresView.as_view(),
        name="project-scores",
    ),
    path(
        "teacher/projects",
        views.TeacherProjectListView.as_view(),
        name="teacher-projects",
    ),
    path(
        "projects/<int:project_id>/stages/<int:stage_id>/evaluation",
        views.StageEvaluationView.as_view(),
        name="stage-evaluation",
    ),
]
