
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.factories import StudentFactory, UserFactory
from apps.editions.factories import StageFactory
from apps.teams.enums import InvitationStatus, MemberRole
from apps.teams.factories import (
    InvitationFactory,
    TeamFactory,
    TeamMemberFactory,
)
from apps.teams.models import Invitation
from apps.teams.use_cases.invite_member import (
    InvitationRejected,
    invite_member,
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


def test_lider_envia_convite_com_sucesso():
    team = TeamFactory()
    create_open_formation(team.edition)
    leader = get_leader(team)
    invited_student = StudentFactory()

    invitation = invite_member(
        actor=leader,
        team_id=team.id,
        student_id=invited_student.pk,
    )

    assert isinstance(invitation, Invitation)
    assert invitation.team == team
    assert invitation.student == invited_student
    assert invitation.status == InvitationStatus.PENDING
    assert Invitation.objects.count() == 1


def test_usuario_que_nao_e_aluno_nao_pode_enviar_convite():
    team = TeamFactory()
    create_open_formation(team.edition)
    user = UserFactory(role=UserRole.TEACHER)
    invited_student = StudentFactory()

    with pytest.raises(
        InvitationRejected,
        match="Somente alunos podem enviar convites.",
    ):
        invite_member(
            actor=user,
            team_id=team.id,
            student_id=invited_student.pk,
        )

    assert Invitation.objects.count() == 0


def test_aluno_sem_perfil_nao_pode_enviar_convite():
    team = TeamFactory()
    create_open_formation(team.edition)
    user = UserFactory(role=UserRole.STUDENT)
    invited_student = StudentFactory()

    with pytest.raises(
        InvitationRejected,
        match="O perfil de aluno não foi encontrado.",
    ):
        invite_member(
            actor=user,
            team_id=team.id,
            student_id=invited_student.pk,
        )

    assert Invitation.objects.count() == 0


def test_equipe_inexistente_nao_pode_receber_convite():
    leader = StudentFactory()
    invited_student = StudentFactory()

    with pytest.raises(
        InvitationRejected,
        match="Equipe não encontrada.",
    ):
        invite_member(
            actor=leader.user,
            team_id=999999,
            student_id=invited_student.pk,
        )

    assert Invitation.objects.count() == 0


def test_integrante_que_nao_e_lider_nao_pode_convidar():
    team = TeamFactory()
    create_open_formation(team.edition)
    member = StudentFactory()
    TeamMemberFactory(team=team, student=member)
    invited_student = StudentFactory()

    with pytest.raises(
        InvitationRejected,
        match="Somente o líder ativo da equipe pode enviar convites.",
    ):
        invite_member(
            actor=member.user,
            team_id=team.id,
            student_id=invited_student.pk,
        )

    assert Invitation.objects.count() == 0


def test_ex_lider_nao_pode_enviar_convite():
    team = TeamFactory()
    create_open_formation(team.edition)
    leader_membership = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    )
    leader = leader_membership.student.user

    leader_membership.active = False
    leader_membership.left_at = timezone.now()
    leader_membership.save(update_fields=["active", "left_at"])

    invited_student = StudentFactory()

    with pytest.raises(
        InvitationRejected,
        match="Somente o líder ativo da equipe pode enviar convites.",
    ):
        invite_member(
            actor=leader,
            team_id=team.id,
            student_id=invited_student.pk,
        )

    assert Invitation.objects.count() == 0


def test_nao_pode_enviar_convite_sem_formacao_aberta():
    team = TeamFactory()
    leader = get_leader(team)
    invited_student = StudentFactory()

    with pytest.raises(
        InvitationRejected,
        match="Não existe prazo de formação aberto para esta equipe.",
    ):
        invite_member(
            actor=leader,
            team_id=team.id,
            student_id=invited_student.pk,
        )

    assert Invitation.objects.count() == 0


def test_equipe_desclassificada_nao_pode_enviar_convite():
    team = TeamFactory(disqualified=True)
    create_open_formation(team.edition)
    leader = get_leader(team)
    invited_student = StudentFactory()

    with pytest.raises(
        InvitationRejected,
        match="Equipes desclassificadas não podem enviar convites.",
    ):
        invite_member(
            actor=leader,
            team_id=team.id,
            student_id=invited_student.pk,
        )

    assert Invitation.objects.count() == 0


def test_equipe_no_limite_maximo_nao_pode_receber_convite():
    team = TeamFactory()
    create_open_formation(team.edition)
    leader = get_leader(team)

    for _ in range(team.edition.max_members - 1):
        TeamMemberFactory(team=team)

    invited_student = StudentFactory()

    with pytest.raises(
        InvitationRejected,
        match="A equipe já atingiu o limite máximo de integrantes.",
    ):
        invite_member(
            actor=leader,
            team_id=team.id,
            student_id=invited_student.pk,
        )

    assert Invitation.objects.count() == 0


def test_estudante_inexistente_nao_pode_receber_convite():
    team = TeamFactory()
    create_open_formation(team.edition)
    leader = get_leader(team)

    with pytest.raises(
        InvitationRejected,
        match="Estudante não encontrado.",
    ):
        invite_member(
            actor=leader,
            team_id=team.id,
            student_id=999999,
        )

    assert Invitation.objects.count() == 0


def test_estudante_inativo_nao_pode_receber_convite():
    team = TeamFactory()
    create_open_formation(team.edition)
    leader = get_leader(team)
    invited_student = StudentFactory(
        user__is_active=False,
    )

    with pytest.raises(
        InvitationRejected,
        match="O estudante não possui cadastro ativo e confirmado.",
    ):
        invite_member(
            actor=leader,
            team_id=team.id,
            student_id=invited_student.pk,
        )

    assert Invitation.objects.count() == 0


def test_estudante_com_email_nao_confirmado_nao_pode_receber_convite():
    team = TeamFactory()
    create_open_formation(team.edition)
    leader = get_leader(team)
    invited_student = StudentFactory(
        user__email_confirmed=False,
    )

    with pytest.raises(
        InvitationRejected,
        match="O estudante não possui cadastro ativo e confirmado.",
    ):
        invite_member(
            actor=leader,
            team_id=team.id,
            student_id=invited_student.pk,
        )

    assert Invitation.objects.count() == 0


def test_estudante_que_ja_participa_de_equipe_na_edicao_nao_pode_ser_convidado():
    team = TeamFactory()
    create_open_formation(team.edition)
    leader = get_leader(team)
    invited_student = StudentFactory()

    another_team = TeamFactory(edition=team.edition)
    TeamMemberFactory(
        team=another_team,
        student=invited_student,
    )

    with pytest.raises(
        InvitationRejected,
        match="O estudante já participa de uma equipe ativa nesta edição.",
    ):
        invite_member(
            actor=leader,
            team_id=team.id,
            student_id=invited_student.pk,
        )

    assert Invitation.objects.count() == 0


def test_nao_pode_enviar_convite_duplicado():
    team = TeamFactory()
    create_open_formation(team.edition)
    leader = get_leader(team)
    invited_student = StudentFactory()

    InvitationFactory(
        team=team,
        student=invited_student,
        status=InvitationStatus.PENDING,
    )

    with pytest.raises(
        InvitationRejected,
        match="Já existe um convite pendente para este estudante nesta equipe.",
    ):
        invite_member(
            actor=leader,
            team_id=team.id,
            student_id=invited_student.pk,
        )

    assert Invitation.objects.filter(
        team=team,
        student=invited_student,
        status=InvitationStatus.PENDING,
    ).count() == 1


def test_reverte_operacao_se_ocorrer_erro_ao_criar_convite():
    team = TeamFactory()
    create_open_formation(team.edition)
    leader = get_leader(team)
    invited_student = StudentFactory()

    with patch(
        "apps.teams.use_cases.invite_member.Invitation.objects.create",
        side_effect=IntegrityError("Erro simulado"),
    ):
        with pytest.raises(
            InvitationRejected,
            match="Não foi possível enviar o convite.",
        ):
            invite_member(
                actor=leader,
                team_id=team.id,
                student_id=invited_student.pk,
            )

    assert Invitation.objects.count() == 0
