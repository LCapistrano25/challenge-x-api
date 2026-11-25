import pytest

from apps.accounts.factories import StudentFactory
from apps.core.tests.contract import mismatches, schema
from apps.editions.enums import EditionStatus
from apps.editions.factories import EditionFactory, StageFactory
from apps.evaluations.enums import ScoreStatus
from apps.evaluations.factories import StageScoreFactory
from apps.projects.factories import ProjectFactory
from apps.teams.enums import MemberRole, TeamSituation
from apps.teams.factories import (
    InvitationFactory,
    JoinRequestFactory,
    TeamFactory,
    TeamMemberFactory,
)
from apps.teams.rules import compute_unmet_requirements
from apps.teams.use_cases.get_student_dashboard import get_student_dashboard

pytestmark = pytest.mark.django_db


def test_academico_sem_equipe_tem_dashboard_vazio():
    edition = EditionFactory(status=EditionStatus.PUBLISHED)
    student = StudentFactory()

    dashboard = get_student_dashboard(actor=student.user)

    assert mismatches(dashboard, schema("StudentDashboard")) == []
    assert dashboard["edition"]["id"] == edition.pk
    assert dashboard["team"] is None
    assert dashboard["is_leader"] is False
    assert dashboard["incomplete_requirements"] == []
    assert dashboard["project"] is None
    assert dashboard["stages"] == []
    assert dashboard["pending_actions"] == []


def test_lider_visualiza_equipe_e_projeto():
    edition = EditionFactory(status=EditionStatus.PUBLISHED)
    team = TeamFactory(edition=edition)
    TeamMemberFactory(team=team)
    TeamMemberFactory(team=team)
    leader = team.members.get(role=MemberRole.LEADER, active=True)
    project = ProjectFactory(team=team, edition=edition)

    dashboard = get_student_dashboard(actor=leader.student.user)

    assert mismatches(dashboard, schema("StudentDashboard")) == []
    assert dashboard["team"]["id"] == team.pk
    assert dashboard["team"]["situation"] == team.situation
    assert dashboard["is_leader"] is True
    assert dashboard["project"]["id"] == project.pk
    assert dashboard["incomplete_requirements"] == []


def test_equipe_incompleta_apresenta_requisitos_nao_atendidos():
    edition = EditionFactory(
        status=EditionStatus.PUBLISHED,
        min_members=3,
    )
    team = TeamFactory(edition=edition, incomplete=True)
    leader = team.members.get(role=MemberRole.LEADER, active=True)

    dashboard = get_student_dashboard(actor=leader.student.user)

    assert dashboard["team"]["situation"] == TeamSituation.INCOMPLETE
    assert dashboard["incomplete_requirements"] == [
        "MIN_MEMBERS",
        "CHALLENGE_NOT_SELECTED",
        "PROJECT_DATA_MISSING",
    ]


def test_academico_sem_equipe_visualiza_convite_recebido():
    edition = EditionFactory(status=EditionStatus.PUBLISHED)
    student = StudentFactory()
    team = TeamFactory(edition=edition)

    invitation = InvitationFactory(
        team=team,
        student=student,
    )

    dashboard = get_student_dashboard(actor=student.user)

    assert dashboard["team"] is None
    assert len(dashboard["pending_actions"]) == 1
    assert dashboard["pending_actions"][0] == {
        "kind": "INVITATION_RECEIVED",
        "description": (f"Você recebeu um convite para entrar na equipe {team.name}."),
        "reference_id": invitation.pk,
    }


def test_lider_visualiza_solicitacao_de_entrada_pendente():
    edition = EditionFactory(status=EditionStatus.PUBLISHED)
    team = TeamFactory(edition=edition)
    leader = team.members.get(role=MemberRole.LEADER, active=True)

    join_request = JoinRequestFactory(team=team)

    dashboard = get_student_dashboard(actor=leader.student.user)

    actions = dashboard["pending_actions"]

    join_request_action = next(
        action for action in actions if action["kind"] == "JOIN_REQUEST_TO_REVIEW"
    )

    assert join_request_action["reference_id"] == join_request.pk


def test_lider_visualiza_pendencia_de_dados_do_projeto():
    edition = EditionFactory(status=EditionStatus.PUBLISHED)
    team = TeamFactory(edition=edition)
    leader = team.members.get(role=MemberRole.LEADER, active=True)

    dashboard = get_student_dashboard(actor=leader.student.user)

    actions = dashboard["pending_actions"]

    assert any(action["kind"] == "PROJECT_DATA_PENDING" for action in actions)


def test_lider_visualiza_entrega_pendente():
    edition = EditionFactory(status=EditionStatus.PUBLISHED)
    team = TeamFactory(edition=edition)
    leader = team.members.get(role=MemberRole.LEADER, active=True)

    ProjectFactory(team=team, edition=edition)
    stage = StageFactory(edition=edition)

    dashboard = get_student_dashboard(actor=leader.student.user)

    pending_deliverable = next(
        action
        for action in dashboard["pending_actions"]
        if action["kind"] == "DELIVERABLE_PENDING"
    )

    assert pending_deliverable["reference_id"] == stage.pk


def test_equipe_completa_nao_apresenta_requisitos_pendentes():
    edition = EditionFactory(status=EditionStatus.PUBLISHED)
    team = TeamFactory(edition=edition, situation=TeamSituation.COMPLETE)
    leader = team.members.get(role=MemberRole.LEADER, active=True)

    dashboard = get_student_dashboard(actor=leader.student.user)

    assert dashboard["team"]["situation"] == TeamSituation.COMPLETE
    assert dashboard["incomplete_requirements"] == []


def test_dashboard_nao_altera_situacao_incompleta_registrada():
    edition = EditionFactory(
        status=EditionStatus.PUBLISHED,
        min_members=3,
    )
    team = TeamFactory(edition=edition, incomplete=True)
    leader = team.members.get(role=MemberRole.LEADER, active=True)

    TeamMemberFactory(team=team, edition=edition)
    TeamMemberFactory(team=team, edition=edition)
    ProjectFactory(team=team, edition=edition)

    dashboard = get_student_dashboard(actor=leader.student.user)

    team.refresh_from_db()

    assert team.situation == TeamSituation.INCOMPLETE
    assert dashboard["team"]["situation"] == TeamSituation.INCOMPLETE
    assert dashboard["incomplete_requirements"] == []


def test_equipe_com_requisitos_nao_atendidos_apresenta_motivos():
    edition = EditionFactory(
        status=EditionStatus.PUBLISHED,
        min_members=3,
    )
    team = TeamFactory(
        edition=edition,
        situation=TeamSituation.REQUIREMENTS_NOT_MET,
    )
    leader = team.members.get(role=MemberRole.LEADER, active=True)

    dashboard = get_student_dashboard(actor=leader.student.user)

    assert dashboard["team"]["situation"] == TeamSituation.REQUIREMENTS_NOT_MET
    assert dashboard["incomplete_requirements"] == [
        "MIN_MEMBERS",
        "CHALLENGE_NOT_SELECTED",
        "PROJECT_DATA_MISSING",
    ]


def test_equipe_incompleta_apenas_por_falta_de_integrantes():
    edition = EditionFactory(
        status=EditionStatus.PUBLISHED,
        min_members=3,
    )
    team = TeamFactory(edition=edition, incomplete=True)
    leader = team.members.get(role=MemberRole.LEADER, active=True)
    ProjectFactory(team=team, edition=edition)

    dashboard = get_student_dashboard(actor=leader.student.user)

    assert dashboard["incomplete_requirements"] == ["MIN_MEMBERS"]


def test_equipe_incompleta_apenas_por_falta_de_desafio():
    edition = EditionFactory(
        status=EditionStatus.PUBLISHED,
        min_members=1,
    )
    team = TeamFactory(edition=edition, incomplete=True)
    leader = team.members.get(role=MemberRole.LEADER, active=True)
    ProjectFactory(team=team, edition=edition, challenge=None)

    dashboard = get_student_dashboard(actor=leader.student.user)

    assert dashboard["incomplete_requirements"] == ["CHALLENGE_NOT_SELECTED"]


def test_equipe_incompleta_apenas_por_dados_do_projeto():
    edition = EditionFactory(
        status=EditionStatus.PUBLISHED,
        min_members=1,
    )
    team = TeamFactory(edition=edition, incomplete=True)
    leader = team.members.get(role=MemberRole.LEADER, active=True)
    ProjectFactory(
        team=team,
        edition=edition,
        title="",
        summary="Resumo válido.",
    )

    dashboard = get_student_dashboard(actor=leader.student.user)

    assert dashboard["incomplete_requirements"] == ["PROJECT_DATA_MISSING"]


def test_academico_sem_edicao_publicada_tem_dashboard_vazio():
    EditionFactory(status=EditionStatus.SETUP)
    student = StudentFactory()

    dashboard = get_student_dashboard(actor=student.user)

    assert dashboard["edition"] is None
    assert dashboard["team"] is None
    assert dashboard["is_leader"] is False
    assert dashboard["incomplete_requirements"] == []
    assert dashboard["project"] is None
    assert dashboard["stages"] == []
    assert dashboard["pending_actions"] == []
    assert mismatches(dashboard, schema("StudentDashboard")) == []


def test_dashboard_apresenta_etapas_com_situacoes_corretas():
    from datetime import timedelta

    from django.utils import timezone

    edition = EditionFactory(status=EditionStatus.PUBLISHED)
    team = TeamFactory(edition=edition)
    leader = team.members.get(role=MemberRole.LEADER, active=True)
    ProjectFactory(team=team, edition=edition)
    now = timezone.now()

    upcoming = StageFactory(
        edition=edition,
        order=1,
        starts_at=now + timedelta(days=2),
        ends_at=now + timedelta(days=5),
        scored=True,
    )
    opened = StageFactory(
        edition=edition,
        order=2,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=5),
        scored=True,
    )
    finished = StageFactory(
        edition=edition,
        order=3,
        starts_at=now - timedelta(days=10),
        ends_at=now - timedelta(days=2),
        scored=True,
    )

    dashboard = get_student_dashboard(actor=leader.student.user)

    stages = dashboard["stages"]

    assert [item["stage"]["id"] for item in stages] == [
        upcoming.pk,
        opened.pk,
        finished.pk,
    ]
    assert [item["stage"]["phase_status"] for item in stages] == [
        "UPCOMING",
        "OPEN",
        "FINISHED",
    ]
    assert all(item["stage"]["evaluation_ends_at"] for item in stages)
    assert mismatches(dashboard, schema("StudentDashboard")) == []


def test_dashboard_apresenta_notas_pendentes_e_definitivas():
    edition = EditionFactory(status=EditionStatus.PUBLISHED)
    team = TeamFactory(edition=edition)
    leader = team.members.get(role=MemberRole.LEADER, active=True)
    project = ProjectFactory(team=team, edition=edition)

    pending_stage = StageFactory(
        edition=edition,
        order=1,
        scored=True,
    )
    definitive_stage = StageFactory(
        edition=edition,
        order=2,
        scored=True,
    )

    StageScoreFactory(
        project=project,
        stage=definitive_stage,
        definitive=True,
    )

    dashboard = get_student_dashboard(actor=leader.student.user)

    scores = {item["stage"]["id"]: item["score"] for item in dashboard["stages"]}

    assert scores[pending_stage.pk] == {
        "status": "PENDING",
        "value": None,
    }
    assert scores[definitive_stage.pk] == {
        "status": "DEFINITIVE",
        "value": "2.50",
    }
    assert mismatches(dashboard, schema("StudentDashboard")) == []


def test_dashboard_apresenta_zero_por_falta_de_entrega():
    from datetime import timedelta

    from django.utils import timezone

    edition = EditionFactory(status=EditionStatus.PUBLISHED)
    team = TeamFactory(edition=edition)
    leader = team.members.get(role=MemberRole.LEADER, active=True)
    project = ProjectFactory(team=team, edition=edition)

    stage = StageFactory(
        edition=edition,
        starts_at=timezone.now() - timedelta(days=20),
        scored=True,
    )

    StageScoreFactory(
        project=project,
        stage=stage,
        status=ScoreStatus.ZERO_NO_SUBMISSION,
        value=0,
    )

    dashboard = get_student_dashboard(actor=leader.student.user)

    stage_data = next(
        item for item in dashboard["stages"] if item["stage"]["id"] == stage.pk
    )

    assert stage_data["score"] == {
        "status": "ZERO_NO_SUBMISSION",
        "value": "0.00",
    }
    assert stage_data["deliverable_status"] == "NOT_DELIVERED"
    assert mismatches(dashboard, schema("StudentDashboard")) == []


def test_equipe_incompleta_apenas_por_resumo_ausente():
    edition = EditionFactory(
        status=EditionStatus.PUBLISHED,
        min_members=1,
    )
    team = TeamFactory(edition=edition, incomplete=True)
    leader = team.members.get(role=MemberRole.LEADER, active=True)

    ProjectFactory(
        team=team,
        edition=edition,
        title="Projeto válido",
        summary="",
    )

    dashboard = get_student_dashboard(actor=leader.student.user)

    assert dashboard["incomplete_requirements"] == ["PROJECT_DATA_MISSING"]


def test_compute_unmet_requirements_identifica_excesso_de_integrantes():
    edition = EditionFactory(
        status=EditionStatus.PUBLISHED,
        min_members=1,
        max_members=1,
    )
    team = TeamFactory(edition=edition)
    TeamMemberFactory(team=team, edition=edition)

    ProjectFactory(team=team, edition=edition)

    assert compute_unmet_requirements(team) == ["2 integrantes; o máximo é 1."]
