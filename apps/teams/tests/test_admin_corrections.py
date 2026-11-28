import pytest
from django.urls import reverse

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import NotAdminActor
from apps.accounts.factories import StudentFactory, UserFactory
from apps.editions.enums import EditionStatus
from apps.editions.exceptions import EditionClosed
from apps.editions.factories import EditionFactory
from apps.notifications.models import Notification
from apps.projects.enums import ProjectStatus
from apps.projects.factories import ProjectFactory
from apps.teams.enums import MemberRole, TeamStatus
from apps.teams.exceptions import InvalidNewLeader, TeamNotActive, TeamNotDisqualified
from apps.teams.factories import TeamFactory, TeamMemberFactory
from apps.teams.models import Team, TeamMember
from apps.teams.use_cases.assign_leader import assign_leader
from apps.teams.use_cases.disqualify_team import disqualify_team
from apps.teams.use_cases.reinstate_team import reinstate_team

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_user():
    return UserFactory(role=UserRole.ADMIN)


@pytest.fixture
def disqualified(admin_user):
    # disqualify_team só age em edição publicada (a vigente).
    project = ProjectFactory(team__edition__status=EditionStatus.PUBLISHED)
    disqualify_team(actor=admin_user, team_id=project.team_id, reason="Plágio")
    return Team.objects.get(pk=project.team_id)


def leader_of(team):
    return team.members.get(active=True, role=MemberRole.LEADER)


# Reverter desclassificação


def test_reverte_desclassificacao_e_volta_o_projeto(admin_user, disqualified):
    reinstate_team(actor=admin_user, team=disqualified)

    disqualified.refresh_from_db()
    assert disqualified.status == TeamStatus.ACTIVE
    assert disqualified.disqualification_reason == ""
    assert disqualified.disqualified_at is None
    assert disqualified.disqualified_by is None
    assert disqualified.project.status == ProjectStatus.IN_PROGRESS
    assert Notification.objects.filter(title="Desclassificação revertida").exists()


def test_equipe_ativa_nao_e_revertida(admin_user):
    with pytest.raises(TeamNotDisqualified):
        reinstate_team(actor=admin_user, team=TeamFactory())


def test_edicao_encerrada_nao_reverte(admin_user, disqualified):
    disqualified.edition.status = EditionStatus.CLOSED
    disqualified.edition.save()

    with pytest.raises(EditionClosed):
        reinstate_team(actor=admin_user, team=disqualified)


def test_so_admin_reverte(disqualified):
    with pytest.raises(NotAdminActor):
        reinstate_team(actor=UserFactory(role=UserRole.TEACHER), team=disqualified)

    disqualified.refresh_from_db()
    assert disqualified.status == TeamStatus.DISQUALIFIED


# Trocar líder


def test_admin_troca_o_lider(admin_user):
    team = TeamFactory()
    old = leader_of(team)
    new = TeamMemberFactory(team=team)

    assign_leader(actor=admin_user, member=new)

    old.refresh_from_db()
    new.refresh_from_db()
    assert old.role == MemberRole.MEMBER
    assert new.role == MemberRole.LEADER
    assert Notification.objects.filter(title="Liderança da equipe alterada").exists()


def test_admin_define_lider_em_equipe_sem_lider(admin_user):
    member = TeamMemberFactory()

    assign_leader(actor=admin_user, member=member)

    member.refresh_from_db()
    assert member.role == MemberRole.LEADER


def test_integrante_inativo_ou_ja_lider_nao_vira_lider(admin_user):
    team = TeamFactory()
    inactive = TeamMemberFactory(team=team, active=False, left_at="2026-01-01T00:00Z")

    with pytest.raises(InvalidNewLeader):
        assign_leader(actor=admin_user, member=inactive)
    with pytest.raises(InvalidNewLeader):
        assign_leader(actor=admin_user, member=leader_of(team))


def test_equipe_desclassificada_nao_troca_lider(admin_user, disqualified):
    member = TeamMemberFactory(team=disqualified)

    with pytest.raises(TeamNotActive):
        assign_leader(actor=admin_user, member=member)


# Django admin


@pytest.fixture
def admin_client(client, admin_user):
    client.force_login(admin_user)
    return client


def test_acao_do_admin_reverte_desclassificacao(admin_client, disqualified):
    admin_client.post(
        reverse("admin:teams_team_changelist"),
        {"action": "reinstate_team_action", "_selected_action": [disqualified.pk]},
    )

    disqualified.refresh_from_db()
    assert disqualified.status == TeamStatus.ACTIVE


def test_acao_do_admin_troca_lider_e_integrante_e_somente_leitura(admin_client):
    team = TeamFactory()
    member = TeamMemberFactory(team=team)

    admin_client.post(
        reverse("admin:teams_teammember_changelist"),
        {"action": "assign_leader_action", "_selected_action": [member.pk]},
    )
    change = admin_client.post(
        reverse("admin:teams_teammember_change", args=[member.pk]), {"role": "MEMBER"}
    )

    member.refresh_from_db()
    assert member.role == MemberRole.LEADER
    assert change.status_code == 403


def test_inline_recusa_integrantes_acima_do_maximo(admin_client):
    edition = EditionFactory(min_members=1, max_members=1)
    team = TeamFactory(edition=edition)
    leader = leader_of(team)
    extra = StudentFactory()
    prefix = "members"

    response = admin_client.post(
        reverse("admin:teams_team_change", args=[team.pk]),
        {
            "edition": edition.pk,
            "name": team.name,
            "code": team.code,
            "status": team.status,
            "disqualification_reason": "",
            f"{prefix}-TOTAL_FORMS": "2",
            f"{prefix}-INITIAL_FORMS": "1",
            f"{prefix}-0-id": leader.pk,
            f"{prefix}-0-team": team.pk,
            f"{prefix}-0-edition": edition.pk,
            f"{prefix}-0-student": leader.student_id,
            f"{prefix}-0-role": MemberRole.LEADER,
            f"{prefix}-0-active": "on",
            f"{prefix}-1-team": team.pk,
            f"{prefix}-1-edition": edition.pk,
            f"{prefix}-1-student": extra.pk,
            f"{prefix}-1-role": MemberRole.MEMBER,
            f"{prefix}-1-active": "on",
        },
    )

    assert response.status_code == 200  # formulário volta com erro
    assert "o máximo é 1" in response.content.decode()
    assert TeamMember.objects.filter(team=team).count() == 1
