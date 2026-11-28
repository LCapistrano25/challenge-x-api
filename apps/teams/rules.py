from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.editions.enums import EditionStatus, StageKind
from apps.editions.models import Stage

# Saída que deixa a equipe abaixo do mínimo nas últimas horas do prazo dá tempo extra
# para repor a vaga (RF22, RF26). shortcut: valores fixos; mover para a edição se o
# regulamento variar por ano.
FORMATION_LAST_HOURS = timedelta(hours=24)
FORMATION_EXTENSION = timedelta(hours=48)


def get_open_formation_stage(edition, now=None):
    """Etapa de formação em andamento na edição, ou None (RF22).

    Só edição publicada forma equipes: em configuração os limites ainda mudam
    (RF48) e a validação deles não olha equipes existentes.
    """
    now = now or timezone.now()
    return Stage.objects.filter(
        edition=edition,
        edition__status=EditionStatus.PUBLISHED,
        kind=StageKind.FORMATION,
        starts_at__lte=now,
        ends_at__gte=now,
    ).first()


def is_formation_open_for_team(team, now=None) -> bool:
    """Prazo de formação aberto para a equipe: a etapa ou a janela extra dela."""
    now = now or timezone.now()
    extended = team.formation_extended_until
    return get_open_formation_stage(team.edition, now) is not None or (
        extended is not None
        and now <= extended
        and team.edition.status == EditionStatus.PUBLISHED
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
    return [message for _, message in _unmet_requirements(team)]


def unmet_requirement_codes(team) -> list[str]:
    """Os mesmos requisitos com os códigos do enum IncompleteRequirement do contrato.

    Acima do máximo de integrantes não tem código no contrato e fica de fora.
    """
    codes = []
    for code, _ in _unmet_requirements(team):
        if code and code not in codes:
            codes.append(code)
    return codes


def _unmet_requirements(team) -> list[tuple[str | None, str]]:
    edition = team.edition
    unmet = []
    members = team.members.filter(active=True).count()
    if members < edition.min_members:
        unmet.append(
            ("MIN_MEMBERS", f"{members} integrantes; o mínimo é {edition.min_members}.")
        )
    if members > edition.max_members:
        unmet.append(
            (None, f"{members} integrantes; o máximo é {edition.max_members}.")
        )
    # Lê o projeto pela relação reversa: teams não importa de projects (cadeia).
    project = getattr(team, "project", None)
    if project is None or not project.challenge_id:
        unmet.append(("CHALLENGE_NOT_SELECTED", "Sem desafio escolhido."))
    if project is None or not project.title:
        unmet.append(("PROJECT_DATA_MISSING", "Projeto sem título."))
    if project is None or not project.summary:
        unmet.append(("PROJECT_DATA_MISSING", "Projeto sem resumo."))
    # Categoria obrigatória (D-06); o contrato a conta como dado do projeto.
    if project is None or not project.category_id:
        unmet.append(("PROJECT_DATA_MISSING", "Projeto sem categoria."))
    return unmet
