"""As respostas de evaluations seguem o contrato (docs/api/openapi.yaml)."""

import pytest

from apps.core.tests.contract import mismatches, schema
from apps.evaluations.tests.test_api import PAINEL, client_for, corpo
from apps.evaluations.tests.test_api import ctx as ctx_form  # noqa: F401
from apps.evaluations.tests.test_scores_api import avaliar, novo_professor
from apps.evaluations.tests.test_scores_api import ctx as ctx_scores  # noqa: F401

pytestmark = pytest.mark.django_db


def test_formulario_de_avaliacao_segue_o_contrato(ctx_form):  # noqa: F811
    client_for(ctx_form.user).put(ctx_form.url, corpo(ctx_form), format="json")

    response = client_for(ctx_form.user).get(ctx_form.url)

    assert response.status_code == 200
    assert mismatches(response.json(), schema("EvaluationForm")) == []


def test_painel_do_professor_segue_o_contrato(ctx_form):  # noqa: F811
    response = client_for(ctx_form.user).get(PAINEL)

    assert response.status_code == 200
    assert response.json()["results"]
    assert mismatches(response.json(), schema("PaginatedTeacherProjectRow")) == []


@pytest.mark.parametrize("avaliacoes", [1, 2])
def test_notas_do_projeto_seguem_o_contrato(ctx_scores, avaliacoes):  # noqa: F811
    for _ in range(avaliacoes):
        avaliar(ctx_scores, novo_professor(ctx_scores))

    response = client_for(ctx_scores.aluno).get(ctx_scores.url)

    assert response.status_code == 200
    assert mismatches(response.json(), schema("ProjectScores")) == []
