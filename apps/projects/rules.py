from django.core.exceptions import ValidationError


def ensure_project_in_team_edition(project) -> None:
    """Equipe, desafio e categoria do projeto são todos da mesma edição (RN01)."""
    edition_id = project.edition_id
    if project.team.edition_id != edition_id:
        raise ValidationError({"edition": "A edição não é a da equipe."})
    if project.challenge.edition_id != edition_id:
        raise ValidationError({"challenge": "O desafio é de outra edição."})
    if project.category_id and project.category.edition_id != edition_id:
        raise ValidationError({"category": "A categoria é de outra edição."})


def ensure_stage_in_project_edition(submission) -> None:
    """A entrega só pode ser de uma etapa da edição do projeto (RF31)."""
    if submission.stage.edition_id != submission.project.edition_id:
        raise ValidationError({"stage": "A etapa é de outra edição."})
