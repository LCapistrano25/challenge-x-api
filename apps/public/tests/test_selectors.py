import pytest
from django.utils import timezone

from apps.editions.enums import EditionStatus
from apps.editions.factories import EditionFactory
from apps.projects.enums import ProjectStatus
from apps.projects.factories import ProjectFactory
from apps.public.selectors import (
    get_current_edition,
    get_public_project,
    list_closed_editions,
    list_edition_winners,
    list_public_projects,
)
from apps.results.factories import ProjectResultFactory


@pytest.mark.django_db
def test_get_current_edition():
    """Garante que retorna apenas a edição com status PUBLISHED."""
    EditionFactory(status=EditionStatus.PUBLISHED)

    resultado = get_current_edition()

    assert resultado is not None
    assert resultado.status == EditionStatus.PUBLISHED


@pytest.mark.django_db
def test_list_closed_editions():
    """Garante que lista apenas edições com status CLOSED."""
    # Cria 2 edições encerradas e 1 publicada
    EditionFactory(status=EditionStatus.CLOSED)
    EditionFactory(status=EditionStatus.CLOSED)
    EditionFactory(status=EditionStatus.PUBLISHED)

    resultados = list_closed_editions()

    assert resultados.count() == 2


@pytest.mark.django_db
def test_list_edition_winners():
    """Garante que lista apenas projetos premiados da edição correta e encerrada."""
    # Garantimos que as edições estão no status CLOSED
    edicao_alvo = EditionFactory(status=EditionStatus.CLOSED)
    outra_edicao = EditionFactory(status=EditionStatus.CLOSED)

    # 1. Projeto premiado (Vencedor na edição alvo, devidamente aprovado)
    proj_vencedor = ProjectFactory(edition=edicao_alvo)
    ProjectResultFactory(project=proj_vencedor, award=1, approved_at=timezone.now())

    # 2. Projeto não premiado (Participou na edição alvo, mas não ganhou)
    proj_comum = ProjectFactory(edition=edicao_alvo)
    ProjectResultFactory(project=proj_comum, award=None)

    # 3. Projeto premiado noutra edição
    proj_outra = ProjectFactory(edition=outra_edicao)
    ProjectResultFactory(project=proj_outra, award=2, approved_at=timezone.now())

    # Executa o seletor passando o OBJETO em vez do ID (e.id)
    vencedores = list_edition_winners(edicao_alvo)

    # Validações
    assert vencedores.count() == 1
    assert vencedores.first().project == proj_vencedor


@pytest.mark.django_db
def test_list_public_projects():
    """Garante que a vitrine lista apenas projetos com status COMPLETED."""
    # 1. Projeto Público (Concluído)
    ProjectFactory(status=ProjectStatus.COMPLETED, title="Projeto Público")
    # 2. Projeto Privado (Em Andamento)
    ProjectFactory(status=ProjectStatus.IN_PROGRESS, title="Projeto Privado")
    # 3. Projeto Desclassificado
    ProjectFactory(status=ProjectStatus.DISQUALIFIED, title="Projeto Desclassificado")

    projetos = list_public_projects()

    assert projetos.count() == 1
    assert projetos.first().title == "Projeto Público"


@pytest.mark.django_db
def test_get_public_project():
    """Garante que só é possível detalhar um projeto se ele for público (COMPLETED)."""
    p_publico = ProjectFactory(status=ProjectStatus.COMPLETED)
    p_privado = ProjectFactory(status=ProjectStatus.IN_PROGRESS)

    # Sucesso ao buscar o projeto público
    resultado_publico = get_public_project(p_publico.id)
    assert resultado_publico is not None
    assert resultado_publico.id == p_publico.id

    # Falha (retorna None) ao tentar buscar um projeto que não é público
    resultado_privado = get_public_project(p_privado.id)
    assert resultado_privado is None
