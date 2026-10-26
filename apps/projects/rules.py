from django.core.exceptions import ValidationError


def ensure_project_in_team_edition(project) -> None:
    """Equipe, desafio e categoria do projeto são todos da mesma edição (RN01)."""
    edition_id = project.edition_id
    if project.team.edition_id != edition_id:
        raise ValidationError({"edition": "A edição não é a da equipe."})
    if project.challenge_id and project.challenge.edition_id != edition_id:
        raise ValidationError({"challenge": "O desafio é de outra edição."})
    if project.category_id and project.category.edition_id != edition_id:
        raise ValidationError({"category": "A categoria é de outra edição."})


def ensure_project_complete(project) -> None:
    """Só entrega projeto com desafio, título e resumo (RF30, RF31, RF51)."""
    filled = {
        "challenge": project.challenge_id,
        "title": project.title,
        "summary": project.summary,
    }
    missing = {
        f: "Obrigatório para enviar a entrega." for f, v in filled.items() if not v
    }
    if missing:
        raise ValidationError(missing)


def ensure_item_matches_field(item) -> None:
    """O item responde a um campo da etapa da entrega, com o mesmo tipo (RF31)."""
    if item.field.stage_id != item.version.submission.stage_id:
        raise ValidationError({"field": "O campo é de outra etapa."})
    if item.field.kind != item.kind:
        raise ValidationError({"kind": "O tipo do item não é o tipo do campo."})


def ensure_stage_in_project_edition(submission) -> None:
    """A entrega só pode ser de uma etapa da edição do projeto (RF31)."""
    if submission.stage.edition_id != submission.project.edition_id:
        raise ValidationError({"stage": "A etapa é de outra edição."})
