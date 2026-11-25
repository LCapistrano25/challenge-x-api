from datetime import timedelta

import pytest
from django.utils import timezone

from apps.editions.factories import CategoryFactory, StageFactory
from apps.projects.factories import ProjectFactory
from apps.teams.enums import MemberRole, TeamSituation, TeamStatus
from apps.teams.factories import TeamFactory, TeamMemberFactory
from apps.teams.use_cases.flag_team_status import (
    FlagTeamStatusRejected,
    flag_team_status,
)

pytestmark = pytest.mark.django_db


def criar_formacao(team, starts_at, ends_at):
    return StageFactory(
        edition=team.edition,
        formation=True,
        starts_at=starts_at,
        ends_at=ends_at,
    )


def criar_equipe_completa():
    team = TeamFactory()
    ProjectFactory(
        team=team,
        category=CategoryFactory(edition=team.edition),
    )
    for _ in range(2):
        TeamMemberFactory(
            team=team,
            edition=team.edition,
            role=MemberRole.MEMBER,
        )
    return team


def test_classifica_equipe_completa_apos_fim_da_formacao():
    now = timezone.now()
    team = criar_equipe_completa()
    criar_formacao(
        team,
        starts_at=now - timedelta(days=10),
        ends_at=now - timedelta(hours=1),
    )

    result = flag_team_status(team_id=team.pk)

    result.refresh_from_db()
    assert result.situation == TeamSituation.COMPLETE


def test_classifica_equipe_incompleta_apos_fim_da_formacao():
    now = timezone.now()
    team = TeamFactory()
    criar_formacao(
        team,
        starts_at=now - timedelta(days=10),
        ends_at=now - timedelta(hours=1),
    )

    result = flag_team_status(team_id=team.pk)

    result.refresh_from_db()
    assert result.situation == TeamSituation.INCOMPLETE


def test_nao_classifica_antes_do_inicio_da_formacao():
    now = timezone.now()
    team = TeamFactory()
    criar_formacao(
        team,
        starts_at=now + timedelta(hours=1),
        ends_at=now + timedelta(days=10),
    )

    with pytest.raises(
        FlagTeamStatusRejected,
        match="O período de formação ainda não começou.",
    ):
        flag_team_status(team_id=team.pk)

    team.refresh_from_db()
    assert team.situation is None


def test_nao_classifica_com_formacao_aberta():
    now = timezone.now()
    team = TeamFactory()
    criar_formacao(
        team,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(hours=1),
    )

    with pytest.raises(
        FlagTeamStatusRejected,
        match="O período de formação ou a extensão ainda está aberto.",
    ):
        flag_team_status(team_id=team.pk)

    team.refresh_from_db()
    assert team.situation is None


def test_nao_classifica_com_extensao_ativa():
    now = timezone.now()
    team = TeamFactory()
    criar_formacao(
        team,
        starts_at=now - timedelta(days=10),
        ends_at=now - timedelta(hours=1),
    )
    team.formation_extended_until = now + timedelta(hours=2)
    team.save(update_fields=["formation_extended_until"])

    with pytest.raises(
        FlagTeamStatusRejected,
        match="O período de formação ou a extensão ainda está aberto.",
    ):
        flag_team_status(team_id=team.pk)

    team.refresh_from_db()
    assert team.situation is None


def test_rejeita_edicao_sem_etapa_de_formacao():
    team = TeamFactory()

    with pytest.raises(
        FlagTeamStatusRejected,
        match="Não existe etapa de formação para a edição da equipe.",
    ):
        flag_team_status(team_id=team.pk)

    team.refresh_from_db()
    assert team.situation is None


def test_rejeita_equipe_inexistente():
    with pytest.raises(
        FlagTeamStatusRejected,
        match="Equipe não encontrada.",
    ):
        flag_team_status(team_id=999999)


def test_nao_sobrescreve_situacao_ja_definida():
    team = TeamFactory(incomplete=True)

    result = flag_team_status(team_id=team.pk)

    result.refresh_from_db()
    assert result.situation == TeamSituation.INCOMPLETE


@pytest.mark.parametrize(
    "team_status",
    [TeamStatus.DISQUALIFIED, TeamStatus.DISBANDED],
)
def test_nao_classifica_equipe_que_nao_esta_ativa(team_status):
    if team_status == TeamStatus.DISQUALIFIED:
        team = TeamFactory(disqualified=True)
    else:
        team = TeamFactory(status=team_status)

    with pytest.raises(
        FlagTeamStatusRejected,
        match="Apenas equipes ativas podem ser classificadas.",
    ):
        flag_team_status(team_id=team.pk)

    team.refresh_from_db()
    assert team.status == team_status
    assert team.situation is None
