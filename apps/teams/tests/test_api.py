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
from apps.teams.factories import TeamFactory, TeamMemberFactory
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