from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.factories import UserFactory
from apps.editions.factories import StageCriterionFactory
from apps.evaluations.enums import EvaluationStatus
from apps.evaluations.factories import EvaluationFactory, EvaluationItemFactory
from apps.evaluations.models import ScoreRectification
from apps.evaluations.use_cases.rectify_score import rectify_score

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin():
    return UserFactory(role=UserRole.ADMIN)


@pytest.fixture
def item():
    avaliacao = EvaluationFactory(finalized=True)
    criterio = StageCriterionFactory(stage=avaliacao.stage, max_score=Decimal("2.00"))
    return EvaluationItemFactory(
        evaluation=avaliacao, stage_criterion=criterio, points=Decimal("1.00")
    )


# Retificação de nota (RF14, P-21)


def test_retificacao_troca_os_pontos_e_guarda_o_historico(admin, item):
    retificacao = rectify_score(
        actor=admin, item=item, new_points=Decimal("1.50"), reason="Erro de digitação."
    )

    item.refresh_from_db()
    assert item.points == Decimal("1.50")
    assert retificacao.previous_points == Decimal("1.00")
    assert retificacao.rectified_by == admin


def test_avaliacao_finalizada_fora_do_prazo_pode_ser_retificada(admin, item):
    stage = item.evaluation.stage
    stage.evaluation_ends_at = stage.ends_at + timedelta(seconds=1)
    stage.save()

    rectify_score(actor=admin, item=item, new_points=Decimal("0.50"), reason="Recurso.")

    item.refresh_from_db()
    assert item.points == Decimal("0.50")


@pytest.mark.parametrize(
    ("new_points", "reason", "mensagem"),
    [
        (Decimal("2.01"), "Recurso.", "Máximo do critério"),
        (Decimal("1.50"), "", "não pode estar vazio"),
    ],
)
def test_retificacao_invalida_nao_muda_nada(admin, item, new_points, reason, mensagem):
    with pytest.raises(ValidationError, match=mensagem):
        rectify_score(actor=admin, item=item, new_points=new_points, reason=reason)

    item.refresh_from_db()
    assert item.points == Decimal("1.00")
    assert not ScoreRectification.objects.exists()


def test_so_admin_retifica(item):
    professor = UserFactory(role=UserRole.TEACHER)
    with pytest.raises(ValidationError, match="rectified_by"):
        rectify_score(
            actor=professor, item=item, new_points=Decimal("1.50"), reason="Recurso."
        )


def test_retificacao_precisa_mudar_os_pontos(admin, item):
    with pytest.raises(IntegrityError):
        ScoreRectification.objects.create(
            item=item,
            previous_points=Decimal("1.00"),
            new_points=Decimal("1.00"),
            reason="Nada muda.",
            rectified_by=admin,
        )


# Prazo de avaliação do professor (RF38, P-19)


def test_professor_nao_finaliza_depois_do_prazo():
    avaliacao = EvaluationFactory()
    avaliacao.status = EvaluationStatus.FINALIZED
    avaliacao.finalized_at = avaliacao.stage.evaluation_ends_at + timedelta(minutes=1)
    with pytest.raises(ValidationError, match="prazo de avaliação"):
        avaliacao.full_clean()


def test_professor_finaliza_dentro_do_prazo():
    avaliacao = EvaluationFactory()
    avaliacao.status = EvaluationStatus.FINALIZED
    avaliacao.finalized_at = timezone.now()
    avaliacao.full_clean()
