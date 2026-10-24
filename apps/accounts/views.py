from django.contrib.auth import authenticate, login, logout
from django.core import signing
from django.core.exceptions import ValidationError
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
from apps.accounts.models import User
from apps.accounts.permissions import IsAdmin
from apps.accounts.rules import (
    DomainRoleMismatch,
    InvalidEmailDomain,
    ensure_institutional_domain,
)
from apps.accounts.use_cases.register_student import (
    EMAIL_CONFIRMATION_SALT,
    ConfirmationEmailFailed,
    RegistrationRejected,
    register_student,
)


def error(message, status_code):
    return Response({"erro": message}, status=status_code)


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        data = request.data

        email = str(data.get("email", "")).strip().lower()
        password = data.get("senha")
        registration_number = str(data.get("matricula", "")).strip()
        course = str(data.get("curso", "")).strip()
        term = data.get("periodo")

        if not all([email, password, registration_number, course, term]):
            return error(
                "Informe e-mail, senha, matrícula, curso e período.",
                status.HTTP_400_BAD_REQUEST,
            )

        try:
            term = int(term)
            if term < 1:
                raise ValueError
        except (TypeError, ValueError):
            return error(
                "O período deve ser um número inteiro positivo.",
                status.HTTP_400_BAD_REQUEST,
            )

        try:
            register_student(
                email=email,
                password=password,
                registration_number=registration_number,
                course=course,
                term=term,
                confirmation_url=request.build_absolute_uri(reverse("confirm-email")),
            )
        except (InvalidEmailDomain, RegistrationRejected) as exc:
            return error(str(exc), status.HTTP_400_BAD_REQUEST)
        except DomainRoleMismatch:
            # O cadastro público é exclusivo para acadêmicos.
            return error(
                "Este perfil não pode realizar cadastro público.",
                status.HTTP_403_FORBIDDEN,
            )
        except ValidationError as exc:
            return error(list(exc.messages), status.HTTP_400_BAD_REQUEST)
        except ConfirmationEmailFailed as exc:
            return error(str(exc), status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(
            {"mensagem": "Cadastro iniciado. Confira o e-mail para confirmar a conta."},
            status=status.HTTP_201_CREATED,
        )


class ConfirmEmailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        token = request.query_params.get("token")

        if not token:
            return error("Token não informado.", status.HTTP_400_BAD_REQUEST)

        try:
            data = signing.loads(
                token,
                salt=EMAIL_CONFIRMATION_SALT,
                max_age=60 * 60 * 24,
            )
        except signing.SignatureExpired:
            return error("O link de confirmação expirou.", status.HTTP_400_BAD_REQUEST)
        except signing.BadSignature:
            return error("Token de confirmação inválido.", status.HTTP_400_BAD_REQUEST)

        user = get_object_or_404(User, pk=data.get("user_id"))

        if user.email_confirmed:
            return Response({"mensagem": "E-mail já confirmado."})

        user.email_confirmed = True
        user.is_active = True
        user.save(update_fields=["email_confirmed", "is_active"])

        return Response({"mensagem": "E-mail confirmado com sucesso."})


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()
        password = request.data.get("senha")

        if not email or not password:
            return error("Informe e-mail e senha.", status.HTTP_400_BAD_REQUEST)

        # authenticate() recusa usuário inativo, e o aluno recém-cadastrado é inativo
        # até confirmar o e-mail: sem esta checagem ele veria "Credenciais inválidas".
        pending = User.objects.filter(
            email=email, role=UserRole.STUDENT, is_active=False, email_confirmed=False
        ).first()
        if pending and pending.check_password(password):
            return error(
                "Confirme seu e-mail antes de entrar.", status.HTTP_403_FORBIDDEN
            )

        user = authenticate(request, username=email, password=password)

        if user is None:
            return error("Credenciais inválidas.", status.HTTP_401_UNAUTHORIZED)

        if user.role == UserRole.STUDENT and not user.email_confirmed:
            return error(
                "Confirme seu e-mail antes de entrar.", status.HTTP_403_FORBIDDEN
            )

        # Revalida o domínio institucional, exceto para administradores.
        if user.role != UserRole.ADMIN:
            try:
                ensure_institutional_domain(user.email, user.role)
            except InvalidEmailDomain:
                return error(
                    "Domínio institucional não autorizado.",
                    status.HTTP_403_FORBIDDEN,
                )
            except DomainRoleMismatch as exc:
                return error(str(exc), status.HTTP_403_FORBIDDEN)

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
