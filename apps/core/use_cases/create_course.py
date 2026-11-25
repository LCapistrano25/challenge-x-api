from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.rules import ensure_actor_is_admin
from apps.core.exceptions import CourseNameTaken
from apps.core.models import Course


@transaction.atomic
def create_course(
    *,
    actor,
    name: str,
    term_count: int,
    active: bool = True,
) -> Course:
    """Cadastra um novo curso (RF03)."""
    ensure_actor_is_admin(actor)

    clean_name = (name or "").strip()
    if not clean_name:
        raise ValidationError({"name": "Informe o nome do curso."})

    if term_count not in (8, 10):
        raise ValidationError(
            {"term_count": "O curso deve ter exatamente 8 ou 10 períodos."}
        )

    if Course.objects.filter(name__iexact=clean_name).exists():
        raise CourseNameTaken()

    return Course.objects.create(
        name=clean_name,
        term_count=term_count,
        active=active,
    )
