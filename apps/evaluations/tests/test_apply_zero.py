from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.editions.factories import StageFactory
from apps.evaluations.enums import ScoreStatus
from apps.evaluations.models import StageScore
from apps.evaluations.use_cases.apply_zero_for_missing_submission import (
    apply_zero_for_missing_submission,
)
from apps.projects.factories import (
    DeadlineExtensionFactory,
    ProjectFactory,
    SubmissionFactory,
    SubmissionVersionFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def project():
    return ProjectFactory()


@pytest.fixture
def closed_stage(project):
    # Entrega encerrada há 6 dias.
    return StageFactory(
        edition=project.edition, starts_at=timezone.now() - timedelta(days=20)
    )


def test_prazo_encerrado_sem_entrega_vira_zero(project, closed_stage):
    score = apply_zero_for_missing_submission(project=project, stage=closed_stage)

    assert score.status == ScoreStatus.ZERO_NO_SUBMISSION
    assert score.value == Decimal("0.00")
    assert score.evaluation_count == 0
    assert score.calculated_at is not None


def test_prazo_aberto_nao_recebe_zero(project):
    aberta = StageFactory(edition=project.edition)

    assert apply_zero_for_missing_submission(project=project, stage=aberta) is None
    assert not StageScore.objects.exists()


def test_entrega_no_prazo_nao_recebe_zero(project, closed_stage):
    SubmissionVersionFactory(
        submission=SubmissionFactory(project=project, stage=closed_stage),
        submitted_at=closed_stage.ends_at - timedelta(days=1),
    )

    assert (
        apply_zero_for_missing_submission(project=project, stage=closed_stage) is None
    )
    assert not StageScore.objects.exists()


def test_versao_enviada_depois_do_prazo_nao_conta(project, closed_stage):
    SubmissionVersionFactory(
        submission=SubmissionFactory(project=project, stage=closed_stage),
        submitted_at=closed_stage.ends_at + timedelta(hours=1),
    )

    score = apply_zero_for_missing_submission(project=project, stage=closed_stage)

    assert score.status == ScoreStatus.ZERO_NO_SUBMISSION


def test_prorrogacao_aberta_adia_o_zero(project, closed_stage):
    DeadlineExtensionFactory(
        project=project,
        stage=closed_stage,
        ends_at=timezone.now() + timedelta(hours=1),
    )

    assert (
        apply_zero_for_missing_submission(project=project, stage=closed_stage) is None
    )


def test_repetir_nao_cria_outra_nota(project, closed_stage):
    primeira = apply_zero_for_missing_submission(project=project, stage=closed_stage)

    segunda = apply_zero_for_missing_submission(project=project, stage=closed_stage)

    assert segunda.pk == primeira.pk
    assert StageScore.objects.count() == 1


def test_etapa_sem_avaliacao_do_professor_e_recusada(project):
    formacao = StageFactory(edition=project.edition, formation=True)

    with pytest.raises(ValidationError, match="não tem avaliação"):
        apply_zero_for_missing_submission(project=project, stage=formacao)
