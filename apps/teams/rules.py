from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.editions.enums import StageKind
from apps.editions.models import Stage

# Saída que deixa a equipe abaixo do mínimo nas últimas horas do prazo dá tempo extra
# para repor a vaga (RF22, RF26). shortcut: valores fixos; mover para a edição se o
# regulamento variar por ano.
FORMATION_LAST_HOURS = timedelta(hours=24)
FORMATION_EXTENSION = timedelta(hours=48)


def get_open_formation_stage(edition, now=None):
    """Etapa de formação em andamento na edição, ou None (RF22)."""
    now = now or timezone.now()
    return Stage.objects.filter(
        edition=edition,
        kind=StageKind.FORMATION,
        starts_at__lte=now,
        ends_at__gte=now,
    ).first()


def is_formation_open_for_team(team, now=None) -> bool:
    """Prazo de formação aberto para a equipe: a etapa ou a janela extra dela."""
    now = now or timezone.now()
    extended = team.formation_extended_until
    return get_open_formation_stage(team.edition, now) is not None or (
        extended is not None and now <= extended
    )


def ensure_member_edition_matches_team(team, edition_id: int) -> None:
    """Exige que a edição repetida no integrante seja a da equipe."""
    if team.edition_id != edition_id:
        raise ValidationError({"edition": "A edição não é a da equipe."})


def compute_unmet_requirements(team) -> list[str]:
    """Requisitos que a equipe não cumpre; vazio quando está completa (RF51, P-23).

    Calculado na hora, sem gravar: a `situation` congelada no fim do prazo de
    formação diz se está incompleta, esta lista diz por quê.
    """
    edition = team.edition
    unmet = []
    members = team.members.filter(active=True).count()
    if members < edition.min_members:
        unmet.append(f"{members} integrantes; o mínimo é {edition.min_members}.")
    if members > edition.max_members:
        unmet.append(f"{members} integrantes; o máximo é {edition.max_members}.")
    # Lê o projeto pela relação reversa: teams não importa de projects (cadeia).
    project = getattr(team, "project", None)
    if project is None or not project.challenge_id:
        unmet.append("Sem desafio escolhido.")
    if project is None or not project.title:
        unmet.append("Projeto sem título.")
    if project is None or not project.summary:
        unmet.append("Projeto sem resumo.")
    return unmet
