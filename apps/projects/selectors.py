from django.utils import timezone

from apps.core.models import Course
from apps.editions.enums import StageKind
from apps.editions.models import Category, Challenge, Stage
from apps.projects.enums import DeliveryStatus, PhaseStatus
from apps.projects.models import Submission, SubmissionReceipt, SubmissionVersion


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


def get_phase_status(stage) -> str:
    """Fase da etapa pelas datas: em breve, aberta ou encerrada (RF44)."""
    now = timezone.now()
    if now < stage.starts_at:
        return PhaseStatus.UPCOMING
    if now <= stage.ends_at:
        return PhaseStatus.OPEN
    return PhaseStatus.FINISHED


def get_delivery_status(project, stage) -> str:
    """Status da entrega, calculado e nunca gravado (RF31, P-27).

    Com versão no prazo, enviada; sem versão, não enviada enquanto o prazo da
    equipe está aberto e não entregue depois dele.
    """
    submission = Submission.objects.filter(project=project, stage=stage).first()
    if submission is not None and get_valid_version(submission) is not None:
        return DeliveryStatus.SUBMITTED
    if timezone.now() <= get_submission_deadline(project, stage):
        return DeliveryStatus.NOT_SUBMITTED
    return DeliveryStatus.NOT_DELIVERED


def get_official_version(project, stage) -> SubmissionVersion | None:
    """Versão que vale, só depois de encerrado o prazo da equipe (RF31)."""
    if timezone.now() <= get_submission_deadline(project, stage):
        return None
    submission = Submission.objects.filter(project=project, stage=stage).first()
    return get_valid_version(submission) if submission else None


def get_project_deliverables(project):
    """Etapas de entrega da edição com campos de entrega, em ordem (RF31)."""
    return (
        Stage.objects.filter(
            edition_id=project.edition_id,
            kind=StageKind.SUBMISSION,
            submission_fields__isnull=False,
        )
        .distinct()
        .order_by("order")
    )


def get_receipt_by_version(version_id: int) -> SubmissionReceipt | None:
    """Comprovante da versão, com equipe, projeto e etapa carregados (RF31)."""
    return (
        SubmissionReceipt.objects.select_related(
            "version__submission__project__team",
            "version__submission__stage",
        )
        .filter(version_id=version_id)
        .first()
    )
