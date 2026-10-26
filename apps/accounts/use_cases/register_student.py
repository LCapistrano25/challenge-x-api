"""UC21 — Realizar autocadastro. RF19. Regras: RN02 do Administrador (domínios)."""

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core import signing
from django.core.mail import send_mail
from django.db import IntegrityError, transaction

from apps.accounts.enums import UserRole
from apps.accounts.models import Student, User
from apps.accounts.rules import ensure_institutional_domain
from apps.core.models import Course

EMAIL_CONFIRMATION_SALT = "email-confirmation"


class RegistrationRejected(Exception):
    pass


class ConfirmationEmailFailed(Exception):
    pass


@transaction.atomic
def register_student(
    *,
    actor: User | None,
    email: str,
    password: str,
    registration_number: str,
    course_id: int,
    term: int,
    confirmation_url: str,
) -> User:
    """Cria o acadêmico inativo e envia o link de confirmação de e-mail.

    actor é None no autocadastro (quem age ainda não tem conta).

    Levanta InvalidEmailDomain, DomainRoleMismatch, RegistrationRejected,
    ValidationError (senha fraca) ou ConfirmationEmailFailed.
    """
    ensure_institutional_domain(email, UserRole.STUDENT)

    course = Course.objects.filter(pk=course_id, active=True).first()
    if course is None:
        raise RegistrationRejected("Curso inválido.")
    if term > course.term_count:
        raise RegistrationRejected(
            f"O período deve estar entre 1 e {course.term_count}."
        )

    # Conta pendente (link perdido ou expirado) é refeita: senão o aluno não
    # consegue nem cadastrar de novo nem entrar. O Student some junto (CASCADE).
    User.objects.filter(
        email__iexact=email,
        role=UserRole.STUDENT,
        is_active=False,
        email_confirmed=False,
    ).delete()

    # Mensagem genérica: não revela se o e-mail ou a matrícula já existem.
    rejected = "Não foi possível realizar o cadastro com esses dados."
    if (
        User.objects.filter(email__iexact=email).exists()
        or Student.objects.filter(registration_number=registration_number).exists()
    ):
        raise RegistrationRejected(rejected)

    validate_password(password)

    try:
        user = User.objects.create_user(
            email=email,
            password=password,
            role=UserRole.STUDENT,
            is_active=False,
            email_confirmed=False,
        )
        Student.objects.create(
            user=user,
            registration_number=registration_number,
            course=course,
            term=term,
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
