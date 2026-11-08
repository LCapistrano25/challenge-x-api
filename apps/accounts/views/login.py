from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import InvalidCredentials
from apps.accounts.rules import ensure_reviewer_in_current_edition
from apps.accounts.serializers import LoginSerializer

# Aluno e professor entram pela Microsoft (RF18, RF36).
PASSWORD_ROLES = {UserRole.ADMIN, UserRole.EXTERNAL_REVIEWER}


def user_data(user):
    """Corpo do login e do /me: a sessão vai no cookie, não na resposta."""
    return {
        "user_id": user.pk,
        "name": user.name,
        "email": user.email,
        "role": user.role,
    }


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    """Sessão com e-mail e senha para administrador e avaliador externo (RF01, RF41)."""

    permission_classes = [AllowAny]
    authentication_classes = []
    # Limita tentativas por IP contra força bruta na senha (taxa em REST_FRAMEWORK).
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # authenticate() já recusa usuário inativo. Todo motivo sai como o mesmo 401,
        # sem dizer qual campo está errado.
        user = authenticate(
            request,
            username=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if user is None or user.role not in PASSWORD_ROLES:
            raise InvalidCredentials()
        if user.role == UserRole.EXTERNAL_REVIEWER:
            ensure_reviewer_in_current_edition(user)

        login(request, user)

        return Response(user_data(user))


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(user_data(request.user))


class CsrfView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"csrfToken": get_token(request)})
