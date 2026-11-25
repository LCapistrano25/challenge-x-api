from typing import Any

from apps.core.models import Course


def list_public_courses() -> list[dict[str, Any]]:
    """
    Lista os cursos para o público geral.
    Regra: Retorna APENAS os cursos marcados como ativos.
    """
    # Filtra por active=True e devolve os dados puros
    return list(Course.objects.filter(active=True).values("id", "name"))
