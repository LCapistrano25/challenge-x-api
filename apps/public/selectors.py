from django.db.models import Prefetch, QuerySet

from apps.editions.enums import EditionStatus
from apps.editions.models import Challenge, Edition
from apps.projects.enums import ProjectStatus
from apps.projects.models import Project
from apps.results.models import ProjectResult
from apps.teams.models import TeamMember


def get_current_edition() -> Edition | None:
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
        .first()
    )


def list_closed_editions() -> QuerySet[Edition]:
    return Edition.objects.filter(status=EditionStatus.CLOSED).order_by("-closed_at")


def list_edition_winners(edition: Edition) -> QuerySet[ProjectResult]:
    if edition.status != EditionStatus.CLOSED:
        return ProjectResult.objects.none()

    return (
        ProjectResult.objects.filter(
            project__edition=edition,
            award__isnull=False,
            approved_at__isnull=False,
        )
        .select_related(
            "project__edition",
            "project__category",
            "project__team",
            "project__challenge__course",
            "project__challenge__sdg",
        )
        .prefetch_related(
            Prefetch(
                "project__team__members",
                # Trazemos o student e o user encadeados
                queryset=TeamMember.objects.select_related("student__user"),
                # O serializer do revisor procura exatamente por 'active_members'
                to_attr="active_members",
            )
        )
        .order_by("award")
    )


def list_public_projects() -> QuerySet[Project]:
    return (
        Project.objects.filter(status=ProjectStatus.COMPLETED)
        .select_related("edition", "category", "challenge")
        .order_by("-created_at")
    )


def get_public_project(project_id: int) -> Project | None:
    return (
        Project.objects.filter(id=project_id, status=ProjectStatus.COMPLETED)
        .select_related("edition", "category", "challenge", "team")
        .first()
    )
