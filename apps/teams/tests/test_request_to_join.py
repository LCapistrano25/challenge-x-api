
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.factories import StudentFactory, UserFactory
from apps.editions.factories import StageFactory
from apps.notifications.models import Notification, NotificationType
from apps.teams.enums import MemberRole, RequestStatus
from apps.teams.factories import (
    JoinRequestFactory,
    TeamFactory,
    TeamMemberFactory,
)
from apps.teams.models import JoinRequest
from apps.teams.use_cases.request_to_join import (
    JoinRequestRejected,
    request_to_join,
)

pytestmark = pytest.mark.django_db


def create_open_formation(edition):
    now = timezone.now()
    StageFactory(
        edition=edition,
        formation=True,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=7),
    )


def get_leader(team):
    membership = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    )
    return membership.student.user


def test_aluno_solicita_entrada_em_equipe_com_sucesso():
    team = TeamFactory()
    create_open_formation(team.edition)
    student = StudentFactory()

    join_request = request_to_join(
        actor=student.user,
        team_id=team.id,
    )

    assert isinstance(join_request, JoinRequest)
    assert join_request.team == team
    assert join_request.student == student
    assert join_request.status == RequestStatus.PENDING
    assert JoinRequest.objects.count() == 1

    notification = Notification.objects.get(user=get_leader(team))

    assert notification.type == NotificationType.TEAM
    assert notification.title == "Nova solicitação para equipe"
    assert notification.message == (
        f"Um aluno solicitou entrada na equipe {team.name}."
    )
    assert notification.link == f"/equipes/{team.id}"
    assert notification.read_at is None


def test_usuario_que_nao_e_aluno_nao_pode_solicitar_entrada():
    team = TeamFactory()
    create_open_formation(team.edition)
    user = UserFactory(role=UserRole.TEACHER)

    with pytest.raises(
        JoinRequestRejected,
        match="Somente alunos podem solicitar entrada em equipes.",
    ):
        request_to_join(actor=user, team_id=team.id)

    assert JoinRequest.objects.count() == 0


def test_aluno_sem_perfil_nao_pode_solicitar_entrada():
    team = TeamFactory()
    create_open_formation(team.edition)
    user = UserFactory(role=UserRole.STUDENT)

    with pytest.raises(
        JoinRequestRejected,
        match="O perfil de aluno não foi encontrado.",
    ):
        request_to_join(actor=user, team_id=team.id)

    assert JoinRequest.objects.count() == 0


def test_equipe_inexistente_nao_pode_receber_solicitacao():
    student = StudentFactory()

    with pytest.raises(
        JoinRequestRejected,
        match="Equipe não encontrada.",
    ):
        request_to_join(actor=student.user, team_id=999999)

    assert JoinRequest.objects.count() == 0


def test_nao_pode_solicitar_entrada_sem_formacao_aberta():
    team = TeamFactory()
    student = StudentFactory()

    with pytest.raises(
        JoinRequestRejected,
        match="Não existe prazo de formação aberto para esta equipe.",
    ):
        request_to_join(actor=student.user, team_id=team.id)

    assert JoinRequest.objects.count() == 0


def test_equipe_sem_vagas_nao_pode_receber_solicitacao():
    team = TeamFactory()
    create_open_formation(team.edition)
    student = StudentFactory()

    for _ in range(team.edition.max_members - 1):
        TeamMemberFactory(team=team)

    with pytest.raises(
        JoinRequestRejected,
        match="A equipe já atingiu o limite máximo de integrantes.",
    ):
        request_to_join(actor=student.user, team_id=team.id)

    assert JoinRequest.objects.count() == 0


def test_aluno_inativo_nao_pode_solicitar_entrada():
    student = StudentFactory(user__is_active=False)
    team = TeamFactory()
    create_open_formation(team.edition)

    with pytest.raises(
        JoinRequestRejected,
        match="O cadastro do aluno deve estar ativo e confirmado.",
    ):
        request_to_join(actor=student.user, team_id=team.id)

    assert JoinRequest.objects.count() == 0


def test_aluno_com_email_nao_confirmado_nao_pode_solicitar_entrada():
    student = StudentFactory(user__email_confirmed=False)
    team = TeamFactory()
    create_open_formation(team.edition)

    with pytest.raises(
        JoinRequestRejected,
        match="O cadastro do aluno deve estar ativo e confirmado.",
    ):
        request_to_join(actor=student.user, team_id=team.id)

    assert JoinRequest.objects.count() == 0


def test_aluno_que_ja_esta_em_outra_equipe_nao_pode_solicitar_entrada():
    team = TeamFactory()
    create_open_formation(team.edition)
    student = StudentFactory()

    other_team = TeamFactory(edition=team.edition)
    TeamMemberFactory(
        team=other_team,
        student=student,
    )

    with pytest.raises(
        JoinRequestRejected,
        match="O aluno já participa de uma equipe ativa nesta edição.",
    ):
        request_to_join(actor=student.user, team_id=team.id)

    assert JoinRequest.objects.count() == 0


def test_nao_pode_enviar_solicitacao_duplicada():
    team = TeamFactory()
    create_open_formation(team.edition)
    student = StudentFactory()

    JoinRequestFactory(
        team=team,
        student=student,
        status=RequestStatus.PENDING,
    )

    with pytest.raises(
        JoinRequestRejected,
        match="Já existe uma solicitação pendente para esta equipe.",
    ):
        request_to_join(actor=student.user, team_id=team.id)

    assert JoinRequest.objects.filter(
        team=team,
        student=student,
        status=RequestStatus.PENDING,
    ).count() == 1


def test_equipe_desclassificada_nao_pode_receber_solicitacao():
    team = TeamFactory(disqualified=True)
    create_open_formation(team.edition)
    student = StudentFactory()

    with pytest.raises(
        JoinRequestRejected,
        match="Não é possível solicitar entrada em uma equipe desclassificada.",
    ):
        request_to_join(actor=student.user, team_id=team.id)

    assert JoinRequest.objects.count() == 0


def test_equipe_sem_lider_ativo_nao_pode_receber_solicitacao():
    team = TeamFactory()
    create_open_formation(team.edition)

    leader_membership = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    )
    leader_membership.active = False
    leader_membership.left_at = timezone.now()
    leader_membership.save(update_fields=["active", "left_at"])

    student = StudentFactory()

    with pytest.raises(
        JoinRequestRejected,
        match="A equipe não possui um líder ativo.",
    ):
        request_to_join(actor=student.user, team_id=team.id)

    assert JoinRequest.objects.count() == 0


def test_reverte_operacao_se_ocorrer_erro_ao_criar_solicitacao():
    team = TeamFactory()
    create_open_formation(team.edition)
    student = StudentFactory()

    with patch(
        "apps.teams.use_cases.request_to_join.JoinRequest.objects.create",
        side_effect=IntegrityError("Erro simulado"),
    ):
        with pytest.raises(
            JoinRequestRejected,
            match="Não foi possível registrar a solicitação.",
        ):
            request_to_join(actor=student.user, team_id=team.id)

    assert JoinRequest.objects.count() == 0
    assert Notification.objects.count() == 0
