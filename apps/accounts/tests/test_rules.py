import pytest

from apps.accounts.exceptions import ReviewerNotInCurrentEdition
from apps.accounts.factories import ExternalReviewerFactory
from apps.accounts.rules import ensure_reviewer_in_current_edition
from apps.editions.enums import EditionStatus
from apps.editions.factories import EditionFactory
from apps.editions.models import EditionReviewer

pytestmark = pytest.mark.django_db

# Avaliador externo e a edição vigente (RF41, P-41)


def link(reviewer, status):
    EditionReviewer.objects.create(
        edition=EditionFactory(status=status), reviewer=reviewer
    )


def test_avaliador_vinculado_a_edicao_publicada_passa():
    reviewer = ExternalReviewerFactory()
    link(reviewer, EditionStatus.PUBLISHED)

    ensure_reviewer_in_current_edition(reviewer.user)


def test_avaliador_sem_vinculo_e_recusado():
    with pytest.raises(ReviewerNotInCurrentEdition):
        ensure_reviewer_in_current_edition(ExternalReviewerFactory().user)


@pytest.mark.parametrize("status", [EditionStatus.SETUP, EditionStatus.CLOSED])
def test_vinculo_com_edicao_nao_vigente_nao_basta(status):
    reviewer = ExternalReviewerFactory()
    link(reviewer, status)

    with pytest.raises(ReviewerNotInCurrentEdition):
        ensure_reviewer_in_current_edition(reviewer.user)


def test_vinculo_de_outro_avaliador_nao_conta():
    link(ExternalReviewerFactory(), EditionStatus.PUBLISHED)

    with pytest.raises(ReviewerNotInCurrentEdition):
        ensure_reviewer_in_current_edition(ExternalReviewerFactory().user)
