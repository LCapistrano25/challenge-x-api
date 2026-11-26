from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.editions.enums import EditionStatus
from apps.editions.factories import EditionFactory, StageFactory
from apps.teams.enums import TeamSituation
from apps.teams.factories import TeamFactory
from apps.teams.use_cases.flag_team_status import flag_team_status

pytestmark = pytest.mark.django_db


def criar_equipe_elegivel():
    edition = EditionFactory(status=EditionStatus.PUBLISHED)
    team = TeamFactory(edition=edition)
    now = timezone.now()

    StageFactory(
        edition=edition,
        formation=True,
        starts_at=now - timedelta(days=10),
        ends_at=now - timedelta(hours=1),
    )

    return team


def test_comando_classifica_equipe_elegivel():
    team = criar_equipe_elegivel()

    call_command("classify_team_status")

    team.refresh_from_db()
    assert team.situation == TeamSituation.INCOMPLETE


def test_comando_tenta_novamente_equipe_que_falhou(monkeypatch, caplog):
    team = criar_equipe_elegivel()
    tentativas = 0

    def falhar_na_primeira_tentativa(*, team_id):
        nonlocal tentativas
        tentativas += 1

        if tentativas == 1:
            raise RuntimeError("Falha simulada.")

        return flag_team_status(team_id=team_id)

    monkeypatch.setattr(
        "apps.teams.management.commands.classify_team_status.flag_team_status",
        falhar_na_primeira_tentativa,
    )

    call_command("classify_team_status")

    team.refresh_from_db()
    assert team.situation is None
    assert "Falha ao classificar a equipe" in caplog.text

    call_command("classify_team_status")

    team.refresh_from_db()
    assert team.situation == TeamSituation.INCOMPLETE
    assert tentativas == 2


def test_comando_ignora_equipe_com_formacao_aberta(caplog):
    edition = EditionFactory(status=EditionStatus.PUBLISHED)
    team = TeamFactory(edition=edition)
    now = timezone.now()

    StageFactory(
        edition=edition,
        formation=True,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(hours=2),
    )

    call_command("classify_team_status")

    team.refresh_from_db()
    assert team.situation is None
    assert "Falha ao classificar a equipe" not in caplog.text
