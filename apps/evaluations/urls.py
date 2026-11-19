from django.urls import path

from apps.evaluations import views

urlpatterns = [
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
