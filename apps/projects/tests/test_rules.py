from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.factories import StudentFactory, UserFactory
from apps.core.factories import CourseFactory
from apps.editions.factories import ChallengeFactory, EditionFactory, StageFactory
from apps.projects.exceptions import (
    ChallengeNotEligible,
    ChallengeNotSelected,
    FormationClosed,
    NotTeamLeader,
)
from apps.projects.factories import ProjectFactory
from apps.projects.rules import (
    ensure_actor_is_team_leader,
    ensure_challenge_eligible,
    ensure_formation_period_is_open,
    ensure_project_has_challenge,
)
from apps.teams.enums import MemberRole
from apps.teams.factories import TeamFactory, TeamMemberFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def team():
    return TeamFactory()


def leader_user(team):
    return team.members.get(role=MemberRole.LEADER).student.user


def leader_course(team):
    return team.members.get(role=MemberRole.LEADER).student.course


def leave(member):
    member.active = False
    member.left_at = timezone.now()
    member.save()


# Líder da equipe (RF29, RF30)


def test_lider_ativo_passa(team):
    ensure_actor_is_team_leader(team, leader_user(team))


def test_integrante_comum_nao_e_lider(team):
    membro = TeamMemberFactory(team=team)
    with pytest.raises(NotTeamLeader):
        ensure_actor_is_team_leader(team, membro.student.user)


def test_ex_lider_inativo_nao_e_lider(team):
    leave(team.members.get(role=MemberRole.LEADER))
    with pytest.raises(NotTeamLeader):
        ensure_actor_is_team_leader(team, leader_user(team))


def test_lider_de_outra_equipe_nao_e_lider(team):
    with pytest.raises(NotTeamLeader):
        ensure_actor_is_team_leader(team, leader_user(TeamFactory()))


def test_admin_nao_e_lider(team):
    with pytest.raises(NotTeamLeader):
        ensure_actor_is_team_leader(team, UserFactory(role=UserRole.ADMIN))


def test_sem_ator_nao_e_lider(team):
    with pytest.raises(NotTeamLeader):
        ensure_actor_is_team_leader(team, None)


# Prazo de formação (RF29)


def formation(edition, start, end):
    now = timezone.now()
    return StageFactory(
        formation=True, edition=edition, starts_at=now + start, ends_at=now + end
    )


def test_prazo_aberto_passa(team):
    formation(team.edition, -timedelta(days=1), timedelta(days=1))
    ensure_formation_period_is_open(team.edition)


def test_prazo_que_ainda_nao_comecou_esta_fechado(team):
    formation(team.edition, timedelta(days=1), timedelta(days=2))
    with pytest.raises(FormationClosed):
        ensure_formation_period_is_open(team.edition)


def test_prazo_encerrado_esta_fechado(team):
    formation(team.edition, -timedelta(days=2), -timedelta(days=1))
    with pytest.raises(FormationClosed):
        ensure_formation_period_is_open(team.edition)


def test_sem_etapa_de_formacao_esta_fechado(team):
    with pytest.raises(FormationClosed):
        ensure_formation_period_is_open(team.edition)


def test_etapa_de_formacao_de_outra_edicao_nao_vale(team):
    formation(EditionFactory(), -timedelta(days=1), timedelta(days=1))
    with pytest.raises(FormationClosed):
        ensure_formation_period_is_open(team.edition)


def test_etapa_que_nao_e_de_formacao_nao_vale(team):
    now = timezone.now()
    StageFactory(
        edition=team.edition,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=1),
    )
    with pytest.raises(FormationClosed):
        ensure_formation_period_is_open(team.edition)


# Desafio elegível (RF29)


def test_desafio_de_curso_de_integrante_ativo_passa(team):
    desafio = ChallengeFactory(edition=team.edition, course=leader_course(team))
    ensure_challenge_eligible(team, desafio)


def test_desafio_de_curso_de_outro_integrante_ativo_passa(team):
    curso = CourseFactory()
    TeamMemberFactory(team=team, student=StudentFactory(course=curso))
    desafio = ChallengeFactory(edition=team.edition, course=curso)
    ensure_challenge_eligible(team, desafio)


def test_desafio_de_curso_sem_integrante_e_recusado(team):
    with pytest.raises(ChallengeNotEligible):
        ensure_challenge_eligible(team, ChallengeFactory(edition=team.edition))


def test_desafio_de_curso_so_de_ex_integrante_e_recusado(team):
    curso = CourseFactory()
    leave(TeamMemberFactory(team=team, student=StudentFactory(course=curso)))
    desafio = ChallengeFactory(edition=team.edition, course=curso)
    with pytest.raises(ChallengeNotEligible):
        ensure_challenge_eligible(team, desafio)


def test_desafio_inativo_e_recusado(team):
    desafio = ChallengeFactory(
        edition=team.edition, course=leader_course(team), active=False
    )
    with pytest.raises(ChallengeNotEligible):
        ensure_challenge_eligible(team, desafio)


def test_desafio_de_outra_edicao_e_recusado(team):
    desafio = ChallengeFactory(edition=EditionFactory(), course=leader_course(team))
    with pytest.raises(ChallengeNotEligible):
        ensure_challenge_eligible(team, desafio)


# Desafio já escolhido (RF30)


def test_projeto_com_desafio_passa():
    ensure_project_has_challenge(ProjectFactory())


def test_projeto_sem_desafio_e_recusado():
    with pytest.raises(ChallengeNotSelected):
        ensure_project_has_challenge(ProjectFactory(challenge=None))
