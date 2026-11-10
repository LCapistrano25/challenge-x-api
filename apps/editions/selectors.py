from typing import List
from apps.editions.models.edition import EditionReviewer


def get_edition_reviewer(edition_id: int) -> List[EditionReviewer]:
    """Consulta os avaliadores de uma Edição Específica"""

    edition_reviewer = EditionReviewer.objects.filter(edition_id=edition_id)

    return edition_reviewer