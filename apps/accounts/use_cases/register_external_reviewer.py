"""UC11 — Cadastrar avaliador externo. RF11."""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import EmailTaken
from apps.accounts.models import ExternalReviewer, User
from apps.accounts.rules import ensure_actor_is_admin


@transaction.atomic
def register_external_reviewer(
    *, actor: User, name: str, email: str, password: str, institution: str = ""
) -> ExternalReviewer:
    """Cria o usuário avaliador externo com senha e o perfil dele (UC11, RF11).

    O e-mail não tem restrição de domínio; o vínculo com a edição é feito depois
    (P-05). Levanta NotAdminActor, EmailTaken ou ValidationError (senha fraca).
    """
    ensure_actor_is_admin(actor)

    if User.objects.filter(email__iexact=email).exists():
        raise EmailTaken()
    try:
        validate_password(password)
    except ValidationError as error:
        raise ValidationError({"password": error.messages}) from None

    try:
        user = User.objects.create_user(
            email=email,
            password=password,
            name=name,
            role=UserRole.EXTERNAL_REVIEWER,
        )
    except IntegrityError:
        # Dois cadastros simultâneos passam pela checagem acima; o banco desempata.
        raise EmailTaken() from None
    return ExternalReviewer.objects.create(user=user, institution=institution)
