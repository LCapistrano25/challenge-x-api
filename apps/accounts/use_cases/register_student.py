"""UC21 — Realizar autocadastro. RF19. Regras: RN02 do Administrador (domínios)."""

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core import signing
from django.core.mail import send_mail
from django.db import IntegrityError, transaction

from apps.accounts.enums import UserRole
from apps.accounts.models import User
from apps.accounts.rules import ensure_institutional_domain

EMAIL_CONFIRMATION_SALT = "email-confirmation"


class RegistrationRejected(Exception):
    pass


class ConfirmationEmailFailed(Exception):
    pass


@transaction.atomic
def register_student(
    *,
    email: str,
    password: str,
    registration_number: str,
    course: str,
    term: int,
    confirmation_url: str,
) -> User:
    """Cria o acadêmico inativo e envia o link de confirmação de e-mail.

    Levanta InvalidEmailDomain, DomainRoleMismatch, RegistrationRejected,
    ValidationError (senha fraca) ou ConfirmationEmailFailed.
    """
    ensure_institutional_domain(email, UserRole.STUDENT)

    # Mensagem genérica: não revela se o e-mail ou a matrícula já existem.
    rejected = "Não foi possível realizar o cadastro com esses dados."
    if (
        User.objects.filter(email__iexact=email).exists()
        or User.objects.filter(registration_number=registration_number).exists()
    ):
        raise RegistrationRejected(rejected)

    validate_password(password)

    try:
        user = User.objects.create_user(
            email=email,
            password=password,
            role=UserRole.STUDENT,
            registration_number=registration_number,
            course=course,
            term=term,
            is_active=False,
            email_confirmed=False,
        )
    except IntegrityError:
        # Dois cadastros simultâneos passam pela checagem acima; o banco desempata.
        raise RegistrationRejected(rejected) from None

    token = signing.dumps({"user_id": user.pk}, salt=EMAIL_CONFIRMATION_SALT)

    try:
        send_mail(
            subject="Confirme seu e-mail - Desafio X",
            message=(
                f"Para confirmar seu e-mail, acesse: {confirmation_url}?token={token}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception as error:
        # A exceção desfaz a transação: não fica conta pendente sem e-mail.
        raise ConfirmationEmailFailed(
            "Não foi possível enviar o e-mail de confirmação."
        ) from error

    return user
