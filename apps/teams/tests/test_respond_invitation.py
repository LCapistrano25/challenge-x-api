from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.factories import StudentFactory
from apps.editions.factories import StageFactory
from apps.notifications.models import Notification, NotificationType
from apps.teams.enums import (
    InvitationStatus,
    MemberRole,
    RequestStatus,
)
from apps.teams.factories import (
    InvitationFactory,
    JoinRequestFactory,
    TeamFactory,
    TeamMemberFactory,
)
from apps.teams.models import TeamMember
from apps.teams.use_cases.respond_invitation import (
    InvitationResponseRejected,
    respond_invitation,
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


def test_estudante_aceita_convite_com_sucesso():
    team = TeamFactory()
    create_open_formation(team.edition)
    invited_student = StudentFactory()

    invitation = InvitationFactory(
        team=team,
        student=invited_student,
        status=InvitationStatus.PENDING,
    )

    response = respond_invitation(
        actor=invited_student.user,
        invitation_id=invitation.pk,
        accept=True,
    )

    invitation.refresh_from_db()

    assert response.pk == invitation.pk
    assert invitation.status == InvitationStatus.ACCEPTED
    assert invitation.responded_at is not None

    assert TeamMember.objects.filter(
        team=team,
        student=invited_student,
        role=MemberRole.MEMBER,
        active=True,
    ).exists()


def test_estudante_recusa_convite_com_sucesso():
    team = TeamFactory()
    create_open_formation(team.edition)
    invited_student = StudentFactory()

    invitation = InvitationFactory(
        team=team,
        student=invited_student,
        status=InvitationStatus.PENDING,
    )

    response = respond_invitation(
        actor=invited_student.user,
        invitation_id=invitation.pk,
        accept=False,
    )

    invitation.refresh_from_db()

    assert response.pk == invitation.pk
    assert invitation.status == InvitationStatus.DECLINED
    assert invitation.responded_at is not None

    assert not TeamMember.objects.filter(
        team=team,
        student=invited_student,
        active=True,
    ).exists()


def test_usuario_que_nao_e_aluno_nao_pode_responder_convite():
    from apps.accounts.enums import UserRole
    from apps.accounts.factories import UserFactory

    team = TeamFactory()
    create_open_formation(team.edition)
    invited_student = StudentFactory()
    invitation = InvitationFactory(
        team=team,
        student=invited_student,
    )
    teacher = UserFactory(role=UserRole.TEACHER)

    with pytest.raises(
        InvitationResponseRejected,
        match="Somente alunos podem responder convites.",
    ):
        respond_invitation(
            actor=teacher,
            invitation_id=invitation.pk,
            accept=True,
        )


def test_aluno_sem_perfil_nao_pode_responder_convite():
    from apps.accounts.enums import UserRole
    from apps.accounts.factories import UserFactory

    team = TeamFactory()
    create_open_formation(team.edition)
    invited_student = StudentFactory()
    invitation = InvitationFactory(
        team=team,
        student=invited_student,
    )
    user = UserFactory(role=UserRole.STUDENT)

    with pytest.raises(
        InvitationResponseRejected,
        match="O perfil de aluno não foi encontrado.",
    ):
        respond_invitation(
            actor=user,
            invitation_id=invitation.pk,
            accept=True,
        )


def test_aluno_nao_pode_responder_convite_de_outro_estudante():
    team = TeamFactory()
    create_open_formation(team.edition)
    invited_student = StudentFactory()
    another_student = StudentFactory()
    invitation = InvitationFactory(
        team=team,
        student=invited_student,
    )

    with pytest.raises(
        InvitationResponseRejected,
        match="Este convite não pertence ao estudante autenticado.",
    ):
        respond_invitation(
            actor=another_student.user,
            invitation_id=invitation.pk,
            accept=True,
        )


def test_aluno_inativo_nao_pode_responder_convite():
    team = TeamFactory()
    create_open_formation(team.edition)
    invited_student = StudentFactory(user__is_active=False)
    invitation = InvitationFactory(
        team=team,
        student=invited_student,
    )

    with pytest.raises(
        InvitationResponseRejected,
        match="O estudante não possui cadastro ativo e confirmado.",
    ):
        respond_invitation(
            actor=invited_student.user,
            invitation_id=invitation.pk,
            accept=True,
        )


def test_aluno_com_email_nao_confirmado_nao_pode_responder_convite():
    team = TeamFactory()
    create_open_formation(team.edition)
    invited_student = StudentFactory(user__email_confirmed=False)
    invitation = InvitationFactory(
        team=team,
        student=invited_student,
    )

    with pytest.raises(
        InvitationResponseRejected,
        match="O estudante não possui cadastro ativo e confirmado.",
    ):
        respond_invitation(
            actor=invited_student.user,
            invitation_id=invitation.pk,
            accept=True,
        )


def test_convite_inexistente_nao_pode_ser_respondido():
    student = StudentFactory()

    with pytest.raises(
        InvitationResponseRejected,
        match="Convite não encontrado.",
    ):
        respond_invitation(
            actor=student.user,
            invitation_id=999999,
            accept=True,
        )


def test_convite_ja_respondido_nao_pode_ser_respondido_novamente():
    team = TeamFactory()
    create_open_formation(team.edition)
    student = StudentFactory()
    invitation = InvitationFactory(
        team=team,
        student=student,
        status=InvitationStatus.DECLINED,
    )

    with pytest.raises(
        InvitationResponseRejected,
        match="Este convite não está mais pendente.",
    ):
        respond_invitation(
            actor=student.user,
            invitation_id=invitation.pk,
            accept=True,
        )


def test_convite_de_equipe_desclassificada_nao_pode_ser_respondido():
    team = TeamFactory(disqualified=True)
    create_open_formation(team.edition)
    student = StudentFactory()
    invitation = InvitationFactory(
        team=team,
        student=student,
    )

    with pytest.raises(
        InvitationResponseRejected,
        match="Não é possível responder a convites de equipes desclassificadas.",
    ):
        respond_invitation(
            actor=student.user,
            invitation_id=invitation.pk,
            accept=True,
        )


def test_nao_pode_responder_convite_sem_formacao_aberta():
    team = TeamFactory()
    student = StudentFactory()
    invitation = InvitationFactory(
        team=team,
        student=student,
    )

    with pytest.raises(
        InvitationResponseRejected,
        match="Não existe prazo de formação aberto para esta equipe.",
    ):
        respond_invitation(
            actor=student.user,
            invitation_id=invitation.pk,
            accept=True,
        )


def test_aluno_que_ja_participa_de_outra_equipe_nao_pode_aceitar_convite():
    team = TeamFactory()
    another_team = TeamFactory(edition=team.edition)
    create_open_formation(team.edition)

    student = StudentFactory()

    TeamMemberFactory(
        team=another_team,
        student=student,
    )

    invitation = InvitationFactory(
        team=team,
        student=student,
    )

    with pytest.raises(
        InvitationResponseRejected,
        match="O estudante já participa de uma equipe ativa nesta edição.",
    ):
        respond_invitation(
            actor=student.user,
            invitation_id=invitation.pk,
            accept=True,
        )

    assert not TeamMember.objects.filter(
        team=team,
        student=student,
        active=True,
    ).exists()


def test_nao_pode_aceitar_convite_quando_equipe_atingiu_limite_maximo():
    team = TeamFactory()
    create_open_formation(team.edition)
    student = StudentFactory()

    for _ in range(team.edition.max_members - 1):
        TeamMemberFactory(team=team)

    invitation = InvitationFactory(
        team=team,
        student=student,
    )

    with pytest.raises(
        InvitationResponseRejected,
        match="A equipe já atingiu o limite máximo de integrantes.",
    ):
        respond_invitation(
            actor=student.user,
            invitation_id=invitation.pk,
            accept=True,
        )

    assert not TeamMember.objects.filter(
        team=team,
        student=student,
        active=True,
    ).exists()


def test_aceitar_convite_cancela_outros_convites_pendentes():
    team = TeamFactory()
    another_team = TeamFactory(edition=team.edition)
    create_open_formation(team.edition)
    student = StudentFactory()

    invitation = InvitationFactory(
        team=team,
        student=student,
        status=InvitationStatus.PENDING,
    )
    another_invitation = InvitationFactory(
        team=another_team,
        student=student,
        status=InvitationStatus.PENDING,
    )

    respond_invitation(
        actor=student.user,
        invitation_id=invitation.pk,
        accept=True,
    )

    invitation.refresh_from_db()
    another_invitation.refresh_from_db()

    assert invitation.status == InvitationStatus.ACCEPTED
    assert another_invitation.status == InvitationStatus.CANCELLED


def test_aceitar_convite_cancela_solicitacoes_pendentes_de_outras_equipes():
    team = TeamFactory()
    another_team = TeamFactory(edition=team.edition)
    create_open_formation(team.edition)
    student = StudentFactory()

    invitation = InvitationFactory(
        team=team,
        student=student,
        status=InvitationStatus.PENDING,
    )
    join_request = JoinRequestFactory(
        team=another_team,
        student=student,
        status=RequestStatus.PENDING,
    )

    respond_invitation(
        actor=student.user,
        invitation_id=invitation.pk,
        accept=True,
    )

    invitation.refresh_from_db()
    join_request.refresh_from_db()

    assert invitation.status == InvitationStatus.ACCEPTED
    assert join_request.status == RequestStatus.CANCELLED


def test_aceitar_convite_notifica_lider():
    team = TeamFactory()
    create_open_formation(team.edition)
    invited_student = StudentFactory()

    leader_membership = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    )

    invitation = InvitationFactory(
        team=team,
        student=invited_student,
        status=InvitationStatus.PENDING,
    )

    respond_invitation(
        actor=invited_student.user,
        invitation_id=invitation.pk,
        accept=True,
    )

    notification = Notification.objects.get(
        user=leader_membership.student.user,
    )

    assert notification.type == NotificationType.TEAM
    assert notification.title == "Convite aceito"
    assert notification.message == (
        f"{invited_student.user.name} aceitou o convite "
        f"para participar da equipe {team.name}."
    )
    assert notification.link == f"/equipes/{team.id}"


def test_recusar_convite_notifica_lider():
    team = TeamFactory()
    create_open_formation(team.edition)
    invited_student = StudentFactory()

    leader_membership = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    )

    invitation = InvitationFactory(
        team=team,
        student=invited_student,
        status=InvitationStatus.PENDING,
    )

    respond_invitation(
        actor=invited_student.user,
        invitation_id=invitation.pk,
        accept=False,
    )

    notification = Notification.objects.get(
        user=leader_membership.student.user,
    )

    assert notification.type == NotificationType.TEAM
    assert notification.title == "Convite recusado"
    assert notification.message == (
        f"{invited_student.user.name} recusou o convite "
        f"para participar da equipe {team.name}."
    )
    assert notification.link == f"/equipes/{team.id}"
