from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.factories import StudentFactory, TeacherFactory, UserFactory
from apps.editions.enums import EditionStatus
from apps.editions.factories import StageCriterionFactory
from apps.evaluations.enums import ScoreStatus
from apps.evaluations.factories import EvaluationFactory, EvaluationItemFactory
from apps.evaluations.models import ScoreRectification, StageScore
from apps.evaluations.use_cases.recalculate_stage_score import recalculate_stage_score

pytestmark = pytest.mark.django_db


def client_for(user):
    client = APIClient()
    client.force_login(user)
    return client


def url(evaluation):
    return f"/api/admin/evaluations/{evaluation.pk}/rectifications"


@pytest.fixture
def admin():
    return UserFactory(role=UserRole.ADMIN)


@pytest.fixture
def item():
    avaliacao = EvaluationFactory(finalized=True)
    criterio = StageCriterionFactory(stage=avaliacao.stage, max_score=Decimal("2.00"))
    item = EvaluationItemFactory(
        evaluation=avaliacao, stage_criterion=criterio, points=Decimal("1.00")
    )
    recalculate_stage_score(project=avaliacao.project, stage=avaliacao.stage)
    return item


def corpo(item, new_points="1.50", reason="Erro de digitação."):
    return {
        "stage_criterion_id": item.stage_criterion_id,
        "new_points": new_points,
        "reason": reason,
    }


# POST /api/admin/evaluations/{evaluation_id}/rectifications (RF14)


def test_admin_retifica_e_a_nota_da_etapa_acompanha(admin, item):
    response = client_for(admin).post(url(item.evaluation), corpo(item), format="json")

    assert response.status_code == 201
    assert response.data["previous_points"] == "1.00"
    assert response.data["new_points"] == "1.50"
    assert response.data["rectified_by"] == admin.pk
    assert response.data["stage_score"] == {"value": "1.50", "evaluation_count": 1}
    nota = StageScore.objects.get()
    assert nota.status == ScoreStatus.DEFINITIVE
    assert ScoreRectification.objects.count() == 1


def test_exige_login(item):
    response = APIClient().post(url(item.evaluation), corpo(item), format="json")

    assert response.status_code == 403


@pytest.mark.parametrize("fabrica", [StudentFactory, TeacherFactory])
def test_so_admin_retifica(item, fabrica):
    usuario = fabrica().user

    response = client_for(usuario).post(
        url(item.evaluation), corpo(item), format="json"
    )

    assert response.status_code == 403
    assert not ScoreRectification.objects.exists()


def test_avaliacao_inexistente_da_404(admin, item):
    response = client_for(admin).post(
        "/api/admin/evaluations/999999/rectifications", corpo(item), format="json"
    )

    assert response.status_code == 404


def test_criterio_que_nao_e_da_avaliacao_da_400(admin, item):
    outro = StageCriterionFactory(stage=item.evaluation.stage)

    response = client_for(admin).post(
        url(item.evaluation),
        {"stage_criterion_id": outro.pk, "new_points": "1.50", "reason": "x"},
        format="json",
    )

    assert response.status_code == 400
    assert not ScoreRectification.objects.exists()


@pytest.mark.parametrize(
    ("new_points", "reason"),
    [("2.01", "Recurso."), ("1.50", ""), ("1.00", "Nada muda."), ("-1", "Recurso.")],
)
def test_corpo_invalido_da_400_e_nao_muda_nada(admin, item, new_points, reason):
    response = client_for(admin).post(
        url(item.evaluation), corpo(item, new_points, reason), format="json"
    )

    assert response.status_code == 400
    item.refresh_from_db()
    assert item.points == Decimal("1.00")


def test_avaliacao_em_rascunho_da_400(admin):
    rascunho = EvaluationItemFactory(evaluation=EvaluationFactory())

    response = client_for(admin).post(
        url(rascunho.evaluation), corpo(rascunho), format="json"
    )

    assert response.status_code == 400


def test_edicao_encerrada_da_400(admin, item):
    edicao = item.evaluation.project.edition
    edicao.status = EditionStatus.CLOSED
    edicao.save()

    response = client_for(admin).post(url(item.evaluation), corpo(item), format="json")

    assert response.status_code == 400
    item.refresh_from_db()
    assert item.points == Decimal("1.00")
