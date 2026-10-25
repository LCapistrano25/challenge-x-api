from django.core.exceptions import ValidationError


def ensure_member_edition_matches_team(team, edition_id: int) -> None:
    """Exige que a edição repetida no integrante seja a da equipe."""
    if team.edition_id != edition_id:
        raise ValidationError({"edition": "A edição não é a da equipe."})
