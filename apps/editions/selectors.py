from django.db.models import QuerySet

from apps.editions.models import EditionReviewer


def list_edition_reviewers(edition_id: int) -> QuerySet[EditionReviewer]:
    """Vínculos de avaliador externo de uma edição (RF11)."""
    # O serializer lê usuário e curso de cada vínculo: busca tudo numa consulta.
    return (
        EditionReviewer.objects.filter(edition_id=edition_id)
        .select_related("reviewer__user", "course")
        .order_by("id")
    )
