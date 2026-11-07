from django.urls import path

from apps.accounts import views

urlpatterns = [
    path("register", views.RegisterView.as_view(), name="register"),
    path("confirm-email", views.ConfirmEmailView.as_view(), name="confirm-email"),
    path("login", views.LoginView.as_view(), name="login"),
    path("logout", views.LogoutView.as_view(), name="logout"),
    path("me", views.MeView.as_view(), name="me"),
    path("csrf", views.CsrfView.as_view(), name="csrf"),
    path(
        "admin/teste-acesso",
        views.AdminAccessTestView.as_view(),
        name="admin-access-test",
    ),
]
