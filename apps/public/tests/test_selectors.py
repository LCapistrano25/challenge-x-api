import pytest
from django.utils import timezone

from apps.editions.factories import EditionFactory
from apps.editions.models import Edition
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
    """Garante que retorna apenas a edição publicada e não encerrada."""
    now = timezone.now()

    # Edição em Setup (não publicada)
    Edition.objects.create(year=2025, semester=1, name="Setup")

    # Edição Vigente (publicada, sem encerramento)
    vigente = Edition.objects.create(
        year=2025, semester=2, name="Vigente", published_at=now
    )

    # Edição Encerrada (já possui closed_at)
    Edition.objects.create(
        year=2024, semester=2, name="Encerrada", published_at=now, closed_at=now
    )

    result = get_current_edition()
    assert result is not None
    assert result.id == vigente.id


@pytest.mark.django_db
def test_list_closed_editions():
    """Garante que lista apenas edições com a data de encerramento preenchida."""
    now = timezone.now()

    # Cria duas edições encerradas
    Edition.objects.create(
        year=2023, semester=1, name="Encerrada 1", published_at=now, closed_at=now
    )
    Edition.objects.create(
        year=2023, semester=2, name="Encerrada 2", published_at=now, closed_at=now
    )
    # Cria uma edição vigente
    Edition.objects.create(year=2024, semester=1, name="Vigente", published_at=now)

    resultados = list_closed_editions()

    assert resultados.count() == 2
    for ed in resultados:
        assert ed.closed_at is not None


@pytest.mark.django_db
def test_list_edition_winners():
    """Garante que lista apenas projetos premiados da edição correta."""
    edicao_alvo = EditionFactory()
    outra_edicao = EditionFactory()

    # 1. Projeto premiado (Vencedor na edição alvo)
    proj_vencedor = ProjectFactory(edition=edicao_alvo)
    ProjectResultFactory(project=proj_vencedor, award=1)

    # 2. Projeto não premiado (Participou na edição alvo, mas não ganhou)
    proj_comum = ProjectFactory(edition=edicao_alvo)
    ProjectResultFactory(project=proj_comum, award=None)

    # 3. Projeto premiado noutra edição
    proj_outra = ProjectFactory(edition=outra_edicao)
    ProjectResultFactory(project=proj_outra, award=2)

    # Executa o seletor
    vencedores = list_edition_winners(edicao_alvo.id)

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
