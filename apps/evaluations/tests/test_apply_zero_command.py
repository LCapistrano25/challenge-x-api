from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.editions.enums import EditionStatus
from apps.editions.factories import StageFactory
from apps.evaluations.enums import ScoreStatus
from apps.evaluations.models import StageScore
from apps.projects.factories import DeadlineExtensionFactory, ProjectFactory

pytestmark = pytest.mark.django_db


def rodar():
    saida = StringIO()
    call_command("apply_zero_scores", stdout=saida)
    return saida.getvalue()


@pytest.fixture
def project():
    return ProjectFactory(team__edition__status=EditionStatus.PUBLISHED)


def etapa_encerrada(project):
    return StageFactory(
        edition=project.edition, starts_at=timezone.now() - timedelta(days=20)
    )


def test_aplica_zero_a_quem_nao_entregou(project):
    etapa = etapa_encerrada(project)

    assert "aplicadas: 1" in rodar()

    nota = StageScore.objects.get(project=project, stage=etapa)
    assert nota.status == ScoreStatus.ZERO_NO_SUBMISSION


def test_rodar_de_novo_nao_duplica(project):
    etapa_encerrada(project)
    rodar()

    rodar()

    assert StageScore.objects.count() == 1


def test_respeita_a_prorrogacao_da_equipe(project):
    etapa = etapa_encerrada(project)
    DeadlineExtensionFactory(
        project=project, stage=etapa, ends_at=timezone.now() + timedelta(hours=1)
    )

    assert "aplicadas: 0" in rodar()
    assert not StageScore.objects.exists()


def test_ignora_etapa_com_prazo_aberto(project):
    StageFactory(edition=project.edition)

    rodar()

    assert not StageScore.objects.exists()


def test_ignora_edicao_que_nao_esta_publicada():
    projeto = ProjectFactory(team__edition__status=EditionStatus.SETUP)
    etapa_encerrada(projeto)

    rodar()

    assert not StageScore.objects.exists()
