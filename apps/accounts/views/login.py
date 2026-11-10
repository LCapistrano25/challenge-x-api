from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from apps.accounts.rules import ensure_password_login_allowed
from apps.accounts.serializers import LoginSerializer


class EmailRateThrottle(SimpleRateThrottle):
    """Limita tentativas por e-mail, não por IP: o campus sai por um IP só.

    A taxa fica em REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["login"].
    """

    scope = "login"

    def get_cache_key(self, request, view):
        email = str(request.data.get("email", "")).strip().lower()
        return (
            self.cache_format % {"scope": self.scope, "ident": email} if email else None
        )


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
    # Contra força bruta na senha de uma conta.
    throttle_classes = [EmailRateThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            request,
            username=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        ensure_password_login_allowed(user)
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
