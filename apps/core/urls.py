from django.urls import path
from apps.core.views import CourseCreateView, CourseDetailView

urlpatterns = [
    # Isso vai responder no caminho /api/admin/courses (GET e POST)
    path("admin/courses", CourseCreateView.as_view(), name="create-course"),
    
    # Isso vai responder no caminho /api/admin/courses/{id} (PATCH e futuramente DELETE)
    path("admin/courses/<int:course_id>", CourseDetailView.as_view(), name="detail-course"),
]