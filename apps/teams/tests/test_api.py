from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.factories import (
    StudentFactory,
    TeacherCourseFactory,
    TeacherFactory,
    UserFactory,
)
from apps.editions.enums import EditionStatus
from apps.editions.factories import (
    ChallengeFactory,
    EditionFactory,
    StageFactory,
)
from apps.projects.models import Project
from apps.teams.enums import InvitationStatus
from apps.teams.factories import (
    InvitationFactory,
    TeamFactory,
    TeamMemberFactory,
)
from apps.teams.models import Team

pytestmark = pytest.mark.django_db

TEAMS_URL = "/api/teams"


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_aluno_cria_equipe_pela_api():
    student = StudentFactory()
    edition = EditionFactory(status=EditionStatus.PUBLISHED)

    now = timezone.now()
    StageFactory(
        edition=edition,
        formation=True,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=7),
    )

    client = authenticated_client(student.user)

    response = client.post(
        TEAMS_URL,
        {"name": "Equipe API"},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["name"] == "Equipe API"
    assert response.data["code"]

    team = Team.objects.get(name="Equipe API")
    assert team.edition == edition


def test_aluno_integrante_consulta_equipe():
    student = StudentFactory()
    team = TeamFactory(leader=False)
    TeamMemberFactory(team=team, student=student)

    client = authenticated_client(student.user)

    response = client.get(f"{TEAMS_URL}/{team.id}")

    assert response.status_code == 200
    assert response.data["id"] == team.id


def test_professor_com_vinculo_ativo_consulta_equipe():
    team = TeamFactory()
    teacher = TeacherFactory()

    challenge = ChallengeFactory(
        edition=team.edition,
    )
    Project.objects.create(
        team=team,
        edition=team.edition,
        challenge=challenge,
    )

    TeacherCourseFactory(
        teacher=teacher,
        course=challenge.course,
        active=True,
    )

    client = authenticated_client(teacher.user)

    response = client.get(f"{TEAMS_URL}/{team.id}")

    assert response.status_code == 200
    assert response.data["id"] == team.id


def test_admin_consulta_qualquer_equipe():
    admin = UserFactory(role=UserRole.ADMIN)
    team = TeamFactory()

    client = authenticated_client(admin)

    response = client.get(f"{TEAMS_URL}/{team.id}")

    assert response.status_code == 200
    assert response.data["id"] == team.id


def test_aluno_que_nao_e_integrante_recebe_404():
    student = StudentFactory()
    team = TeamFactory()

    client = authenticated_client(student.user)

    response = client.get(f"{TEAMS_URL}/{team.id}")

    assert response.status_code == 404


def test_professor_sem_vinculo_ativo_recebe_404():
    team = TeamFactory()
    teacher = TeacherFactory()

    challenge = ChallengeFactory(edition=team.edition)
    Project.objects.create(
        team=team,
        edition=team.edition,
        challenge=challenge,
    )

    TeacherCourseFactory(
        teacher=teacher,
        course=challenge.course,
        active=False,
    )

    client = authenticated_client(teacher.user)

    response = client.get(f"{TEAMS_URL}/{team.id}")

    assert response.status_code == 404


def test_integrante_inativo_recebe_404():
    student = StudentFactory()
    team = TeamFactory(leader=False)
    membership = TeamMemberFactory(team=team, student=student)

    membership.active = False
    membership.left_at = timezone.now()
    membership.save()

    client = authenticated_client(student.user)

    response = client.get(f"{TEAMS_URL}/{team.id}")

    assert response.status_code == 404


def test_equipe_inexistente_retorna_404():
    admin = UserFactory(role=UserRole.ADMIN)
    client = authenticated_client(admin)

    response = client.get(f"{TEAMS_URL}/999999")

    assert response.status_code == 404


def test_professor_nao_pode_criar_equipe():
    teacher = TeacherFactory()
    client = authenticated_client(teacher.user)

    response = client.post(
        TEAMS_URL,
        {"name": "Equipe Indevida"},
        format="json",
    )

    assert response.status_code == 403


def test_criacao_sem_nome_retorna_400():
    student = StudentFactory()
    client = authenticated_client(student.user)

    response = client.post(
        TEAMS_URL,
        {},
        format="json",
    )

    assert response.status_code == 400


MY_INVITATIONS_URL = "/api/me/invitations"


def test_aluno_lista_seus_convites_recebidos():
    student = StudentFactory()
    invitation = InvitationFactory(student=student)

    client = authenticated_client(student.user)

    response = client.get(MY_INVITATIONS_URL)

    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["id"] == invitation.id


def test_aluno_filtra_convites_por_status():
    from apps.teams.enums import InvitationStatus

    student = StudentFactory()
    pending = InvitationFactory(
        student=student,
        status=InvitationStatus.PENDING,
    )
    InvitationFactory(
        student=student,
        status=InvitationStatus.DECLINED,
    )

    client = authenticated_client(student.user)

    response = client.get(
        f"{MY_INVITATIONS_URL}?status=PENDING",
    )

    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["id"] == pending.id


def test_aluno_nao_visualiza_convites_de_outros_alunos():
    student = StudentFactory()
    other_student = StudentFactory()

    own_invitation = InvitationFactory(student=student)
    InvitationFactory(student=other_student)

    client = authenticated_client(student.user)

    response = client.get(MY_INVITATIONS_URL)

    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["id"] == own_invitation.id


def test_usuario_que_nao_e_aluno_nao_lista_convites():
    teacher = TeacherFactory()
    client = authenticated_client(teacher.user)

    response = client.get(MY_INVITATIONS_URL)

    assert response.status_code == 403


def test_lider_lista_convites_enviados_pela_equipe():
    team = TeamFactory()
    leader = team.members.get(role="LEADER", active=True).student
    invitation = InvitationFactory(team=team)

    client = authenticated_client(leader.user)

    response = client.get(f"{TEAMS_URL}/{team.id}/invitations")

    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["id"] == invitation.id


def test_lider_filtra_convites_por_status():
    from apps.teams.enums import InvitationStatus

    team = TeamFactory()
    leader = team.members.get(role="LEADER", active=True).student

    pending = InvitationFactory(
        team=team,
        status=InvitationStatus.PENDING,
    )
    InvitationFactory(
        team=team,
        status=InvitationStatus.DECLINED,
    )

    client = authenticated_client(leader.user)

    response = client.get(
        f"{TEAMS_URL}/{team.id}/invitations?status=PENDING",
    )

    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["id"] == pending.id


def test_aluno_que_nao_e_lider_nao_lista_convites():
    team = TeamFactory()
    student = StudentFactory()

    client = authenticated_client(student.user)

    response = client.get(f"{TEAMS_URL}/{team.id}/invitations")

    assert response.status_code == 404


def test_lider_nao_lista_convites_de_outra_equipe():
    team = TeamFactory()
    other_team = TeamFactory()

    leader = team.members.get(role="LEADER", active=True).student
    InvitationFactory(team=other_team)

    client = authenticated_client(leader.user)

    response = client.get(
        f"{TEAMS_URL}/{other_team.id}/invitations",
    )

    assert response.status_code == 404


INVITATIONS_URL = "/api/invitations"


def create_open_formation(edition):
    now = timezone.now()
    StageFactory(
        edition=edition,
        formation=True,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=7),
    )


def test_aluno_aceita_convite_pela_api():
    team = TeamFactory()
    create_open_formation(team.edition)
    student = StudentFactory()
    invitation = InvitationFactory(team=team, student=student)

    client = authenticated_client(student.user)
    response = client.post(
        f"{INVITATIONS_URL}/{invitation.id}/respond",
        {"accept": True},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["status"] == InvitationStatus.ACCEPTED

    invitation.refresh_from_db()
    assert invitation.responded_at is not None
    assert team.members.filter(student=student, active=True).exists()


def test_aluno_recusa_convite_pela_api():
    team = TeamFactory()
    create_open_formation(team.edition)
    student = StudentFactory()
    invitation = InvitationFactory(team=team, student=student)

    client = authenticated_client(student.user)
    response = client.post(
        f"{INVITATIONS_URL}/{invitation.id}/respond",
        {"accept": False},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["status"] == InvitationStatus.DECLINED

    invitation.refresh_from_db()
    assert invitation.responded_at is not None


def test_aluno_nao_responde_convite_de_outro_aluno_pela_api():
    team = TeamFactory()
    student = StudentFactory()
    another_student = StudentFactory()
    invitation = InvitationFactory(team=team, student=student)

    client = authenticated_client(another_student.user)
    response = client.post(
        f"{INVITATIONS_URL}/{invitation.id}/respond",
        {"accept": True},
        format="json",
    )

    assert response.status_code == 404


def test_convite_inexistente_retorna_404_pela_api():
    student = StudentFactory()
    client = authenticated_client(student.user)

    response = client.post(
        f"{INVITATIONS_URL}/999999/respond",
        {"accept": True},
        format="json",
    )

    assert response.status_code == 404


def test_convite_ja_respondido_retorna_409_pela_api():
    team = TeamFactory()
    student = StudentFactory()
    invitation = InvitationFactory(
        team=team,
        student=student,
        status=InvitationStatus.DECLINED,
    )

    client = authenticated_client(student.user)
    response = client.post(
        f"{INVITATIONS_URL}/{invitation.id}/respond",
        {"accept": True},
        format="json",
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "invitation_not_pending"


def test_usuario_que_nao_e_aluno_nao_responde_convite_pela_api():
    teacher = TeacherFactory()
    client = authenticated_client(teacher.user)

    response = client.post(
        f"{INVITATIONS_URL}/999999/respond",
        {"accept": True},
        format="json",
    )

    assert response.status_code == 403


def test_resposta_sem_campo_accept_retorna_400():
    student = StudentFactory()
    client = authenticated_client(student.user)

    response = client.post(
        f"{INVITATIONS_URL}/999999/respond",
        {},
        format="json",
    )

    assert response.status_code == 400
