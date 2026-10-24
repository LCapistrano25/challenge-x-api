from django.urls import path

from apps.accounts import views

urlpatterns = [
    path("auth/register", views.RegisterView.as_view(), name="register"),
    path("auth/confirm-email", views.ConfirmEmailView.as_view(), name="confirm-email"),
    path("auth/login", views.LoginView.as_view(), name="login"),
    path("auth/logout", views.LogoutView.as_view(), name="logout"),
    path("auth/me", views.MeView.as_view(), name="me"),
    path("auth/csrf", views.CsrfView.as_view(), name="csrf"),
    path(
        "admin/teste-acesso",
        views.AdminAccessTestView.as_view(),
        name="admin-access-test",
    ),
]
