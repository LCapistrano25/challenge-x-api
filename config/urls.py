"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
Including another URLconf
    1. Import the include() function: from django.urls import include, path, re_path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path, re_path

from config import api_docs
from config.exception import api_not_found

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/docs/", api_docs.swagger_ui, name="api-docs"),
    path("api/docs/openapi.yaml", api_docs.openapi_spec, name="api-docs-spec"),
    path("api/", include("apps.core.urls")),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/admin/", include("apps.accounts.admin_urls")),
    path("api/", include("apps.teams.urls")),
    path("api/teams/", include("apps.projects.urls")),
    path("api/admin/teams/", include("apps.projects.admin_urls")),
    path("api/", include("apps.evaluations.urls")),
    path("api/projects/", include("apps.projects.delivery_urls")),
    path("api/deliverable-versions/", include("apps.projects.version_urls")),
    path("api/deliverable-items/", include("apps.projects.file_urls")),
    path("api/admin/", include("apps.editions.urls")),
    path("api/admin/editions/", include("apps.results.urls")),
    path("api/public/", include("apps.public.urls")),
    path("", include("apps.notifications.urls")),
    path("api/support/", include("apps.support.urls")),
    path("api/admin/support/", include("apps.support.admin_urls")),
]

# Por último: rota da API que não casou (inclusive parâmetro de caminho inválido)
# sai em JSON também com DEBUG=True, quando o Django ignoraria o handler404.
urlpatterns.append(re_path(r"^api/", api_not_found))

handler404 = "config.exception.api_not_found"
