from datetime import timedelta

import pytest

from apps.projects.factories import SubmissionFactory, SubmissionVersionFactory
from apps.projects.selectors import get_valid_version

pytestmark = pytest.mark.django_db


@pytest.fixture
def submission():
    return SubmissionFactory()


def at(submission, delta):
    return submission.stage.ends_at + delta


# Critérios de pronto da issue BM5


def test_envio_no_prazo_vale(submission):
    version = SubmissionVersionFactory(
        submission=submission,
        number=1,
        submitted_at=at(submission, -timedelta(hours=1)),
    )
    assert get_valid_version(submission) == version


def test_envio_fora_do_prazo_nao_vale(submission):
    SubmissionVersionFactory(
        submission=submission,
        number=1,
        submitted_at=at(submission, timedelta(minutes=1)),
    )
    assert get_valid_version(submission) is None


def test_sem_nenhuma_versao(submission):
    assert get_valid_version(submission) is None


# Casos de borda


def test_vale_a_de_maior_numero_dentro_do_prazo(submission):
    SubmissionVersionFactory(
        submission=submission, number=1, submitted_at=at(submission, -timedelta(days=2))
    )
    ultima_no_prazo = SubmissionVersionFactory(
        submission=submission, number=2, submitted_at=at(submission, -timedelta(days=1))
    )
    SubmissionVersionFactory(
        submission=submission, number=3, submitted_at=at(submission, timedelta(hours=1))
    )
    assert get_valid_version(submission) == ultima_no_prazo


def test_envio_exatamente_no_fim_do_prazo_vale(submission):
    version = SubmissionVersionFactory(
        submission=submission, number=1, submitted_at=submission.stage.ends_at
    )
    assert get_valid_version(submission) == version
