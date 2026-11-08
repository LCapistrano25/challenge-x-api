from django.urls import path

from apps.accounts import views

urlpatterns = [
    path("sessions/password", views.LoginView.as_view(), name="password-session"),
    path("logout", views.LogoutView.as_view(), name="logout"),
    path("me", views.MeView.as_view(), name="me"),
    path("csrf", views.CsrfView.as_view(), name="csrf"),
    path("students", views.StudentProfileView.as_view(), name="student-profile"),
]
