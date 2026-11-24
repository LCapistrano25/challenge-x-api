from django.urls import path

from apps.projects import views

urlpatterns = [
    path(
        "<int:project_id>/deliverables",
        views.ProjectDeliverablesView.as_view(),
        name="project-deliverables",
    ),
    path(
        "<int:project_id>/stages/<int:stage_id>/versions",
        views.ProjectStageVersionsView.as_view(),
        name="project-stage-versions",
    ),
]
