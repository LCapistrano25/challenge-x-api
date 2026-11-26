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
from apps.core.tests.contract import mismatches, schema
from apps.editions.enums import EditionStatus
from apps.editions.factories import (
    ChallengeFactory,
    EditionFactory,
    StageFactory,
)
from apps.projects.models import Project
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
from apps.teams.models import Invitation, Team, TeamMember

pytestmark = pytest.mark.django_db

TEAMS_URL = "/api/teams"
DASHBOARD_URL = "/api/me/dashboard"


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
        {
            "name": "Equipe API",
            "invitations": [
                {"student_id": StudentFactory().pk},
                {"email": StudentFactory().user.email},
            ],
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["name"] == "Equipe API"
    assert response.data["code"]

    team = Team.objects.get(name="Equipe API")
    assert team.edition == edition
    assert Invitation.objects.filter(team=team).count() == 2


def test_criacao_so_com_o_nome_retorna_400_pedindo_convites():
    student = StudentFactory()
    edition = EditionFactory(status=EditionStatus.PUBLISHED)

    now = timezone.now()
    StageFactory(
        edition=edition,
        formation=True,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=7),
    )

    response = authenticated_client(student.user).post(
        TEAMS_URL, {"name": "Equipe Solo"}, format="json"
    )

    assert response.status_code == 400
    assert response.data["error"]["code"] == "team_invitations_required"
    assert not Team.objects.filter(name="Equipe Solo").exists()


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


def test_convite_fora_do_prazo_retorna_409_e_nao_500():
    team = TeamFactory()  # a edição não tem etapa de formação aberta
    leader = team.members.get(role="LEADER", active=True).student

    response = authenticated_client(leader.user).post(
        f"{TEAMS_URL}/{team.id}/invitations",
        {"student_id": StudentFactory().pk},
        format="json",
    )

    assert response.status_code == 409
    assert "prazo de formação" in response.data["error"]["message"]


@pytest.mark.parametrize("cadastro", ["inexistente", "nao_confirmado"])
def test_convite_por_email_de_aluno_sem_cadastro_valido_retorna_404(cadastro):
    # InvitationCreate aceita student_id ou email (#231).
    team = TeamFactory()
    create_open_formation(team.edition)
    leader = team.members.get(role="LEADER", active=True).student
    email = "ninguem@a.catolica-to.edu.br"
    if cadastro == "nao_confirmado":
        email = StudentFactory(user__email_confirmed=False).user.email

    response = authenticated_client(leader.user).post(
        f"{TEAMS_URL}/{team.id}/invitations", {"email": email}, format="json"
    )

    assert response.status_code == 404
    assert response.data["error"]["code"] == "not_found"
    assert not Invitation.objects.exists()


def test_convite_por_email_segue_o_contrato():
    team = TeamFactory()
    create_open_formation(team.edition)
    leader = team.members.get(role="LEADER", active=True).student
    body = {"email": StudentFactory().user.email}
    assert mismatches(body, schema("InvitationCreate")) == []

    response = authenticated_client(leader.user).post(
        f"{TEAMS_URL}/{team.id}/invitations", body, format="json"
    )

    assert response.status_code == 201
    assert mismatches(response.json(), schema("Invitation")) == []


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


def test_aluno_lista_equipes_com_vagas():
    student = StudentFactory()
    team = TeamFactory()
    team.edition.status = EditionStatus.PUBLISHED
    team.edition.max_members = 5
    team.edition.save()

    client = authenticated_client(student.user)

    response = client.get(TEAMS_URL)

    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["id"] == team.id
    assert response.data[0]["members_count"] == 1
    assert response.data[0]["available_vacancies"] == 4


def test_equipes_de_edicoes_nao_publicadas_nao_aparecem():
    student = StudentFactory()
    TeamFactory()

    client = authenticated_client(student.user)

    response = client.get(TEAMS_URL)

    assert response.status_code == 200
    assert len(response.data) == 0


def test_equipes_lotadas_nao_aparecem_na_consulta():
    student = StudentFactory()
    team = TeamFactory()

    team.edition.status = EditionStatus.PUBLISHED
    team.edition.min_members = 1
    team.edition.max_members = 2
    team.edition.save()

    TeamMemberFactory(team=team)

    client = authenticated_client(student.user)
    response = client.get(TEAMS_URL)

    assert response.status_code == 200
    assert len(response.data) == 0


def test_aluno_solicita_entrada_em_equipe_pela_api():
    team = TeamFactory()
    create_open_formation(team.edition)
    student = StudentFactory()

    client = authenticated_client(student.user)

    response = client.post(
        f"{TEAMS_URL}/{team.id}/join-requests",
        {},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["status"] == RequestStatus.PENDING
    assert response.data["team"]["id"] == team.id


def test_aluno_nao_pode_solicitar_entrada_duas_vezes():
    team = TeamFactory()
    create_open_formation(team.edition)
    student = StudentFactory()

    client = authenticated_client(student.user)

    first_response = client.post(
        f"{TEAMS_URL}/{team.id}/join-requests",
        {},
        format="json",
    )

    second_response = client.post(
        f"{TEAMS_URL}/{team.id}/join-requests",
        {},
        format="json",
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.data["error"]["code"] == "request_already_pending"


def test_aluno_nao_pode_solicitar_entrada_em_equipe_lotada():
    team = TeamFactory()
    create_open_formation(team.edition)

    team.edition.min_members = 1
    team.edition.max_members = 1
    team.edition.save()

    student = StudentFactory()
    client = authenticated_client(student.user)

    response = client.post(
        f"{TEAMS_URL}/{team.id}/join-requests",
        {},
        format="json",
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "team_full"


def test_aluno_nao_pode_solicitar_entrada_com_formacao_encerrada():
    team = TeamFactory()
    student = StudentFactory()

    now = timezone.now()
    StageFactory(
        edition=team.edition,
        formation=True,
        starts_at=now - timedelta(days=10),
        ends_at=now - timedelta(days=1),
    )

    client = authenticated_client(student.user)

    response = client.post(
        f"{TEAMS_URL}/{team.id}/join-requests",
        {},
        format="json",
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "formation_closed"


def test_usuario_que_nao_e_aluno_nao_solicita_entrada():
    team = TeamFactory()
    teacher = TeacherFactory()
    client = authenticated_client(teacher.user)

    response = client.post(
        f"{TEAMS_URL}/{team.id}/join-requests",
        {},
        format="json",
    )

    assert response.status_code == 403


def test_aluno_consulta_suas_solicitacoes_de_entrada():
    student = StudentFactory()
    join_request = JoinRequestFactory(student=student)

    client = authenticated_client(student.user)

    response = client.get("/api/me/join-requests")

    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["id"] == join_request.id


def test_aluno_filtra_suas_solicitacoes_por_status():
    student = StudentFactory()
    pending_request = JoinRequestFactory(
        student=student,
        status=RequestStatus.PENDING,
    )
    JoinRequestFactory(
        student=student,
        status=RequestStatus.REJECTED,
    )

    client = authenticated_client(student.user)

    response = client.get(
        "/api/me/join-requests",
        {"status": RequestStatus.PENDING},
    )

    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["id"] == pending_request.id


def test_aluno_nao_consulta_solicitacoes_de_outro_aluno():
    student = StudentFactory()
    JoinRequestFactory(student=StudentFactory())

    client = authenticated_client(student.user)

    response = client.get("/api/me/join-requests")

    assert response.status_code == 200
    assert len(response.data) == 0


def test_lider_consulta_solicitacoes_recebidas_pela_equipe():
    team = TeamFactory()
    join_request = JoinRequestFactory(team=team)

    leader = TeamMember.objects.get(
        team=team,
        role=MemberRole.LEADER,
        active=True,
    )

    client = authenticated_client(leader.student.user)

    response = client.get(f"{TEAMS_URL}/{team.id}/join-requests")

    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["id"] == join_request.id


def test_lider_filtra_solicitacoes_recebidas_por_status():
    team = TeamFactory()
    pending_request = JoinRequestFactory(
        team=team,
        status=RequestStatus.PENDING,
    )
    JoinRequestFactory(
        team=team,
        status=RequestStatus.REJECTED,
    )

    leader = TeamMember.objects.get(
        team=team,
        role=MemberRole.LEADER,
        active=True,
    )

    client = authenticated_client(leader.student.user)

    response = client.get(
        f"{TEAMS_URL}/{team.id}/join-requests",
        {"status": RequestStatus.PENDING},
    )

    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["id"] == pending_request.id


def test_aluno_que_nao_e_lider_nao_consulta_solicitacoes_da_equipe():
    team = TeamFactory()
    student = StudentFactory()

    client = authenticated_client(student.user)

    response = client.get(f"{TEAMS_URL}/{team.id}/join-requests")

    assert response.status_code == 404


def test_lider_aprova_solicitacao_de_entrada_pela_api():
    team = TeamFactory()

    now = timezone.now()
    StageFactory(
        edition=team.edition,
        formation=True,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=7),
    )

    join_request = JoinRequestFactory(team=team)

    leader = TeamMember.objects.get(
        team=team,
        role=MemberRole.LEADER,
        active=True,
    )

    client = authenticated_client(leader.student.user)

    response = client.post(
        f"/api/join-requests/{join_request.id}/respond",
        {"approve": True},
        format="json",
    )

    assert response.status_code == 200, response.data

    join_request.refresh_from_db()
    assert join_request.status == RequestStatus.APPROVED

    assert TeamMember.objects.filter(
        team=team,
        student=join_request.student,
        role=MemberRole.MEMBER,
        active=True,
    ).exists()


def test_lider_rejeita_solicitacao_de_entrada_pela_api():
    team = TeamFactory()

    now = timezone.now()
    StageFactory(
        edition=team.edition,
        formation=True,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=7),
    )

    join_request = JoinRequestFactory(team=team)

    leader = TeamMember.objects.get(
        team=team,
        role=MemberRole.LEADER,
        active=True,
    )

    client = authenticated_client(leader.student.user)

    response = client.post(
        f"/api/join-requests/{join_request.id}/respond",
        {"approve": False},
        format="json",
    )

    assert response.status_code == 200, response.data

    join_request.refresh_from_db()
    assert join_request.status == RequestStatus.REJECTED

    assert not TeamMember.objects.filter(
        team=team,
        student=join_request.student,
        active=True,
    ).exists()


def test_aluno_sai_da_equipe_pela_api():
    team = TeamFactory()
    create_open_formation(team.edition)

    leader = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    )

    student = StudentFactory(course=leader.student.course)

    membership = TeamMemberFactory(
        team=team,
        student=student,
        role=MemberRole.MEMBER,
    )

    client = authenticated_client(student.user)

    response = client.post(
        f"{TEAMS_URL}/{team.id}/leave", {"confirm": True}, format="json"
    )

    assert response.status_code == 204

    membership.refresh_from_db()
    assert membership.active is False
    assert membership.left_at is not None


def test_lider_sozinho_sai_pela_api_e_desfaz_a_equipe():
    team = TeamFactory()
    create_open_formation(team.edition)
    leader = team.members.get(role=MemberRole.LEADER, active=True)

    response = authenticated_client(leader.student.user).post(
        f"{TEAMS_URL}/{team.id}/leave"
    )

    assert response.status_code == 204
    team.refresh_from_db()
    assert team.status == TeamStatus.DISBANDED


def test_lider_com_outros_integrantes_nao_consegue_sair_pela_api():
    team = TeamFactory()
    create_open_formation(team.edition)
    TeamMemberFactory(team=team, role=MemberRole.MEMBER)

    leader = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    )

    client = authenticated_client(leader.student.user)

    response = client.post(f"{TEAMS_URL}/{team.id}/leave")

    assert response.status_code == 409
    assert response.data["error"]["code"] == "leader_must_transfer"


def test_aluno_que_nao_e_integrante_nao_consegue_sair_pela_api():
    team = TeamFactory()
    create_open_formation(team.edition)

    student = StudentFactory()
    client = authenticated_client(student.user)

    response = client.post(f"{TEAMS_URL}/{team.id}/leave")

    assert response.status_code == 404


def test_aluno_nao_consegue_sair_apos_formacao_pela_api():
    team = TeamFactory()

    StageFactory(
        edition=team.edition,
        formation=True,
        starts_at=timezone.now() - timedelta(days=3),
        ends_at=timezone.now() - timedelta(days=1),
    )

    leader = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    )

    student = StudentFactory(course=leader.student.course)

    membership = TeamMemberFactory(
        team=team,
        student=student,
        role=MemberRole.MEMBER,
    )

    client = authenticated_client(student.user)

    response = client.post(f"{TEAMS_URL}/{team.id}/leave")

    assert response.status_code == 409

    membership.refresh_from_db()
    assert membership.active is True
    assert membership.left_at is None


def test_professor_nao_consegue_sair_pela_api():
    team = TeamFactory()
    teacher = TeacherFactory()

    client = authenticated_client(teacher.user)

    response = client.post(f"{TEAMS_URL}/{team.id}/leave")

    assert response.status_code == 403


def test_saida_abaixo_do_minimo_pede_confirmacao_pela_api():
    team = TeamFactory()
    create_open_formation(team.edition)
    saindo = TeamMemberFactory(team=team, role=MemberRole.MEMBER)
    client = authenticated_client(saindo.student.user)

    sem_confirmar = client.post(f"{TEAMS_URL}/{team.id}/leave")
    confirmando = client.post(
        f"{TEAMS_URL}/{team.id}/leave", {"confirm": True}, format="json"
    )

    assert sem_confirmar.status_code == 409
    assert sem_confirmar.data["error"]["code"] == "leave_below_minimum"
    assert "1 de 3 integrantes" in sem_confirmar.data["error"]["message"]
    assert confirmando.status_code == 204


def test_dashboard_sem_autenticacao_retorna_401():
    response = APIClient().get(DASHBOARD_URL)

    assert response.status_code == 401


@pytest.mark.parametrize(
    "user_factory",
    [TeacherFactory, lambda: UserFactory(role=UserRole.ADMIN)],
)
def test_dashboard_para_usuario_sem_perfil_academico_retorna_403(user_factory):
    user = user_factory()
    response = authenticated_client(user.user if hasattr(user, "user") else user).get(
        DASHBOARD_URL
    )

    assert response.status_code == 403


def test_academico_consulta_dashboard_pela_api():
    student = StudentFactory()
    EditionFactory(status=EditionStatus.PUBLISHED)

    response = authenticated_client(student.user).get(DASHBOARD_URL)

    assert response.status_code == 200
    assert mismatches(response.data, schema("StudentDashboard")) == []
