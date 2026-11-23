from django.urls import path

from apps.accounts import views

urlpatterns = [
    path(
        "email-domains",
        views.EmailDomainListCreateView.as_view(),
        name="admin-email-domains",
    ),
    path(
        "email-domains/<int:domain_id>",
        views.EmailDomainDetailView.as_view(),
        name="admin-email-domain-detail",
    ),
    path("students", views.StudentListView.as_view(), name="admin-students"),
    path(
        "students/<int:user_id>",
        views.StudentDetailView.as_view(),
        name="admin-student-detail",
    ),
    path(
        "students/<int:user_id>/status",
        views.StudentStatusView.as_view(),
        name="admin-student-status",
    ),
    path("teachers", views.TeacherListView.as_view(), name="admin-teachers"),
    path(
        "teachers/<int:user_id>",
        views.TeacherDetailView.as_view(),
        name="admin-teacher-detail",
    ),
    path(
        "teachers/<int:user_id>/status",
        views.TeacherStatusView.as_view(),
        name="admin-teacher-status",
    ),
    path(
        "external-evaluators",
        views.ExternalReviewerListView.as_view(),
        name="admin-external-evaluators",
    ),
    path(
        "external-evaluators/<int:user_id>",
        views.ExternalReviewerDetailView.as_view(),
        name="admin-external-evaluator-detail",
    ),
    path(
        "external-evaluators/<int:user_id>/status",
        views.ExternalReviewerStatusView.as_view(),
        name="admin-external-evaluator-status",
    ),
]
