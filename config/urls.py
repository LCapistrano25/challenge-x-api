from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.core.urls")),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/teams/", include("apps.projects.urls")),
    path("api/admin/editions/", include("apps.editions.urls")),
    path("api/", include("apps.teams.urls")),
]
