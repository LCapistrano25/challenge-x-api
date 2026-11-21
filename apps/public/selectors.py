from django.db.models import QuerySet

from apps.editions.models import Edition
from apps.projects.enums import ProjectStatus
from apps.projects.models import Project
from apps.results.models import ProjectResult


def get_current_edition() -> Edition | None:
    """
    Retorna a edição vigente.
    Regra: Possui data de publicação, mas não possui data de encerramento.
    """
    return (
        Edition.objects.filter(published_at__isnull=False, closed_at__isnull=True)
        .order_by("-year", "-semester")
        .first()
    )


def list_closed_editions() -> QuerySet[Edition]:
    """
    Lista todas as edições que já foram encerradas.
    Regra: Possui data de encerramento preenchida.
    """
    return Edition.objects.filter(closed_at__isnull=False).order_by(
        "-year", "-semester"
    )


def list_edition_winners(edition_id: int) -> QuerySet[ProjectResult]:
    """
    Retorna a galeria de vencedores da edição.
    Regra: Resultados com a coluna 'award' preenchida na edição solicitada.
    """
    return (
        ProjectResult.objects.filter(
            project__edition_id=edition_id, award__isnull=False
        )
        .select_related("project")
        .order_by("award")
    )


def list_public_projects() -> QuerySet[Project]:
    """
    Lista todos os projetos públicos para a vitrine.
    Regra (P-28): Apenas projetos com status COMPLETED.
    """
    return (
        Project.objects.filter(status=ProjectStatus.COMPLETED)
        .select_related("edition", "category", "challenge")
        .order_by("-created_at")
    )


def get_public_project(project_id: int) -> Project | None:
    """
    Retorna o detalhe de um projeto público específico.
    Regra (P-28): O projeto deve ter o status COMPLETED.
    """
    return (
        Project.objects.filter(id=project_id, status=ProjectStatus.COMPLETED)
        .select_related("edition", "category", "challenge", "team")
        .first()
    )
