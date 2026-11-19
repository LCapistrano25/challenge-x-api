from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.factories import StudentFactory, UserFactory
from apps.core.factories import CourseFactory
from apps.editions.enums import FieldKind, StageKind
from apps.editions.factories import (
    CategoryFactory,
    ChallengeFactory,
    EditionFactory,
    StageFactory,
    StageSubmissionFieldFactory,
)
from apps.projects.exceptions import (
    CategoryNotAvailable,
    ChallengeNotEligible,
    ChallengeNotSelected,
    FormationClosed,
    NotTeamLeader,
    ProjectNotFound,
    StageDeadlineClosed,
    StageNotFound,
    StageNotOpen,
    TeamDisqualified,
    TeamIncomplete,
)
from apps.projects.factories import DeadlineExtensionFactory, ProjectFactory
from apps.projects.rules import (
    ensure_actor_is_team_leader,
    ensure_category_available,
    ensure_challenge_eligible,
    ensure_formation_period_is_open,
    ensure_items_match_stage_fields,
    ensure_project_has_challenge,
    ensure_stage_accepts_delivery,
    ensure_stage_deadline_open,
    ensure_team_has_project,
    ensure_team_not_disqualified,
    ensure_team_not_incomplete,
)
from apps.teams.enums import MemberRole, TeamSituation
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


# Projeto da equipe já existe (RF30)


def test_equipe_com_projeto_passa(team):
    ProjectFactory(team=team)
    ensure_team_has_project(team)


def test_equipe_sem_projeto_e_recusada(team):
    with pytest.raises(ProjectNotFound):
        ensure_team_has_project(team)


# Categoria disponível (RF30, RF49)


def test_categoria_ativa_da_edicao_passa(team):
    ensure_category_available(team, CategoryFactory(edition=team.edition))


def test_categoria_inativa_e_recusada(team):
    categoria = CategoryFactory(edition=team.edition, active=False)
    with pytest.raises(CategoryNotAvailable):
        ensure_category_available(team, categoria)


def test_categoria_de_outra_edicao_e_recusada(team):
    with pytest.raises(CategoryNotAvailable):
        ensure_category_available(team, CategoryFactory())


# Entrega da etapa (UC34, RF31)


def open_stage(edition, **fields):
    now = timezone.now()
    defaults = {
        "starts_at": now - timedelta(days=1),
        "ends_at": now + timedelta(days=1),
    }
    return StageFactory(edition=edition, **{**defaults, **fields})


def closed_stage(edition, **fields):
    now = timezone.now()
    return open_stage(
        edition,
        starts_at=now - timedelta(days=5),
        ends_at=now - timedelta(days=1),
        **fields,
    )


def test_equipe_ativa_passa_na_desclassificacao(team):
    ensure_team_not_disqualified(team)


def test_equipe_desclassificada_e_recusada():
    with pytest.raises(TeamDisqualified):
        ensure_team_not_disqualified(TeamFactory(disqualified=True))


@pytest.mark.parametrize("situation", [None, TeamSituation.COMPLETE])
def test_equipe_completa_ou_sem_situacao_passa(situation):
    ensure_team_not_incomplete(TeamFactory(situation=situation))


@pytest.mark.parametrize(
    "situation", [TeamSituation.INCOMPLETE, TeamSituation.REQUIREMENTS_NOT_MET]
)
def test_equipe_incompleta_e_recusada(situation):
    with pytest.raises(TeamIncomplete):
        ensure_team_not_incomplete(TeamFactory(situation=situation))


def test_etapa_de_entrega_da_edicao_passa():
    project = ProjectFactory()
    ensure_stage_accepts_delivery(project, open_stage(project.edition))


def test_etapa_de_formacao_e_recusada():
    project = ProjectFactory()
    stage = StageFactory(formation=True, edition=project.edition)
    with pytest.raises(StageNotFound):
        ensure_stage_accepts_delivery(project, stage)


def test_etapa_final_e_recusada():
    project = ProjectFactory()
    stage = StageFactory(edition=project.edition, kind=StageKind.FINAL, scored=False)
    with pytest.raises(StageNotFound):
        ensure_stage_accepts_delivery(project, stage)


def test_etapa_de_outra_edicao_e_recusada():
    with pytest.raises(StageNotFound):
        ensure_stage_accepts_delivery(ProjectFactory(), StageFactory())


def test_prazo_de_entrega_aberto_passa():
    project = ProjectFactory()
    ensure_stage_deadline_open(project, open_stage(project.edition))


def test_prazo_encerrado_e_recusado():
    project = ProjectFactory()
    with pytest.raises(StageDeadlineClosed):
        ensure_stage_deadline_open(project, closed_stage(project.edition))


def test_prorrogacao_ativa_libera_o_prazo_encerrado():
    project = ProjectFactory()
    stage = closed_stage(project.edition)
    DeadlineExtensionFactory(
        project=project, stage=stage, ends_at=timezone.now() + timedelta(days=1)
    )
    ensure_stage_deadline_open(project, stage)


def test_prorrogacao_vencida_e_recusada():
    project = ProjectFactory()
    stage = closed_stage(project.edition)
    DeadlineExtensionFactory(
        project=project, stage=stage, ends_at=stage.ends_at + timedelta(hours=1)
    )
    with pytest.raises(StageDeadlineClosed):
        ensure_stage_deadline_open(project, stage)


def test_antes_do_inicio_e_recusado():
    project = ProjectFactory()
    now = timezone.now()
    stage = open_stage(
        project.edition,
        starts_at=now + timedelta(days=1),
        ends_at=now + timedelta(days=5),
    )
    with pytest.raises(StageNotOpen):
        ensure_stage_deadline_open(project, stage)


@pytest.fixture
def stage():
    return StageFactory()


def link_item(field, link="https://github.com/equipe/projeto"):
    return {"field": field, "link": link}


def test_itens_completos_passam(stage):
    field = StageSubmissionFieldFactory(stage=stage)
    ensure_items_match_stage_fields(stage, [link_item(field)])


def test_campo_obrigatorio_sem_resposta_e_recusado(stage):
    answered = StageSubmissionFieldFactory(stage=stage)
    StageSubmissionFieldFactory(stage=stage, required=True)
    with pytest.raises(ValidationError):
        ensure_items_match_stage_fields(stage, [link_item(answered)])


def test_campo_opcional_pode_faltar(stage):
    answered = StageSubmissionFieldFactory(stage=stage)
    StageSubmissionFieldFactory(stage=stage, required=False)
    ensure_items_match_stage_fields(stage, [link_item(answered)])


def test_campo_de_outra_etapa_e_recusado(stage):
    StageSubmissionFieldFactory(stage=stage)
    other = StageSubmissionFieldFactory()
    with pytest.raises(ValidationError):
        ensure_items_match_stage_fields(stage, [link_item(other)])


def test_campo_repetido_e_recusado(stage):
    field = StageSubmissionFieldFactory(stage=stage)
    with pytest.raises(ValidationError):
        ensure_items_match_stage_fields(stage, [link_item(field), link_item(field)])


def test_campo_de_arquivo_e_recusado(stage):
    field = StageSubmissionFieldFactory(stage=stage, kind=FieldKind.FILE)
    with pytest.raises(ValidationError):
        ensure_items_match_stage_fields(stage, [link_item(field)])


def test_campo_de_arquivo_obrigatorio_nao_bloqueia_o_envio(stage):
    link_field = StageSubmissionFieldFactory(stage=stage)
    StageSubmissionFieldFactory(stage=stage, kind=FieldKind.FILE, required=True)
    ensure_items_match_stage_fields(stage, [link_item(link_field)])


def test_lista_de_itens_vazia_e_recusada(stage):
    with pytest.raises(ValidationError):
        ensure_items_match_stage_fields(stage, [])
