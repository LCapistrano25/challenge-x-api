from django.urls import path
from apps.core.views import CourseCreateView

urlpatterns = [
    # Isso vai responder no caminho /api/admin/courses
    path("admin/courses", CourseCreateView.as_view(), name="create-course"),
]