from datetime import timedelta
from unittest.mock import patch

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.factories import UserFactory
from apps.editions.factories import StageFactory
from apps.notifications.models import Notification, NotificationType
from apps.teams.enums import (
    InvitationStatus,
    MemberRole,
    RequestStatus,
    TeamStatus,
)
from apps.teams.factories import (
    InvitationFactory,
    JoinRequestFactory,
    TeamFactory,
    TeamMemberFactory,
)
from apps.teams.models import JoinRequest, TeamMember
from apps.teams.use_cases.respond_join_request import (
    JoinRequestResponseRejected,
    respond_join_request,
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


def test_lider_aprova_solicitacao_com_sucesso():
    join_request = JoinRequestFactory()
    team = join_request.team
    student = join_request.student

    create_open_formation(team.edition)
    leader = get_leader(team)

    response = respond_join_request(
        actor=leader,
        join_request_id=join_request.id,
        status=RequestStatus.APPROVED,
    )

    join_request.refresh_from_db()

    assert response.id == join_request.id
    assert join_request.status == RequestStatus.APPROVED
    assert join_request.responded_at is not None

    assert TeamMember.objects.filter(
        team=team,
        student=student,
        role=MemberRole.MEMBER,
        active=True,
    ).exists()

    notification = Notification.objects.get(user=student.user)

    assert notification.type == NotificationType.TEAM
    assert notification.title == "Solicitação aprovada"
    assert notification.message == (
        f"Sua solicitação para participar da equipe {team.name} foi aprovada."
    )
    assert notification.link == f"/equipes/{team.id}"
    assert notification.read_at is None


def test_lider_rejeita_solicitacao_com_sucesso():
    join_request = JoinRequestFactory()
    team = join_request.team
    student = join_request.student

    create_open_formation(team.edition)
    leader = get_leader(team)

    response = respond_join_request(
        actor=leader,
        join_request_id=join_request.id,
        status=RequestStatus.REJECTED,
    )

    join_request.refresh_from_db()

    assert response.id == join_request.id
    assert join_request.status == RequestStatus.REJECTED
    assert join_request.responded_at is not None

    assert not TeamMember.objects.filter(
        team=team,
        student=student,
        active=True,
    ).exists()

    notification = Notification.objects.get(user=student.user)

    assert notification.type == NotificationType.TEAM
    assert notification.title == "Solicitação recusada"
    assert notification.message == (
        f"Sua solicitação para participar da equipe {team.name} foi recusada."
    )
    assert notification.link == f"/equipes/{team.id}"


def test_usuario_que_nao_e_aluno_nao_pode_responder_solicitacao():
    join_request = JoinRequestFactory()
    team = join_request.team
    create_open_formation(team.edition)

    user = UserFactory(role=UserRole.TEACHER)

    with pytest.raises(
        JoinRequestResponseRejected,
        match="Somente alunos podem responder solicitações de entrada.",
    ):
        respond_join_request(
            actor=user,
            join_request_id=join_request.id,
            status=RequestStatus.APPROVED,
        )

    join_request.refresh_from_db()
    assert join_request.status == RequestStatus.PENDING
    assert Notification.objects.count() == 0


def test_aluno_sem_perfil_nao_pode_responder_solicitacao():
    join_request = JoinRequestFactory()
    team = join_request.team
    create_open_formation(team.edition)

    user = UserFactory(role=UserRole.STUDENT)

    with pytest.raises(
        JoinRequestResponseRejected,
        match="O perfil de aluno não foi encontrado.",
    ):
        respond_join_request(
            actor=user,
            join_request_id=join_request.id,
            status=RequestStatus.APPROVED,
        )

    join_request.refresh_from_db()
    assert join_request.status == RequestStatus.PENDING
    assert Notification.objects.count() == 0


def test_integrante_que_nao_e_lider_nao_pode_responder_solicitacao():
    join_request = JoinRequestFactory()
    team = join_request.team
    create_open_formation(team.edition)

    member = TeamMemberFactory(team=team)
    user = member.student.user

    with pytest.raises(
        JoinRequestResponseRejected,
        match="Somente o líder ativo da equipe pode responder solicitações.",
    ):
        respond_join_request(
            actor=user,
            join_request_id=join_request.id,
            status=RequestStatus.APPROVED,
        )

    join_request.refresh_from_db()
    assert join_request.status == RequestStatus.PENDING
    assert Notification.objects.count() == 0


def test_ex_lider_nao_pode_responder_solicitacao():
    join_request = JoinRequestFactory()
    team = join_request.team
    create_open_formation(team.edition)

    leader_membership = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    )
    leader = leader_membership.student.user

    leader_membership.active = False
    leader_membership.left_at = timezone.now()
    leader_membership.save(update_fields=["active", "left_at"])

    with pytest.raises(
        JoinRequestResponseRejected,
        match="Somente o líder ativo da equipe pode responder solicitações.",
    ):
        respond_join_request(
            actor=leader,
            join_request_id=join_request.id,
            status=RequestStatus.APPROVED,
        )

    join_request.refresh_from_db()
    assert join_request.status == RequestStatus.PENDING
    assert Notification.objects.count() == 0


def test_solicitacao_inexistente_nao_pode_ser_respondida():
    team = TeamFactory()
    create_open_formation(team.edition)
    leader = get_leader(team)

    with pytest.raises(
        JoinRequestResponseRejected,
        match="Solicitação não encontrada.",
    ):
        respond_join_request(
            actor=leader,
            join_request_id=999999,
            status=RequestStatus.APPROVED,
        )

    assert JoinRequest.objects.count() == 0
    assert Notification.objects.count() == 0


def test_solicitacao_ja_respondida_nao_pode_ser_respondida_novamente():
    join_request = JoinRequestFactory(status=RequestStatus.REJECTED)
    create_open_formation(join_request.team.edition)
    leader = get_leader(join_request.team)

    with pytest.raises(
        JoinRequestResponseRejected,
        match="Esta solicitação não está mais pendente.",
    ):
        respond_join_request(
            actor=leader,
            join_request_id=join_request.id,
            status=RequestStatus.APPROVED,
        )

    join_request.refresh_from_db()
    assert join_request.status == RequestStatus.REJECTED

    assert not TeamMember.objects.filter(
        team=join_request.team,
        student=join_request.student,
        active=True,
    ).exists()

    assert Notification.objects.count() == 0


def test_lider_nao_pode_aprovar_solicitacao_com_equipe_cheia():
    join_request = JoinRequestFactory()
    team = join_request.team
    create_open_formation(team.edition)
    leader = get_leader(team)

    while TeamMember.objects.filter(team=team, active=True).count() < (
        team.edition.max_members
    ):
        TeamMemberFactory(team=team)

    with pytest.raises(
        JoinRequestResponseRejected,
        match="A equipe já atingiu o limite máximo de integrantes.",
    ):
        respond_join_request(
            actor=leader,
            join_request_id=join_request.id,
            status=RequestStatus.APPROVED,
        )

    join_request.refresh_from_db()
    assert join_request.status == RequestStatus.PENDING


def test_lider_nao_pode_aprovar_aluno_que_ja_esta_em_outra_equipe():
    join_request = JoinRequestFactory()
    team = join_request.team
    create_open_formation(team.edition)
    leader = get_leader(team)

    other_team = TeamFactory(edition=team.edition)
    TeamMemberFactory(
        team=other_team,
        student=join_request.student,
    )

    with pytest.raises(
        JoinRequestResponseRejected,
        match="O estudante já participa de uma equipe ativa nesta edição.",
    ):
        respond_join_request(
            actor=leader,
            join_request_id=join_request.id,
            status=RequestStatus.APPROVED,
        )

    join_request.refresh_from_db()
    assert join_request.status == RequestStatus.PENDING


def test_lider_nao_pode_aprovar_solicitacao_com_formacao_encerrada():
    join_request = JoinRequestFactory()
    leader = get_leader(join_request.team)

    now = timezone.now()
    StageFactory(
        edition=join_request.team.edition,
        formation=True,
        starts_at=now - timedelta(days=10),
        ends_at=now - timedelta(days=1),
    )

    with pytest.raises(
        JoinRequestResponseRejected,
        match="Não existe prazo de formação aberto para esta equipe.",
    ):
        respond_join_request(
            actor=leader,
            join_request_id=join_request.id,
            status=RequestStatus.APPROVED,
        )

    join_request.refresh_from_db()
    assert join_request.status == RequestStatus.PENDING


def test_lider_nao_pode_responder_solicitacao_de_equipe_desclassificada():
    join_request = JoinRequestFactory()
    team = join_request.team
    create_open_formation(team.edition)
    leader = get_leader(team)

    admin = UserFactory(role=UserRole.ADMIN)

    team.status = TeamStatus.DISQUALIFIED
    team.disqualification_reason = "Descumprimento das regras."
    team.disqualified_at = timezone.now()
    team.disqualified_by = admin
    team.save(
        update_fields=[
            "status",
            "disqualification_reason",
            "disqualified_at",
            "disqualified_by",
        ]
    )

    with pytest.raises(
        JoinRequestResponseRejected,
        match="Não é possível responder solicitações de equipes desclassificadas.",
    ):
        respond_join_request(
            actor=leader,
            join_request_id=join_request.id,
            status=RequestStatus.APPROVED,
        )

    join_request.refresh_from_db()
    assert join_request.status == RequestStatus.PENDING


def test_lider_nao_pode_aprovar_solicitacao_de_aluno_inativo():
    join_request = JoinRequestFactory()
    create_open_formation(join_request.team.edition)
    leader = get_leader(join_request.team)

    join_request.student.user.is_active = False
    join_request.student.user.save(update_fields=["is_active"])

    with pytest.raises(
        JoinRequestResponseRejected,
        match="O estudante não possui cadastro ativo e confirmado.",
    ):
        respond_join_request(
            actor=leader,
            join_request_id=join_request.id,
            status=RequestStatus.APPROVED,
        )

    join_request.refresh_from_db()
    assert join_request.status == RequestStatus.PENDING
    assert Notification.objects.count() == 0


def test_lider_nao_pode_aprovar_solicitacao_de_aluno_com_email_nao_confirmado():
    join_request = JoinRequestFactory()
    create_open_formation(join_request.team.edition)
    leader = get_leader(join_request.team)

    join_request.student.user.email_confirmed = False
    join_request.student.user.save(update_fields=["email_confirmed"])

    with pytest.raises(
        JoinRequestResponseRejected,
        match="O estudante não possui cadastro ativo e confirmado.",
    ):
        respond_join_request(
            actor=leader,
            join_request_id=join_request.id,
            status=RequestStatus.APPROVED,
        )

    join_request.refresh_from_db()
    assert join_request.status == RequestStatus.PENDING
    assert Notification.objects.count() == 0


def test_aprovacao_cancela_outras_solicitacoes_pendentes_na_mesma_edicao():
    join_request = JoinRequestFactory()
    team = join_request.team
    create_open_formation(team.edition)
    leader = get_leader(team)

    other_team = TeamFactory(edition=team.edition)
    other_request = JoinRequestFactory(
        team=other_team,
        student=join_request.student,
        status=RequestStatus.PENDING,
    )

    respond_join_request(
        actor=leader,
        join_request_id=join_request.id,
        status=RequestStatus.APPROVED,
    )

    join_request.refresh_from_db()
    other_request.refresh_from_db()

    assert join_request.status == RequestStatus.APPROVED
    assert other_request.status == RequestStatus.CANCELLED


def test_aprovacao_cancela_convites_pendentes_na_mesma_edicao():
    join_request = JoinRequestFactory()
    team = join_request.team
    create_open_formation(team.edition)
    leader = get_leader(team)

    other_team = TeamFactory(edition=team.edition)
    invitation = InvitationFactory(
        team=other_team,
        student=join_request.student,
        status=InvitationStatus.PENDING,
    )

    respond_join_request(
        actor=leader,
        join_request_id=join_request.id,
        status=RequestStatus.APPROVED,
    )

    invitation.refresh_from_db()
    assert invitation.status == InvitationStatus.CANCELLED


def test_rejeicao_mantem_outros_convites_e_solicitacoes_pendentes():
    join_request = JoinRequestFactory()
    team = join_request.team
    create_open_formation(team.edition)
    leader = get_leader(team)

    other_team = TeamFactory(edition=team.edition)

    other_request = JoinRequestFactory(
        team=other_team,
        student=join_request.student,
        status=RequestStatus.PENDING,
    )

    invitation = InvitationFactory(
        team=other_team,
        student=join_request.student,
        status=InvitationStatus.PENDING,
    )

    respond_join_request(
        actor=leader,
        join_request_id=join_request.id,
        status=RequestStatus.REJECTED,
    )

    join_request.refresh_from_db()
    other_request.refresh_from_db()
    invitation.refresh_from_db()

    assert join_request.status == RequestStatus.REJECTED
    assert other_request.status == RequestStatus.PENDING
    assert invitation.status == InvitationStatus.PENDING


def test_rejeicao_nao_adiciona_aluno_a_equipe():
    join_request = JoinRequestFactory()
    create_open_formation(join_request.team.edition)
    leader = get_leader(join_request.team)

    respond_join_request(
        actor=leader,
        join_request_id=join_request.id,
        status=RequestStatus.REJECTED,
    )

    assert not TeamMember.objects.filter(
        team=join_request.team,
        student=join_request.student,
        active=True,
    ).exists()


def test_lider_de_outra_equipe_nao_pode_responder_solicitacao():
    join_request = JoinRequestFactory()
    create_open_formation(join_request.team.edition)

    other_team = TeamFactory(edition=join_request.team.edition)
    other_leader = get_leader(other_team)

    with pytest.raises(
        JoinRequestResponseRejected,
        match="Somente o líder ativo da equipe pode responder solicitações.",
    ):
        respond_join_request(
            actor=other_leader,
            join_request_id=join_request.id,
            status=RequestStatus.APPROVED,
        )

    join_request.refresh_from_db()
    assert join_request.status == RequestStatus.PENDING
    assert Notification.objects.count() == 0


def test_erro_ao_criar_integrante_impede_aprovacao():
    join_request = JoinRequestFactory()
    create_open_formation(join_request.team.edition)
    leader = get_leader(join_request.team)

    with patch(
        "apps.teams.use_cases.respond_join_request.TeamMember.objects.create",
        side_effect=IntegrityError("Erro de integridade"),
    ):
        with pytest.raises(
            JoinRequestResponseRejected,
            match="Não foi possível aprovar a solicitação.",
        ):
            respond_join_request(
                actor=leader,
                join_request_id=join_request.id,
                status=RequestStatus.APPROVED,
            )

    join_request.refresh_from_db()
    assert join_request.status == RequestStatus.PENDING
    assert Notification.objects.count() == 0
