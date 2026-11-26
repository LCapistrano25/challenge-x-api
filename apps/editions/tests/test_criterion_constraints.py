import pytest
from django.db import IntegrityError, transaction

from apps.editions.factories import CriterionFactory, EditionFactory


@pytest.mark.django_db
def test_nome_de_criterio_unico_por_edicao_sem_diferenciar_caixa():
    edition = EditionFactory()
    CriterionFactory(edition=edition, name="Inovação")

    with pytest.raises(IntegrityError), transaction.atomic():
        CriterionFactory(edition=edition, name="INOVAÇÃO")

    CriterionFactory(name="INOVAÇÃO")
