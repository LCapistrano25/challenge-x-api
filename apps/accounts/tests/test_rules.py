import pytest

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import InvalidCredentials, ReviewerNotInCurrentEdition
from apps.accounts.factories import (
    ExternalReviewerFactory,
    StudentFactory,
    TeacherFactory,
    UserFactory,
)
from apps.accounts.rules import (
    ensure_password_login_allowed,
    ensure_reviewer_in_current_edition,
)
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


# Quem entra com senha (RF01, RF41)


def test_admin_entra_com_senha():
    ensure_password_login_allowed(UserFactory(role=UserRole.ADMIN))


def test_avaliador_vinculado_entra_com_senha():
    reviewer = ExternalReviewerFactory()
    link(reviewer, EditionStatus.PUBLISHED)

    ensure_password_login_allowed(reviewer.user)


def test_avaliador_sem_vinculo_nao_entra_com_senha():
    with pytest.raises(ReviewerNotInCurrentEdition):
        ensure_password_login_allowed(ExternalReviewerFactory().user)


@pytest.mark.parametrize("factory", [StudentFactory, TeacherFactory])
def test_aluno_e_professor_nao_entram_com_senha(factory):
    with pytest.raises(InvalidCredentials):
        ensure_password_login_allowed(factory().user)


def test_credencial_recusada_pelo_authenticate_nao_entra():
    with pytest.raises(InvalidCredentials):
        ensure_password_login_allowed(None)
