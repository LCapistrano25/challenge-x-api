from apps.core.models import Course
from apps.editions.models import Category, Challenge
from apps.projects.models import Submission, SubmissionVersion


def get_team_courses(team):
    """Cursos dos integrantes ativos da equipe, sem repetição (RF29)."""
    return Course.objects.filter(
        students__memberships__team=team, students__memberships__active=True
    ).distinct()


def get_eligible_challenges(team):
    """Desafios ativos da edição, de cursos de integrantes ativos (RF29)."""
    return (
        Challenge.objects.filter(
            edition_id=team.edition_id,
            active=True,
            course__in=get_team_courses(team),
        )
        .select_related("course", "sdg")
        .order_by("id")
    )


def get_active_categories(edition):
    """Categorias ativas da edição (RF50)."""
    return Category.objects.filter(edition=edition, active=True).order_by("name")


def get_submission_deadline(project, stage):
    """Prazo de entrega da equipe: a prorrogação, se houver, senão o da etapa."""
    extension = project.deadline_extensions.filter(stage=stage).first()
    return extension.ends_at if extension else stage.ends_at


def get_valid_version(submission: Submission) -> SubmissionVersion | None:
    """Versão que vale: a de maior número enviada até o prazo da equipe na etapa.

    Nenhuma versão no prazo = entrega não enviada (None).
    """
    deadline = get_submission_deadline(submission.project, submission.stage)

    return (
        submission.versions.filter(submitted_at__lte=deadline)
        .order_by("-number")
        .first()
    )
