from django.db.models import Prefetch, QuerySet

from apps.editions.enums import EditionStatus
from apps.editions.models import Challenge, Edition
from apps.projects.enums import ProjectStatus
from apps.projects.models import Project
from apps.results.models import ProjectResult
from apps.teams.models import TeamMember


def get_current_edition() -> Edition | None:
    """Edição vigente: a publicada (RF44, P-41), com etapas, ODS e desafios."""
    return (
        Edition.objects.filter(status=EditionStatus.PUBLISHED)
        .prefetch_related(
            "stages",
            "sdg_links__sdg",
            Prefetch(
                "challenges",
                queryset=Challenge.objects.filter(active=True).select_related(
                    "course", "sdg"
                ),
            ),
        )
        .order_by("-year", "-semester")
        .first()
    )


def list_closed_editions() -> QuerySet[Edition]:
    """Edições encerradas, para o acervo (RF35, RF46)."""
    return Edition.objects.filter(status=EditionStatus.CLOSED).order_by(
        "-year", "-semester"
    )


def list_edition_winners(edition: Edition) -> QuerySet[ProjectResult]:
    """Pódio da edição: só edição encerrada e resultado homologado (RF35, RF46)."""
    if edition.status != EditionStatus.CLOSED:
        return ProjectResult.objects.none()
    return (
        ProjectResult.objects.filter(
            project__edition=edition, award__isnull=False, approved_at__isnull=False
        )
        .select_related(
            "project__edition",
            "project__category",
            "project__challenge__course",
            "project__challenge__sdg",
        )
        .prefetch_related(
            Prefetch(
                "project__team__members",
                queryset=TeamMember.objects.filter(active=True).select_related(
                    "student__user"
                ),
                to_attr="active_members",
            )
        )
        .order_by(
            "project__challenge__course__name", "project__category__name", "award"
        )
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
