from django.db.models import QuerySet

from apps.core.models import Sdg
from apps.editions.models import Challenge, Edition, EditionReviewer


def list_edition_reviewers(edition_id: int) -> QuerySet[EditionReviewer]:
    """Vínculos de avaliador externo de uma edição (RF11)."""
    # O serializer lê usuário e curso de cada vínculo: busca tudo numa consulta.
    return (
        EditionReviewer.objects.filter(edition_id=edition_id)
        .select_related("reviewer__user", "course")
        .order_by("id")
    )


def list_editions():
    """Todas as edições, na ordem do model (ano e semestre, da mais recente)."""
    return Edition.objects.all()


def list_edition_sdgs(edition_id: int) -> QuerySet[Sdg]:
    """Lista as ODS habilitadas, incluindo as inativadas no catálogo."""
    return Sdg.objects.filter(edition_links__edition_id=edition_id).order_by("number")


def list_edition_challenges(
    *,
    edition_id: int,
    course_id: int | None = None,
    sdg_id: int | None = None,
    active: bool | None = None,
) -> QuerySet[Challenge]:
    filters = {"course_id": course_id, "sdg_id": sdg_id, "active": active}
    return (
        Challenge.objects.filter(
            edition_id=edition_id,
            **{field: value for field, value in filters.items() if value is not None},
        )
        .select_related("course", "sdg")
        .order_by("id")
    )
