from django.contrib.auth import authenticate, login, logout
from django.core import signing
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import (
    ConfirmationTokenExpired,
    EmailNotConfirmed,
    InstitutionalDomainDenied,
    InvalidConfirmationToken,
    InvalidCredentials,
    InvalidEmailDomain,
)
from apps.accounts.models import User
from apps.accounts.permissions import IsAdmin
from apps.accounts.rules import ensure_institutional_domain
from apps.accounts.serializers import (
    ConfirmEmailSerializer,
    LoginSerializer,
    RegisterSerializer,
)
from apps.accounts.use_cases.register_student import (
    EMAIL_CONFIRMATION_SALT,
    register_student,
)


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        register_student(
            actor=None,
            **serializer.validated_data,
            confirmation_url=request.build_absolute_uri(reverse("confirm-email")),
        )
        return Response(
            {"mensagem": "Cadastro iniciado. Confira o e-mail para confirmar a conta."},
            status=status.HTTP_201_CREATED,
        )


class ConfirmEmailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        serializer = ConfirmEmailSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        try:
            data = signing.loads(
                serializer.validated_data["token"],
                salt=EMAIL_CONFIRMATION_SALT,
                max_age=60 * 60 * 24,
            )
        except signing.SignatureExpired:
            raise ConfirmationTokenExpired() from None
        except signing.BadSignature:
            raise InvalidConfirmationToken() from None

        user = get_object_or_404(User, pk=data.get("user_id"))

        if user.email_confirmed:
            return Response({"mensagem": "E-mail já confirmado."})

        user.email_confirmed = True
        user.is_active = True
        user.save(update_fields=["email_confirmed", "is_active", "updated_at"])

        return Response({"mensagem": "E-mail confirmado com sucesso."})


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


class AdminAccessTestView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        return Response({"mensagem": "Acesso administrativo autorizado."})
