import pytest
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.factories import (
    TeacherCourseFactory,
    TeacherFactory,
    UserFactory,
)
from apps.core.tests.contract import mismatches, schema
from apps.editions.factories import StageFactory
from apps.projects.factories import ProjectFactory
from apps.teams.enums import MemberRole
from apps.teams.factories import (
    MemberNoteFactory,
    TeamFactory,
    TeamMemberFactory,
)

pytestmark = pytest.mark.django_db


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def create_team_with_project():
    team = TeamFactory()
    project = ProjectFactory(team=team)
    leader = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    )
    target = TeamMemberFactory(
        team=team,
        student__course=project.challenge.course,
    )
    stage = StageFactory(edition=team.edition)

    return team, project, leader, target, stage


def test_lider_registra_observacao_pela_api():
    team, project, leader, target, stage = create_team_with_project()
    client = authenticated_client(leader.student.user)

    response = client.post(
        f"/api/teams/{team.pk}/member-notes",
        {
            "member_id": target.pk,
            "stage_id": stage.pk,
            "text": "Participou ativamente das atividades.",
        },
        format="json",
    )

    assert response.status_code == 201, response.data
    assert "id" in response.data
    assert "created_at" in response.data
    assert "text" not in response.data
    assert mismatches(response.json(), schema("MemberNoteCreated")) == []


def test_registro_sem_autenticacao_retorna_401():
    team, project, leader, target, stage = create_team_with_project()
    client = APIClient()

    response = client.post(
        f"/api/teams/{team.pk}/member-notes",
        {
            "member_id": target.pk,
            "stage_id": stage.pk,
            "text": "Observação.",
        },
        format="json",
    )

    assert response.status_code == 401


def test_professor_nao_registra_observacao():
    team, project, leader, target, stage = create_team_with_project()
    teacher = TeacherFactory()
    client = authenticated_client(teacher.user)

    response = client.post(
        f"/api/teams/{team.pk}/member-notes",
        {
            "member_id": target.pk,
            "stage_id": stage.pk,
            "text": "Observação.",
        },
        format="json",
    )

    assert response.status_code == 403


def test_aluno_que_nao_e_lider_nao_registra_observacao():
    team, project, leader, target, stage = create_team_with_project()
    client = authenticated_client(target.student.user)

    response = client.post(
        f"/api/teams/{team.pk}/member-notes",
        {
            "member_id": target.pk,
            "stage_id": stage.pk,
            "text": "Observação.",
        },
        format="json",
    )

    assert response.status_code == 403


def test_registro_sem_stage_id_retorna_400():
    team, project, leader, target, stage = create_team_with_project()
    client = authenticated_client(leader.student.user)

    response = client.post(
        f"/api/teams/{team.pk}/member-notes",
        {
            "member_id": target.pk,
            "text": "Observação.",
        },
        format="json",
    )

    assert response.status_code == 400


def test_professor_com_vinculo_ativo_consulta_observacoes():
    team, project, leader, target, stage = create_team_with_project()
    MemberNoteFactory(
        member=target,
        author=leader.student,
        stage=stage,
        text="Participação abaixo do esperado.",
    )

    teacher = TeacherFactory()
    TeacherCourseFactory(
        teacher=teacher,
        course=project.challenge.course,
        active=True,
    )
    client = authenticated_client(teacher.user)

    response = client.get(
        f"/api/teams/{team.pk}/member-notes",
    )

    assert response.status_code == 200, response.data
    assert len(response.data) == 1
    assert response.data[0]["text"] == "Participação abaixo do esperado."
    assert response.data[0]["member"]["user_id"] == target.student.user_id
    assert response.data[0]["author"]["user_id"] == leader.student.user_id
    assert mismatches(response.json()[0], schema("MemberNote")) == []


def test_professor_sem_vinculo_ativo_nao_consulta_observacoes():
    team, project, leader, target, stage = create_team_with_project()
    teacher = TeacherFactory()
    client = authenticated_client(teacher.user)

    response = client.get(
        f"/api/teams/{team.pk}/member-notes",
    )

    assert response.status_code == 403


def test_administrador_consulta_observacoes():
    team, project, leader, target, stage = create_team_with_project()
    MemberNoteFactory(
        member=target,
        author=leader.student,
        stage=stage,
    )

    admin = UserFactory(role=UserRole.ADMIN)
    client = authenticated_client(admin)

    response = client.get(
        f"/api/teams/{team.pk}/member-notes",
    )

    assert response.status_code == 200, response.data
    assert len(response.data) == 1


def test_aluno_nao_consulta_observacoes():
    team, project, leader, target, stage = create_team_with_project()
    client = authenticated_client(leader.student.user)

    response = client.get(
        f"/api/teams/{team.pk}/member-notes",
    )

    assert response.status_code == 403


def test_consulta_sem_autenticacao_retorna_401():
    team, project, leader, target, stage = create_team_with_project()
    client = APIClient()

    response = client.get(
        f"/api/teams/{team.pk}/member-notes",
    )

    assert response.status_code == 401


def test_professor_com_vinculo_inativo_nao_consulta_observacoes():
    team, project, leader, target, stage = create_team_with_project()
    teacher = TeacherFactory()

    TeacherCourseFactory(
        teacher=teacher,
        course=project.challenge.course,
        active=False,
    )

    client = authenticated_client(teacher.user)

    response = client.get(
        f"/api/teams/{team.pk}/member-notes",
    )

    assert response.status_code == 403


def test_professor_autorizado_sem_observacoes_recebe_lista_vazia():
    team, project, leader, target, stage = create_team_with_project()
    teacher = TeacherFactory()

    TeacherCourseFactory(
        teacher=teacher,
        course=project.challenge.course,
        active=True,
    )

    client = authenticated_client(teacher.user)

    response = client.get(
        f"/api/teams/{team.pk}/member-notes",
    )

    assert response.status_code == 200
    assert response.json() == []


def test_registro_para_equipe_inexistente_retorna_404():
    team, project, leader, target, stage = create_team_with_project()
    client = authenticated_client(leader.student.user)

    response = client.post(
        "/api/teams/999999/member-notes",
        {
            "member_id": target.pk,
            "stage_id": stage.pk,
            "text": "Observação.",
        },
        format="json",
    )

    assert response.status_code == 404


def test_consulta_de_equipe_inexistente_retorna_404():
    admin = UserFactory(role=UserRole.ADMIN)
    client = authenticated_client(admin)

    response = client.get("/api/teams/999999/member-notes")

    assert response.status_code == 404
