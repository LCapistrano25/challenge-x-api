from django.urls import path

from apps.core.views import (
    CourseCreateView,
    CourseDetailView,
    CoursePublicListView,
    SdgAdminDetailView,
    SdgAdminListCreateView,
    SdgPublicListView,
)

urlpatterns = [
    # Rotas de Cursos
    path("admin/courses", CourseCreateView.as_view(), name="create-course"),
    path(
        "admin/courses/<int:course_id>",
        CourseDetailView.as_view(),
        name="detail-course",
    ),
    path("courses", CoursePublicListView.as_view(), name="public-courses"),
    # Rotas de ODS
    path("sdgs", SdgPublicListView.as_view(), name="public-sdgs"),
    path("admin/sdgs", SdgAdminListCreateView.as_view(), name="admin-sdgs"),
    path("admin/sdgs/<int:sdg_id>", SdgAdminDetailView.as_view(), name="detail-sdg"),
]
