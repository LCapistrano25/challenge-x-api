from django.db.models import QuerySet

from apps.accounts.rules import ensure_actor_is_admin
from apps.core.models import Course


def list_courses(
    *,
    actor,
    search: str | None = None,
    active: bool | None = None,
) -> QuerySet[Course]:
    """Lista todos os cursos cadastrados (administração), com filtros opcionais."""
    ensure_actor_is_admin(actor)

    qs = Course.objects.all()
    if active is not None:
        qs = qs.filter(active=active)
    if search:
        term = search.strip()
        if term:
            qs = qs.filter(name__icontains=term)
    return qs
