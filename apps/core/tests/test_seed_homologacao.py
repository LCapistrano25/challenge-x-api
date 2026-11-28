from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.editions.enums import EditionStatus
from apps.editions.factories import EditionFactory
from apps.editions.models import Edition
from apps.evaluations.enums import ScoreStatus
from apps.evaluations.models import StageScore
from apps.results.models import ProjectResult
from apps.teams.enums import TeamSituation, TeamStatus
from apps.teams.models import Team

pytestmark = pytest.mark.django_db


def rodar(**opcoes):
    saida = StringIO()
    call_command(
        "seed_homologacao",
        password="Senha!2026",
        students_per_course=10,
        stdout=saida,
        **opcoes,
    )
    return saida.getvalue()


def test_monta_o_banco_de_homologacao(settings):
    # Um teste só: a carga leva uns 20 s, então todas as conferências rodam juntas.
    settings.DEBUG = True
    saida = rodar()

    status = list(Edition.objects.order_by("year", "semester").values_list("status"))
    assert status == [
        (EditionStatus.CLOSED,),
        (EditionStatus.CLOSED,),
        (EditionStatus.PUBLISHED,),
        (EditionStatus.SETUP,),
    ]

    for edition in Edition.objects.filter(status=EditionStatus.CLOSED):
        results = ProjectResult.objects.filter(project__edition=edition)
        assert results.filter(approved_at__isnull=False).exists()
        assert results.filter(award=1).exists()

    edition = Edition.objects.get(status=EditionStatus.PUBLISHED)
    teams = Team.objects.filter(edition=edition)
    assert teams.filter(status=TeamStatus.DISQUALIFIED).exists()
    assert teams.filter(status=TeamStatus.DISBANDED).exists()
    assert teams.filter(situation=TeamSituation.INCOMPLETE).exists()
    scores = set(
        StageScore.objects.filter(project__edition=edition).values_list(
            "status", flat=True
        )
    )
    assert scores == {
        ScoreStatus.PENDING,
        ScoreStatus.DEFINITIVE,
        ScoreStatus.ZERO_NO_SUBMISSION,
    }

    assert "admin@desafiox.local" in saida
    assert "Aluno sem equipe com convite pendente" in saida


def test_recusa_banco_que_ja_tem_edicao(settings):
    settings.DEBUG = True
    EditionFactory()
    with pytest.raises(CommandError, match="já tem edição"):
        rodar()


def test_recusa_fora_de_desenvolvimento_e_homologacao(settings):
    settings.DEBUG = False
    settings.ALLOW_PASSWORD_LOGIN_FOR_ALL_ROLES = False
    with pytest.raises(CommandError, match="só roda"):
        rodar()
