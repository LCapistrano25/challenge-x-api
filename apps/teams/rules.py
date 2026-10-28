from django.core.exceptions import ValidationError


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
