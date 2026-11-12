"""Invalidar o desafio do projeto. RF26 (regra 5), RF29. Chamado por teams."""

from django.db import transaction

from apps.accounts.models import User
from apps.projects.models import Project


@transaction.atomic
def invalidate_challenge(*, project: Project, actor: User | None = None) -> Project:
    """Tira o desafio do projeto; título, resumo e categoria ficam como estão.

    Quem decide invalidar (curso sem representante, RF26) é o chamador, por isso
    não há regra de líder nem de prazo aqui. Sem desafio, não faz nada. Ação do
    sistema recebe `actor=None`.
    """
    if project.challenge_id is None:
        return project

    project.challenge = None
    project.save(update_fields=["challenge", "updated_at"])
    return project
