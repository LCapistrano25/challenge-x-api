from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError, transaction
from apps.accounts.enums import UserRole
from apps.accounts.models import ExternalReviewer, User
from apps.accounts.exceptions import NotAdminActor, RegistrationRejected


@transaction.atomic
def register_external_reviewer(*, actor: User, name: str, email: str, password: str, institution: str) -> ExternalReviewer:

    if actor.role != UserRole.ADMIN:
        raise NotAdminActor()
    
    rejected = "Não foi possível realizar o cadastro com esses dados."

    if User.objects.filter(email__iexact=email).exists():
        raise RegistrationRejected(rejected)
    
    validate_password(password)

    try:
        user = User.objects.create_user(
            name=name,
            email=email,
            password=password,
            role=UserRole.EXTERNAL_REVIEWER,
            is_active=True,
            email_confirmed=False,
        )

        external_review = ExternalReviewer.objects.create(
            user=user,
            institution=institution
        )

    except IntegrityError:
        raise RegistrationRejected(rejected) from None

    return external_review
