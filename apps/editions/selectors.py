from django.db.models import QuerySet

from apps.core.models import Sdg
from apps.editions.models import Edition, EditionReviewer


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
