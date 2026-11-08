from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import (
    EmailNotConfirmed,
    InstitutionalDomainDenied,
    InvalidCredentials,
    InvalidEmailDomain,
)
from apps.accounts.models import User
from apps.accounts.rules import ensure_institutional_domain
from apps.accounts.serializers import LoginSerializer


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        password = serializer.validated_data["senha"]

        # authenticate() recusa usuário inativo, e o aluno recém-cadastrado é inativo
        # até confirmar o e-mail: sem esta checagem ele veria "Credenciais inválidas".
        pending = User.objects.filter(
            email=email, role=UserRole.STUDENT, is_active=False, email_confirmed=False
        ).first()
        if pending and pending.check_password(password):
            raise EmailNotConfirmed()

        user = authenticate(request, username=email, password=password)

        if user is None:
            raise InvalidCredentials()

        if user.role == UserRole.STUDENT and not user.email_confirmed:
            raise EmailNotConfirmed()

        # Revalida o domínio institucional, exceto para administradores.
        # DomainRoleMismatch já sai como 403; o domínio inativo, no login, também.
        if user.role != UserRole.ADMIN:
            try:
                ensure_institutional_domain(user.email, user.role)
            except InvalidEmailDomain:
                raise InstitutionalDomainDenied() from None

        login(request, user)

        return Response(
            {
                "mensagem": "Login realizado com sucesso.",
                "email": user.email,
                "perfil": user.role,
            }
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "email": request.user.email,
                "perfil": request.user.role,
                "email_confirmado": request.user.email_confirmed,
            }
        )


class CsrfView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"csrfToken": get_token(request)})
