import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.tests.contract import mismatches, schema
from apps.editions.enums import EditionStatus
from apps.editions.factories import (
    CategoryFactory,
    ChallengeFactory,
    EditionFactory,
    StageFactory,
)
from apps.projects.enums import ProjectStatus
from apps.projects.factories import ProjectFactory
from apps.results.factories import ProjectResultFactory
from apps.teams.factories import TeamMemberFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


def closed_edition():
    return EditionFactory(status=EditionStatus.CLOSED, closed_at=timezone.now())


def winner(edition, award=1, approved=True):
    project = ProjectFactory(
        team__edition=edition, category=CategoryFactory(edition=edition)
    )
    return ProjectResultFactory(
        project=project,
        award=award,
        approved_at=timezone.now() if approved else None,
    )


def test_edicao_vigente_segue_o_contrato(api_client):
    edition = EditionFactory(status=EditionStatus.PUBLISHED, name="Desafio X")
    StageFactory(edition=edition)
    challenge = ChallengeFactory(edition=edition)

    response = api_client.get("/api/public/editions/current")

    assert response.status_code == 200
    body = response.json()
    assert mismatches(body, schema("PublicEdition")) == []
    assert body["edition"]["id"] == edition.id
    assert [c["id"] for c in body["challenges"]] == [challenge.id]
    assert [s["id"] for s in body["sdgs"]] == [challenge.sdg_id]
    assert body["stages"][0]["phase_status"] == "OPEN"


def test_edicao_vigente_e_a_publicada(api_client):
    EditionFactory(status=EditionStatus.SETUP)
    closed_edition()
    publicada = EditionFactory(status=EditionStatus.PUBLISHED)

    response = api_client.get("/api/public/editions/current")

    assert response.json()["edition"]["id"] == publicada.id


def test_edicao_vigente_esconde_desafio_inativo(api_client):
    edition = EditionFactory(status=EditionStatus.PUBLISHED)
    ChallengeFactory(edition=edition, active=False)

    response = api_client.get("/api/public/editions/current")

    assert response.json()["challenges"] == []


def test_sem_edicao_vigente_responde_404(api_client):
    EditionFactory(status=EditionStatus.SETUP)

    response = api_client.get("/api/public/editions/current")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_edicoes_encerradas_seguem_o_contrato(api_client):
    encerrada = closed_edition()
    EditionFactory(status=EditionStatus.PUBLISHED)

    response = api_client.get("/api/public/editions")

    assert response.status_code == 200
    body = response.json()
    assert [item["edition"]["id"] for item in body] == [encerrada.id]
    for item in body:
        assert mismatches(item, schema("PublicEditionListItem")) == []


def test_vencedores_seguem_o_contrato(api_client):
    edition = closed_edition()
    result = winner(edition)

    response = api_client.get(f"/api/public/editions/{edition.id}/winners")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert mismatches(body[0], schema("Winner")) == []
    assert body[0]["award"] == 1
    assert body[0]["project"]["id"] == result.project_id
    assert body[0]["project"]["members"]


def test_vencedores_so_com_resultado_homologado(api_client):
    edition = closed_edition()
    winner(edition, approved=False)

    response = api_client.get(f"/api/public/editions/{edition.id}/winners")

    assert response.json() == []


def test_vencedores_so_de_edicao_encerrada(api_client):
    edition = EditionFactory(status=EditionStatus.PUBLISHED)
    winner(edition)

    response = api_client.get(f"/api/public/editions/{edition.id}/winners")

    assert response.json() == []


def test_vencedores_de_edicao_inexistente_responde_404(api_client):
    response = api_client.get("/api/public/editions/999999/winners")

    assert response.status_code == 404


def test_vencedores_nao_mostra_integrantes_inativos(api_client):
    edition = closed_edition()
    result = winner(edition)

    # Membro inativo precisa da data de saída (left_at)
    TeamMemberFactory(
        team=result.project.team,
        active=False,
        left_at=timezone.now(),
        student__user__name="Inativo Silva",
    )
    # Membro ativo
    TeamMemberFactory(
        team=result.project.team, active=True, student__user__name="Ativo Costa"
    )

    response = api_client.get(f"/api/public/editions/{edition.id}/winners")

    assert response.status_code == 200
    membros_retornados = response.json()[0]["project"]["members"]
    nomes = [m["name"] for m in membros_retornados]
    assert "Ativo Costa" in nomes
    assert "Inativo Silva" not in nomes


def test_projetos_paginados_e_seguem_contrato(api_client):
    edicao = EditionFactory(status=EditionStatus.PUBLISHED)
    ProjectFactory(edition=edicao)
    ProjectFactory(edition=edicao)

    response = api_client.get("/api/public/projects")

    assert response.status_code == 200
    body = response.json()
    assert "count" in body
    assert "results" in body
    assert mismatches(body, schema("PaginatedPublicProject")) == []


def test_projetos_nao_mostra_equipa_desclassificada(api_client):
    edicao = EditionFactory(status=EditionStatus.PUBLISHED)
    p_valido = ProjectFactory(edition=edicao, status=ProjectStatus.IN_PROGRESS)
    p_desclassificado = ProjectFactory(
        edition=edicao, status=ProjectStatus.DISQUALIFIED
    )

    response = api_client.get("/api/public/projects")
    resultados = response.json()["results"]

    ids_retornados = [p["id"] for p in resultados]
    assert p_valido.id in ids_retornados
    assert p_desclassificado.id not in ids_retornados


def test_projetos_edicao_encerrada_so_mostra_publicos_homologados(api_client):
    edicao = EditionFactory(status=EditionStatus.CLOSED)

    # Projeto com resultado homologado (Deve aparecer)
    p_homologado = ProjectFactory(edition=edicao)
    ProjectResultFactory(project=p_homologado, approved_at=timezone.now())

    # Projeto sem resultado (Não deve aparecer)
    p_sem_resultado = ProjectFactory(edition=edicao)

    response = api_client.get(f"/api/public/projects?edition_id={edicao.id}")
    resultados = response.json()["results"]

    ids_retornados = [p["id"] for p in resultados]
    assert p_homologado.id in ids_retornados
    assert p_sem_resultado.id not in ids_retornados


def test_detalhe_projeto_segue_contrato_e_desclassificado_da_404(api_client):
    edicao = EditionFactory(status=EditionStatus.PUBLISHED)
    p_valido = ProjectFactory(edition=edicao)
    p_desclassificado = ProjectFactory(
        edition=edicao, status=ProjectStatus.DISQUALIFIED
    )

    # Testa sucesso (formato do contrato)
    response_sucesso = api_client.get(f"/api/public/projects/{p_valido.id}")
    assert response_sucesso.status_code == 200
    assert mismatches(response_sucesso.json(), schema("PublicProject")) == []

    # Testa falha (404)
    response_falha = api_client.get(f"/api/public/projects/{p_desclassificado.id}")
    assert response_falha.status_code == 404


def test_projeto_de_equipe_desclassificada_fica_fora_da_vitrine(api_client):
    edicao = EditionFactory(status=EditionStatus.PUBLISHED)
    valido = ProjectFactory(team__edition=edicao)
    # Status do projeto ainda IN_PROGRESS: vale a situação da equipe.
    fora = ProjectFactory(team__edition=edicao, team__disqualified=True)

    ids = [p["id"] for p in api_client.get("/api/public/projects").json()["results"]]
    assert valido.id in ids
    assert fora.id not in ids
    assert api_client.get(f"/api/public/projects/{fora.id}").status_code == 404


def test_projeto_sem_desafio_fica_fora_da_vitrine(api_client):
    edicao = EditionFactory(status=EditionStatus.PUBLISHED)
    valido = ProjectFactory(team__edition=edicao)
    sem_desafio = ProjectFactory(team__edition=edicao, challenge=None)

    response = api_client.get("/api/public/projects")

    assert response.status_code == 200
    ids = [p["id"] for p in response.json()["results"]]
    assert ids == [valido.id]
    assert api_client.get(f"/api/public/projects/{sem_desafio.id}").status_code == 404


def test_vencedores_nao_mostra_equipe_desclassificada(api_client):
    from apps.teams.enums import TeamStatus

    edition = closed_edition()
    result = winner(edition)
    from apps.accounts.factories import UserFactory

    team = result.project.team
    team.status = TeamStatus.DISQUALIFIED
    team.disqualification_reason = "Plágio"
    team.disqualified_at = timezone.now()
    team.disqualified_by = UserFactory()
    team.save()

    response = api_client.get(f"/api/public/editions/{edition.id}/winners")

    assert response.json() == []


@pytest.mark.parametrize("param", ["edition_id", "course_id", "sdg_id", "category_id"])
def test_vitrine_filtro_invalido_responde_400(api_client, param):
    response = api_client.get(f"/api/public/projects?{param}=abc")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


def test_vitrine_filtra_por_curso_com_nome_do_contrato(api_client):
    edition = EditionFactory(status=EditionStatus.PUBLISHED)
    alvo = ProjectFactory(
        team__edition=edition, challenge=ChallengeFactory(edition=edition)
    )
    ProjectFactory(team__edition=edition, challenge=ChallengeFactory(edition=edition))

    response = api_client.get(
        f"/api/public/projects?course_id={alvo.challenge.course_id}"
    )

    assert [p["id"] for p in response.json()["results"]] == [alvo.id]
