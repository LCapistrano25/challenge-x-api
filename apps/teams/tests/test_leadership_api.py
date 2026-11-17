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
from apps.projects.factories import ProjectFactory
from apps.teams.enums import MemberRole, RequestStatus, TeamStatus
from apps.teams.factories import (
    LeadershipRequestFactory,
    TeamFactory,
    TeamMemberFactory,
)

pytestmark = pytest.mark.django_db


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def create_team_without_leader():
    team = TeamFactory(leader=False)
    project = ProjectFactory(team=team)
    student = StudentFactory(course=project.challenge.course)

    TeamMemberFactory(
        team=team,
        student=student,
        role=MemberRole.MEMBER,
    )

    return team, project, student


def test_lider_transfere_lideranca_pela_api():
    team = TeamFactory()
    leader = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    ).student

    new_leader = StudentFactory()
    TeamMemberFactory(
        team=team,
        student=new_leader,
        role=MemberRole.MEMBER,
    )

    client = authenticated_client(leader.user)

    response = client.post(
        f"/api/teams/{team.id}/leadership-transfer",
        {"student_id": new_leader.pk},
        format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["student"]["user_id"] == new_leader.user_id
    assert response.data["role"] == MemberRole.LEADER

    team.refresh_from_db()

    assert team.members.get(student=leader).role == MemberRole.MEMBER
    assert team.members.get(student=new_leader).role == MemberRole.LEADER


def test_aluno_que_nao_e_lider_nao_transfere_lideranca():
    team = TeamFactory()
    student = StudentFactory()

    client = authenticated_client(student.user)

    response = client.post(
        f"/api/teams/{team.id}/leadership-transfer",
        {"student_id": student.pk},
        format="json",
    )

    assert response.status_code == 403


def test_professor_nao_transfere_lideranca():
    from apps.accounts.factories import TeacherFactory

    team = TeamFactory()
    teacher = TeacherFactory()

    client = authenticated_client(teacher.user)

    response = client.post(
        f"/api/teams/{team.id}/leadership-transfer",
        {"student_id": 1},
        format="json",
    )

    assert response.status_code == 403


def test_transferencia_sem_student_id_retorna_400():
    team = TeamFactory()
    leader = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    ).student

    client = authenticated_client(leader.user)

    response = client.post(
        f"/api/teams/{team.id}/leadership-transfer",
        {},
        format="json",
    )

    assert response.status_code == 400


def test_nao_transfere_lideranca_para_aluno_de_outra_equipe():
    team = TeamFactory()
    leader = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    ).student
    other_student = StudentFactory()

    client = authenticated_client(leader.user)

    response = client.post(
        f"/api/teams/{team.id}/leadership-transfer",
        {"student_id": other_student.pk},
        format="json",
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "leadership_transfer_rejected"


def test_lider_nao_transfere_lideranca_para_si_mesmo():
    team = TeamFactory()
    leader = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    ).student

    client = authenticated_client(leader.user)

    response = client.post(
        f"/api/teams/{team.id}/leadership-transfer",
        {"student_id": leader.pk},
        format="json",
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "leadership_transfer_rejected"


def test_aluno_solicita_lideranca_pela_api():
    team, project, student = create_team_without_leader()

    client = authenticated_client(student.user)

    response = client.post(
        f"/api/teams/{team.id}/leadership-requests",
        {"justification": "A equipe precisa de um novo líder."},
        format="json",
    )

    assert response.status_code == 201, response.data
    assert response.data["status"] == RequestStatus.PENDING
    assert response.data["justification"] == "A equipe precisa de um novo líder."
    assert response.data["requester"]["user_id"] == student.user_id
    assert response.data["team"]["id"] == team.id


def test_aluno_nao_solicita_lideranca_de_equipe_com_lider_ativo():
    team = TeamFactory()
    project = ProjectFactory(team=team)
    student = StudentFactory(course=project.challenge.course)

    TeamMemberFactory(
        team=team,
        student=student,
        role=MemberRole.MEMBER,
    )

    client = authenticated_client(student.user)

    response = client.post(
        f"/api/teams/{team.id}/leadership-requests",
        {"justification": "Quero assumir a liderança."},
        format="json",
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "leadership_request_rejected"


def test_professor_nao_solicita_lideranca_pela_api():
    from apps.accounts.factories import TeacherFactory

    team, project, student = create_team_without_leader()
    teacher = TeacherFactory()

    client = authenticated_client(teacher.user)

    response = client.post(
        f"/api/teams/{team.id}/leadership-requests",
        {"justification": "Quero assumir a liderança."},
        format="json",
    )

    assert response.status_code == 403


def test_solicitacao_sem_justificativa_retorna_400():
    team, project, student = create_team_without_leader()

    client = authenticated_client(student.user)

    response = client.post(
        f"/api/teams/{team.id}/leadership-requests",
        {"justification": ""},
        format="json",
    )

    assert response.status_code == 400


def test_aluno_que_nao_faz_parte_da_equipe_nao_solicita_lideranca():
    team, project, student = create_team_without_leader()
    other_student = StudentFactory()

    client = authenticated_client(other_student.user)

    response = client.post(
        f"/api/teams/{team.id}/leadership-requests",
        {"justification": "Quero assumir a liderança."},
        format="json",
    )

    assert response.status_code == 404


def test_nao_permite_duas_solicitacoes_pendentes_pela_api():
    team, project, student = create_team_without_leader()

    client = authenticated_client(student.user)
    url = f"/api/teams/{team.id}/leadership-requests"

    first_response = client.post(
        url,
        {"justification": "Primeira solicitação."},
        format="json",
    )

    second_response = client.post(
        url,
        {"justification": "Segunda solicitação."},
        format="json",
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.data["error"]["code"] == "leadership_request_rejected"


def test_equipe_desclassificada_nao_aceita_solicitacao_de_lideranca():
    team = TeamFactory(disqualified=True, leader=False)
    project = ProjectFactory(team=team)
    student = StudentFactory(course=project.challenge.course)

    TeamMemberFactory(
        team=team,
        student=student,
        role=MemberRole.MEMBER,
    )

    client = authenticated_client(student.user)

    response = client.post(
        f"/api/teams/{team.id}/leadership-requests",
        {"justification": "Quero assumir a liderança."},
        format="json",
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "leadership_request_rejected"


def test_integrante_consulta_solicitacoes_de_lideranca_da_equipe():
    team, project, student = create_team_without_leader()

    leadership_request = LeadershipRequestFactory(
        team=team,
        requester=student,
        status=RequestStatus.PENDING,
        justification="A equipe precisa de um novo líder.",
    )

    client = authenticated_client(student.user)

    response = client.get(f"/api/teams/{team.id}/leadership-requests")

    assert response.status_code == 200, response.data
    assert len(response.data) == 1
    assert response.data[0]["id"] == leadership_request.id
    assert response.data[0]["status"] == RequestStatus.PENDING
    assert response.data[0]["requester"]["user_id"] == student.user_id


def test_aluno_de_outra_equipe_nao_consulta_solicitacoes():
    team, project, student = create_team_without_leader()
    other_student = StudentFactory()

    LeadershipRequestFactory(
        team=team,
        requester=student,
        status=RequestStatus.PENDING,
    )

    client = authenticated_client(other_student.user)

    response = client.get(f"/api/teams/{team.id}/leadership-requests")

    assert response.status_code == 404


def test_consulta_solicitacoes_filtrando_por_status():
    team, project, student = create_team_without_leader()

    pending_request = LeadershipRequestFactory(
        team=team,
        requester=student,
        status=RequestStatus.PENDING,
    )

    LeadershipRequestFactory(
        team=team,
        requester=student,
        status=RequestStatus.REJECTED,
    )

    client = authenticated_client(student.user)

    response = client.get(f"/api/teams/{team.id}/leadership-requests?status=PENDING")

    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["id"] == pending_request.id


def test_professor_consulta_solicitacoes_dos_seus_cursos():
    team, project, student = create_team_without_leader()

    teacher = TeacherFactory()
    TeacherCourseFactory(
        teacher=teacher,
        course=project.challenge.course,
        active=True,
    )

    leadership_request = LeadershipRequestFactory(
        team=team,
        requester=student,
        status=RequestStatus.PENDING,
    )

    client = authenticated_client(teacher.user)

    response = client.get("/api/teacher/leadership-requests")

    assert response.status_code == 200, response.data
    assert len(response.data) == 1
    assert response.data[0]["id"] == leadership_request.id


def test_professor_sem_vinculo_nao_consulta_solicitacoes():
    team, _, student = create_team_without_leader()

    teacher = TeacherFactory()

    LeadershipRequestFactory(
        team=team,
        requester=student,
        status=RequestStatus.PENDING,
    )

    client = authenticated_client(teacher.user)

    response = client.get("/api/teacher/leadership-requests")

    assert response.status_code == 200
    assert response.data == []


def test_professor_com_vinculo_inativo_nao_consulta_solicitacoes():
    team, project, student = create_team_without_leader()

    teacher = TeacherFactory()
    TeacherCourseFactory(
        teacher=teacher,
        course=project.challenge.course,
        active=False,
    )

    LeadershipRequestFactory(
        team=team,
        requester=student,
        status=RequestStatus.PENDING,
    )

    client = authenticated_client(teacher.user)

    response = client.get("/api/teacher/leadership-requests")

    assert response.status_code == 200
    assert response.data == []


def test_professor_aprova_solicitacao_de_lideranca_pela_api():
    team, project, student = create_team_without_leader()

    teacher = TeacherFactory()
    TeacherCourseFactory(
        teacher=teacher,
        course=project.challenge.course,
        active=True,
    )

    leadership_request = LeadershipRequestFactory(
        team=team,
        requester=student,
        status=RequestStatus.PENDING,
    )

    client = authenticated_client(teacher.user)

    response = client.post(
        f"/api/leadership-requests/{leadership_request.id}/decide",
        {
            "approve": True,
            "justification": "O aluno atende aos critérios para assumir a liderança.",
        },
        format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["status"] == RequestStatus.APPROVED

    membership = team.members.get(student=student, active=True)
    assert membership.role == MemberRole.LEADER

    leadership_request.refresh_from_db()
    assert leadership_request.teacher == teacher
    assert leadership_request.decided_at is not None


def test_professor_rejeita_solicitacao_de_lideranca_pela_api():
    team, project, student = create_team_without_leader()

    teacher = TeacherFactory()
    TeacherCourseFactory(
        teacher=teacher,
        course=project.challenge.course,
        active=True,
    )

    leadership_request = LeadershipRequestFactory(
        team=team,
        requester=student,
        status=RequestStatus.PENDING,
    )

    client = authenticated_client(teacher.user)

    response = client.post(
        f"/api/leadership-requests/{leadership_request.id}/decide",
        {
            "approve": False,
            "justification": "A solicitação não atende aos critérios estabelecidos.",
        },
        format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["status"] == RequestStatus.REJECTED

    membership = team.members.get(student=student, active=True)
    assert membership.role == MemberRole.MEMBER

    leadership_request.refresh_from_db()
    assert leadership_request.teacher == teacher
    assert leadership_request.decided_at is not None


def test_professor_sem_vinculo_nao_decide_solicitacao_de_lideranca():
    team, _, student = create_team_without_leader()

    teacher = TeacherFactory()

    leadership_request = LeadershipRequestFactory(
        team=team,
        requester=student,
        status=RequestStatus.PENDING,
    )

    client = authenticated_client(teacher.user)

    response = client.post(
        f"/api/leadership-requests/{leadership_request.id}/decide",
        {
            "approve": True,
            "justification": "Solicitação analisada.",
        },
        format="json",
    )

    assert response.status_code == 409

    leadership_request.refresh_from_db()
    assert leadership_request.status == RequestStatus.PENDING
    assert leadership_request.teacher is None


def test_professor_com_vinculo_inativo_nao_decide_solicitacao():
    team, project, student = create_team_without_leader()

    teacher = TeacherFactory()
    TeacherCourseFactory(
        teacher=teacher,
        course=project.challenge.course,
        active=False,
    )

    leadership_request = LeadershipRequestFactory(
        team=team,
        requester=student,
        status=RequestStatus.PENDING,
    )

    client = authenticated_client(teacher.user)

    response = client.post(
        f"/api/leadership-requests/{leadership_request.id}/decide",
        {
            "approve": True,
            "justification": "Solicitação analisada.",
        },
        format="json",
    )

    assert response.status_code == 409

    leadership_request.refresh_from_db()
    assert leadership_request.status == RequestStatus.PENDING
    assert leadership_request.teacher is None


def test_aluno_nao_pode_decidir_solicitacao_de_lideranca():
    team, _, student = create_team_without_leader()

    leadership_request = LeadershipRequestFactory(
        team=team,
        requester=student,
        status=RequestStatus.PENDING,
    )

    client = authenticated_client(student.user)

    response = client.post(
        f"/api/leadership-requests/{leadership_request.id}/decide",
        {
            "approve": True,
            "justification": "Solicitação analisada.",
        },
        format="json",
    )

    assert response.status_code == 403

    leadership_request.refresh_from_db()
    assert leadership_request.status == RequestStatus.PENDING


def test_decisao_sem_justificativa_retorna_400():
    team, project, student = create_team_without_leader()

    teacher = TeacherFactory()
    TeacherCourseFactory(
        teacher=teacher,
        course=project.challenge.course,
        active=True,
    )

    leadership_request = LeadershipRequestFactory(
        team=team,
        requester=student,
        status=RequestStatus.PENDING,
    )

    client = authenticated_client(teacher.user)

    response = client.post(
        f"/api/leadership-requests/{leadership_request.id}/decide",
        {
            "approve": True,
            "justification": "",
        },
        format="json",
    )

    assert response.status_code == 400

    leadership_request.refresh_from_db()
    assert leadership_request.status == RequestStatus.PENDING


def test_professor_nao_decide_solicitacao_ja_decidida():
    team, project, student = create_team_without_leader()

    teacher = TeacherFactory()
    TeacherCourseFactory(
        teacher=teacher,
        course=project.challenge.course,
        active=True,
    )

    leadership_request = LeadershipRequestFactory(
        team=team,
        requester=student,
        status=RequestStatus.REJECTED,
    )

    client = authenticated_client(teacher.user)

    response = client.post(
        f"/api/leadership-requests/{leadership_request.id}/decide",
        {
            "approve": True,
            "justification": "Nova análise da solicitação.",
        },
        format="json",
    )

    assert response.status_code == 409

    leadership_request.refresh_from_db()
    assert leadership_request.status == RequestStatus.REJECTED


def test_professor_nao_decide_solicitacao_inexistente():
    teacher = TeacherFactory()
    client = authenticated_client(teacher.user)

    response = client.post(
        "/api/leadership-requests/999999/decide",
        {
            "approve": True,
            "justification": "Solicitação analisada.",
        },
        format="json",
    )

    assert response.status_code == 404


def test_professor_nao_decide_solicitacao_de_equipe_desclassificada():
    team, project, student = create_team_without_leader()

    admin = UserFactory(role=UserRole.ADMIN)

    team.status = TeamStatus.DISQUALIFIED
    team.disqualification_reason = "Descumprimento do regulamento."
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

    teacher = TeacherFactory()
    TeacherCourseFactory(
        teacher=teacher,
        course=project.challenge.course,
        active=True,
    )

    leadership_request = LeadershipRequestFactory(
        team=team,
        requester=student,
        status=RequestStatus.PENDING,
    )

    client = authenticated_client(teacher.user)

    response = client.post(
        f"/api/leadership-requests/{leadership_request.id}/decide",
        {
            "approve": True,
            "justification": "Solicitação analisada.",
        },
        format="json",
    )

    assert response.status_code == 409

    leadership_request.refresh_from_db()
    assert leadership_request.status == RequestStatus.PENDING
    assert leadership_request.teacher is None


def test_professor_nao_decide_solicitacao_de_equipe_com_lider_ativo():
    team = TeamFactory()
    leader = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    ).student

    project = ProjectFactory(team=team)

    teacher = TeacherFactory()
    TeacherCourseFactory(
        teacher=teacher,
        course=project.challenge.course,
        active=True,
    )

    leadership_request = LeadershipRequestFactory(
        team=team,
        requester=leader,
        status=RequestStatus.PENDING,
    )

    client = authenticated_client(teacher.user)

    response = client.post(
        f"/api/leadership-requests/{leadership_request.id}/decide",
        {
            "approve": True,
            "justification": "Solicitação analisada.",
        },
        format="json",
    )

    assert response.status_code == 409

    leadership_request.refresh_from_db()
    assert leadership_request.status == RequestStatus.PENDING
    assert leadership_request.teacher is None
