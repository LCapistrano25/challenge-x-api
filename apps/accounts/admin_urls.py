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
]
