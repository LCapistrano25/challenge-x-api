import json
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.factories import (
    ExternalReviewerFactory,
    StudentFactory,
    TeacherCourseFactory,
    TeacherFactory,
    UserFactory,
)
from apps.editions.enums import EditionStatus, FieldKind
from apps.editions.factories import (
    CategoryFactory,
    ChallengeFactory,
    StageFactory,
    StageSubmissionFieldFactory,
)
from apps.projects.factories import (
    DeadlineExtensionFactory,
    ProjectFactory,
    SubmissionFactory,
    SubmissionReceiptFactory,
    SubmissionVersionFactory,
)
from apps.projects.files import get_delivery_storage
from apps.projects.models import DeadlineExtension
from apps.projects.tests.conftest import stored_keys, valid_canvas
from apps.teams.enums import MemberRole
from apps.teams.factories import TeamFactory, TeamMemberFactory

pytestmark = pytest.mark.django_db


def url(team, suffix=""):
    return f"/api/teams/{team.pk}/project{suffix}"


def client_for(user):
    client = APIClient()
    client.force_login(user)
    return client


def error_code(response):
    return response.data["error"]["code"]


@pytest.fixture
def team():
    team = TeamFactory()
    now = timezone.now()
    StageFactory(
        formation=True,
        edition=team.edition,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=1),
    )
    return team


@pytest.fixture
def leader(team):
    return team.members.get(role=MemberRole.LEADER).student.user


@pytest.fixture
def challenge(team):
    course = team.members.get(role=MemberRole.LEADER).student.course
    return ChallengeFactory(edition=team.edition, course=course)


@pytest.fixture
def member(team):
    return TeamMemberFactory(team=team).student.user


# GET /api/teams/{team_id}/project/options (RF29, RF50)


def test_opcoes_devolvem_desafios_elegiveis_e_categorias(team, member, challenge):
    ChallengeFactory(edition=team.edition)  # curso sem integrante
    category = CategoryFactory(edition=team.edition, description="Categoria A")
    CategoryFactory(edition=team.edition, active=False)

    response = client_for(member).get(url(team, "/options"))

    assert response.status_code == 200
    assert response.data["challenges"] == [
        {
            "id": challenge.pk,
            "description": challenge.description,
            "course": {"id": challenge.course.pk, "name": challenge.course.name},
            "sdg": {
                "id": challenge.sdg.pk,
                "number": challenge.sdg.number,
                "title": challenge.sdg.title,
            },
        }
    ]
    assert response.data["categories"] == [
        {"id": category.pk, "name": category.name, "description": "Categoria A"}
    ]


def test_opcoes_exigem_login(team):
    assert APIClient().get(url(team, "/options")).status_code == 401


def test_opcoes_recusam_quem_nao_e_aluno(team):
    admin = UserFactory(role=UserRole.ADMIN)
    assert client_for(admin).get(url(team, "/options")).status_code == 403


def test_opcoes_recusam_aluno_de_fora_da_equipe(team):
    de_fora = StudentFactory().user
    response = client_for(de_fora).get(url(team, "/options"))
    assert response.status_code == 403
    assert error_code(response) == "project_access_denied"


def test_opcoes_de_equipe_inexistente(member):
    response = client_for(member).get("/api/teams/999999/project/options")
    assert response.status_code == 404


# GET /api/teams/{team_id}/project (RF30, RF20)


def full_project(team, challenge):
    return ProjectFactory(
        team=team,
        challenge=challenge,
        title="Água limpa",
        category=CategoryFactory(edition=team.edition),
    )


def test_aluno_integrante_consulta_o_projeto(team, member, challenge):
    project = full_project(team, challenge)

    response = client_for(member).get(url(team))

    assert response.status_code == 200
    data = response.data
    assert (data["id"], data["team_id"], data["edition_id"]) == (
        project.pk,
        team.pk,
        team.edition_id,
    )
    assert data["title"] == "Água limpa"
    assert data["summary"] == "Resumo da proposta."
    assert data["objective"] == ""
    assert data["status"] == "IN_PROGRESS"
    assert data["challenge"]["id"] == challenge.pk
    assert data["category"] == {
        "id": project.category.pk,
        "name": project.category.name,
    }
    assert {c["id"] for c in data["courses"]} == {
        m.student.course_id for m in team.members.all()
    }


def test_projeto_sem_desafio_mostra_desafio_nulo(team, member):
    ProjectFactory(team=team, challenge=None, category=None, title="")

    response = client_for(member).get(url(team))

    assert response.status_code == 200
    assert response.data["challenge"] is None
    assert response.data["category"] is None


def test_admin_consulta_qualquer_projeto(team, challenge):
    full_project(team, challenge)
    admin = UserFactory(role=UserRole.ADMIN)
    assert client_for(admin).get(url(team)).status_code == 200


def test_professor_do_curso_do_desafio_consulta(team, challenge):
    full_project(team, challenge)
    link = TeacherCourseFactory(course=challenge.course)
    assert client_for(link.teacher.user).get(url(team)).status_code == 200


def test_professor_de_outro_curso_e_recusado(team, challenge):
    full_project(team, challenge)
    teacher = TeacherFactory().user
    response = client_for(teacher).get(url(team))
    assert response.status_code == 403
    assert error_code(response) == "project_access_denied"


def test_professor_com_vinculo_inativo_e_recusado(team, challenge):
    full_project(team, challenge)
    link = TeacherCourseFactory(course=challenge.course, active=False)
    assert client_for(link.teacher.user).get(url(team)).status_code == 403


def test_professor_nao_ve_projeto_sem_desafio(team):
    ProjectFactory(team=team, challenge=None)
    link = TeacherCourseFactory()
    assert client_for(link.teacher.user).get(url(team)).status_code == 403


def test_aluno_de_fora_da_equipe_nao_consulta(team, challenge):
    full_project(team, challenge)
    assert client_for(StudentFactory().user).get(url(team)).status_code == 403


def test_consulta_do_projeto_exige_login(team):
    assert APIClient().get(url(team)).status_code == 401


def test_consulta_de_equipe_sem_projeto_da_404(team, member):
    response = client_for(member).get(url(team))
    assert response.status_code == 404


def test_consulta_de_equipe_inexistente(member):
    assert client_for(member).get("/api/teams/999999/project").status_code == 404


# PUT /api/teams/{team_id}/project/challenge (RF29)


def test_lider_escolhe_o_desafio(team, leader, challenge):
    response = client_for(leader).put(
        url(team, "/challenge"), {"challenge_id": challenge.pk}, format="json"
    )

    assert response.status_code == 200
    assert response.data["challenge"]["id"] == challenge.pk
    assert response.data["team_id"] == team.pk
    assert response.data["title"] == ""


def test_escolher_com_desafio_inexistente_e_erro_de_validacao(team, leader):
    response = client_for(leader).put(
        url(team, "/challenge"), {"challenge_id": 999999}, format="json"
    )
    assert response.status_code == 400
    assert error_code(response) == "validation_error"
    assert "challenge_id" in response.data["error"]["details"]


def test_escolher_sem_o_campo_e_erro_de_validacao(team, leader):
    response = client_for(leader).put(url(team, "/challenge"), {}, format="json")
    assert response.status_code == 400
    assert error_code(response) == "validation_error"


def test_escolher_desafio_nao_elegivel(team, leader):
    estranho = ChallengeFactory(edition=team.edition)
    response = client_for(leader).put(
        url(team, "/challenge"), {"challenge_id": estranho.pk}, format="json"
    )
    assert response.status_code == 400
    assert error_code(response) == "challenge_not_eligible"


def test_escolher_recusa_quem_nao_e_lider(team, member, challenge):
    response = client_for(member).put(
        url(team, "/challenge"), {"challenge_id": challenge.pk}, format="json"
    )
    assert response.status_code == 403
    assert error_code(response) == "not_team_leader"


def test_escolher_recusa_quem_nao_e_aluno(team, challenge):
    admin = UserFactory(role=UserRole.ADMIN)
    response = client_for(admin).put(
        url(team, "/challenge"), {"challenge_id": challenge.pk}, format="json"
    )
    assert response.status_code == 403


def test_escolher_exige_login(team, challenge):
    response = APIClient().put(
        url(team, "/challenge"), {"challenge_id": challenge.pk}, format="json"
    )
    assert response.status_code == 401


def test_escolher_fora_do_prazo(team, leader, challenge):
    team.edition.stages.all().delete()
    response = client_for(leader).put(
        url(team, "/challenge"), {"challenge_id": challenge.pk}, format="json"
    )
    assert response.status_code == 409
    assert error_code(response) == "formation_closed"


def test_escolher_em_equipe_inexistente(leader, challenge):
    response = client_for(leader).put(
        "/api/teams/999999/project/challenge",
        {"challenge_id": challenge.pk},
        format="json",
    )
    assert response.status_code == 404


# PUT /api/teams/{team_id}/project/details (RF30)

DETAILS = {"title": "Água limpa", "summary": "Sensores no campus."}


@pytest.fixture
def project(team, challenge):
    return ProjectFactory(team=team, challenge=challenge, title="", summary="")


def test_lider_cadastra_os_dados(team, leader, project):
    response = client_for(leader).put(
        url(team, "/details"), {**DETAILS, "objective": "Reduzir 20%."}, format="json"
    )

    assert response.status_code == 200
    assert response.data["id"] == project.pk
    assert response.data["title"] == "Água limpa"
    assert response.data["summary"] == "Sensores no campus."
    assert response.data["objective"] == "Reduzir 20%."


def test_lider_atualiza_os_dados(team, leader, project):
    client = client_for(leader)
    client.put(url(team, "/details"), DETAILS, format="json")

    response = client.put(
        url(team, "/details"), {"title": "Novo", "summary": "Outro"}, format="json"
    )

    assert response.status_code == 200
    assert response.data["title"] == "Novo"
    assert response.data["objective"] == ""


@pytest.mark.parametrize(
    "body",
    [
        {"summary": "x"},
        {"title": "x"},
        {"title": "", "summary": "x"},
        {"title": "x", "summary": "   "},
        {"title": "x" * 201, "summary": "x"},
    ],
)
def test_dados_invalidos_sao_erro_de_validacao(team, leader, project, body):
    response = client_for(leader).put(url(team, "/details"), body, format="json")
    assert response.status_code == 400
    assert error_code(response) == "validation_error"


def test_dados_recusam_quem_nao_e_lider(team, member, project):
    response = client_for(member).put(url(team, "/details"), DETAILS, format="json")
    assert response.status_code == 403
    assert error_code(response) == "not_team_leader"


def test_dados_recusam_quem_nao_e_aluno(team, project):
    teacher = TeacherFactory().user
    response = client_for(teacher).put(url(team, "/details"), DETAILS, format="json")
    assert response.status_code == 403


def test_dados_exigem_login(team, project):
    assert (
        APIClient().put(url(team, "/details"), DETAILS, format="json").status_code
        == 401
    )


def test_dados_fora_do_prazo(team, leader, project):
    team.edition.stages.all().delete()
    response = client_for(leader).put(url(team, "/details"), DETAILS, format="json")
    assert response.status_code == 409
    assert error_code(response) == "formation_closed"


def test_dados_sem_desafio_escolhido(team, leader, project):
    project.challenge = None
    project.save()
    response = client_for(leader).put(url(team, "/details"), DETAILS, format="json")
    assert response.status_code == 409
    assert error_code(response) == "challenge_not_selected"


def test_dados_com_titulo_repetido_na_edicao(team, leader, project):
    ProjectFactory(team=TeamFactory(edition=team.edition), title="ÁGUA LIMPA")
    body = {"title": "água  limpa", "summary": "x"}

    response = client_for(leader).put(url(team, "/details"), body, format="json")

    assert response.status_code == 409
    assert error_code(response) == "project_title_taken"


def test_dados_em_equipe_inexistente(leader):
    response = client_for(leader).put(
        "/api/teams/999999/project/details", DETAILS, format="json"
    )
    assert response.status_code == 404


# Fluxo completo: escolher o desafio e depois cadastrar os dados


def test_fluxo_escolher_e_cadastrar_e_consultar(team, leader, challenge):
    client = client_for(leader)

    client.put(url(team, "/challenge"), {"challenge_id": challenge.pk}, format="json")
    client.put(url(team, "/details"), DETAILS, format="json")
    response = client.get(url(team))

    assert response.status_code == 200
    assert response.data["challenge"]["id"] == challenge.pk
    assert response.data["title"] == "Água limpa"


# PUT /api/teams/{team_id}/project/category (RF30, RF49)


@pytest.fixture
def category(team):
    return CategoryFactory(edition=team.edition)


def put_category(user, team, payload):
    return client_for(user).put(url(team, "/category"), payload, format="json")


def test_lider_escolhe_a_categoria(team, leader, project, category):
    response = put_category(leader, team, {"category_id": category.pk})

    assert response.status_code == 200
    assert response.data["category"] == {"id": category.pk, "name": category.name}
    assert response.data["team_id"] == team.pk


def test_escolher_categoria_exige_login(team, project, category):
    response = APIClient().put(
        url(team, "/category"), {"category_id": category.pk}, format="json"
    )
    assert response.status_code == 401


def test_admin_nao_escolhe_categoria(team, project, category):
    admin = UserFactory(role=UserRole.ADMIN)
    before = project.category_id
    response = put_category(admin, team, {"category_id": category.pk})
    assert response.status_code == 403
    project.refresh_from_db()
    assert project.category_id == before


def test_categoria_recusa_quem_nao_e_lider(team, member, project, category):
    response = put_category(member, team, {"category_id": category.pk})
    assert response.status_code == 403
    assert error_code(response) == "not_team_leader"


def test_categoria_em_equipe_inexistente(leader, category):
    response = client_for(leader).put(
        "/api/teams/999999/project/category",
        {"category_id": category.pk},
        format="json",
    )
    assert response.status_code == 404


def test_categoria_inexistente_e_erro_de_validacao(team, leader, project):
    response = put_category(leader, team, {"category_id": 999999})
    assert response.status_code == 400
    assert error_code(response) == "validation_error"
    assert "category_id" in response.data["error"]["details"]


@pytest.mark.parametrize("payload", [{}, {"category_id": None}])
def test_categoria_ausente_ou_nula_e_erro_de_validacao(team, leader, project, payload):
    response = put_category(leader, team, payload)
    assert response.status_code == 400
    assert error_code(response) == "validation_error"


@pytest.mark.parametrize("kind", ["inativa", "outra_edicao"])
def test_categoria_indisponivel(team, leader, project, kind):
    if kind == "inativa":
        category = CategoryFactory(edition=team.edition, active=False)
    else:
        category = CategoryFactory()
    response = put_category(leader, team, {"category_id": category.pk})
    assert response.status_code == 400
    assert error_code(response) == "category_not_available"


def test_categoria_fora_do_prazo(team, leader, project, category):
    team.edition.stages.all().delete()
    response = put_category(leader, team, {"category_id": category.pk})
    assert response.status_code == 409
    assert error_code(response) == "formation_closed"


def test_categoria_sem_projeto(team, leader, category):
    response = put_category(leader, team, {"category_id": category.pk})
    assert response.status_code == 409
    assert error_code(response) == "project_not_found"


# Entregas da etapa (UC34, RF31)


@pytest.fixture
def dproject():
    return ProjectFactory()


@pytest.fixture
def dleader(dproject):
    return dproject.team.members.get(role=MemberRole.LEADER).student.user


def make_stage(project, start=-1, end=1, **fields):
    now = timezone.now()
    return StageFactory(
        edition=project.edition,
        starts_at=now + timedelta(days=start),
        ends_at=now + timedelta(days=end),
        **fields,
    )


@pytest.fixture
def dstage(dproject):
    return make_stage(dproject)


@pytest.fixture
def dfield(dstage):
    return StageSubmissionFieldFactory(stage=dstage, label="Repositório")


def versions_url(project, stage):
    return f"/api/projects/{project.pk}/stages/{stage.pk}/versions"


def deliverables_url(project):
    return f"/api/projects/{project.pk}/deliverables"


def payload(field, link="https://github.com/equipe/projeto", **extra):
    return {"items": [{"field_id": field.pk, "link": link}], **extra}


def post_version(user, project, stage, body):
    return client_for(user).post(versions_url(project, stage), body, format="json")


def test_lider_envia_a_entrega(dproject, dleader, dstage, dfield):
    response = post_version(dleader, dproject, dstage, payload(dfield, notes="Ok"))

    assert response.status_code == 201
    assert response.data["number"] == 1
    assert response.data["notes"] == "Ok"
    assert response.data["submitted_by"] == {
        "user_id": dleader.pk,
        "name": dleader.name,
    }
    item = response.data["items"][0]
    assert item["field_id"] == dfield.pk
    assert item["type"] == "LINK"
    assert item["link"] == "https://github.com/equipe/projeto"
    assert item["file_url"] is None
    assert response.data["receipt"]["verification_code"]
    assert response.data["receipt"]["file_url"] is None


def test_envio_exige_login(dproject, dstage, dfield):
    response = APIClient().post(
        versions_url(dproject, dstage), payload(dfield), format="json"
    )
    assert response.status_code == 401
    assert error_code(response) == "not_authenticated"


def test_quem_nao_e_aluno_nao_envia(dproject, dstage, dfield):
    users = (
        TeacherFactory().user,
        UserFactory(role=UserRole.ADMIN),
        ExternalReviewerFactory().user,
    )
    for user in users:
        response = post_version(user, dproject, dstage, payload(dfield))
        assert response.status_code == 403
        assert error_code(response) == "permission_denied"


def test_nao_lider_recebe_403_not_team_leader(dproject, dstage, dfield):
    member = TeamMemberFactory(team=dproject.team).student.user
    response = post_version(member, dproject, dstage, payload(dfield))
    assert response.status_code == 403
    assert error_code(response) == "not_team_leader"


def test_envio_de_projeto_inexistente_da_404(dleader, dstage, dfield):
    response = client_for(dleader).post(
        f"/api/projects/999999/stages/{dstage.pk}/versions",
        payload(dfield),
        format="json",
    )
    assert response.status_code == 404


def test_envio_de_etapa_inexistente_da_404(dproject, dleader, dfield):
    response = client_for(dleader).post(
        f"/api/projects/{dproject.pk}/stages/999999/versions",
        payload(dfield),
        format="json",
    )
    assert response.status_code == 404


def test_envio_em_etapa_de_formacao_da_404(dproject, dleader):
    stage = make_stage(dproject, formation=True)
    field = StageSubmissionFieldFactory(stage=stage)
    response = post_version(dleader, dproject, stage, payload(field))
    assert response.status_code == 404
    assert error_code(response) == "stage_not_found"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"items": []},
        {"items": [{"field_id": 999999, "link": "https://a.dev"}]},
        {"items": [{"field_id": None, "link": "https://a.dev"}]},
        {"items": [{"field_id": 1}]},
        {"items": [{"field_id": 1, "link": "nao-e-url"}]},
    ],
)
def test_envio_com_corpo_invalido_da_400(body, dproject, dleader, dstage, dfield):
    if body.get("items") and body["items"][0].get("field_id") == 1:
        body["items"][0]["field_id"] = dfield.pk
    response = post_version(dleader, dproject, dstage, body)
    assert response.status_code == 400
    assert error_code(response) == "validation_error"


def test_envio_sem_campo_obrigatorio_da_400(dproject, dleader, dstage, dfield):
    other = StageSubmissionFieldFactory(stage=dstage, required=True)
    response = post_version(dleader, dproject, dstage, payload(dfield))
    assert response.status_code == 400
    assert error_code(response) == "validation_error"
    assert other.pk


def test_envio_com_campo_de_outra_etapa_da_400(dproject, dleader, dstage, dfield):
    other = StageSubmissionFieldFactory()
    response = post_version(dleader, dproject, dstage, payload(other))
    assert response.status_code == 400


def test_envio_com_projeto_incompleto_da_400(dproject, dleader, dstage, dfield):
    dproject.summary = ""
    dproject.save()
    response = post_version(dleader, dproject, dstage, payload(dfield))
    assert response.status_code == 400
    assert error_code(response) == "validation_error"


def test_envio_sem_categoria_da_400(dproject, dleader, dstage, dfield):
    # Categoria obrigatória para a premiação (D-06).
    dproject.category = None
    dproject.save()
    response = post_version(dleader, dproject, dstage, payload(dfield))
    assert response.status_code == 400
    assert error_code(response) == "validation_error"
    assert "category" in response.data["error"]["details"]


def test_envio_com_prazo_encerrado_da_409(dproject, dleader):
    stage = make_stage(dproject, start=-5, end=-1)
    field = StageSubmissionFieldFactory(stage=stage)
    response = post_version(dleader, dproject, stage, payload(field))
    assert response.status_code == 409
    assert error_code(response) == "stage_deadline_closed"


def test_envio_antes_do_inicio_da_409(dproject, dleader):
    stage = make_stage(dproject, start=1, end=5)
    field = StageSubmissionFieldFactory(stage=stage)
    response = post_version(dleader, dproject, stage, payload(field))
    assert response.status_code == 409
    assert error_code(response) == "stage_not_open"


def test_envio_de_equipe_desclassificada_da_409(dstage, dfield):
    team = TeamFactory(edition=dstage.edition, disqualified=True)
    project = ProjectFactory(team=team)
    leader = team.members.get(role=MemberRole.LEADER).student.user
    response = post_version(leader, project, dstage, payload(dfield))
    assert response.status_code == 409
    assert error_code(response) == "team_disqualified"


def test_envio_de_equipe_incompleta_da_409(dstage, dfield):
    team = TeamFactory(edition=dstage.edition, incomplete=True)
    project = ProjectFactory(team=team)
    leader = team.members.get(role=MemberRole.LEADER).student.user
    response = post_version(leader, project, dstage, payload(dfield))
    assert response.status_code == 409
    assert error_code(response) == "team_incomplete"


def test_envio_com_edicao_encerrada_da_409(dproject, dleader, dstage, dfield):
    dproject.edition.status = "CLOSED"
    dproject.edition.save()
    response = post_version(dleader, dproject, dstage, payload(dfield))
    assert response.status_code == 409
    assert error_code(response) == "edition_closed"


# GET /api/projects/{project_id}/deliverables


def test_aluno_integrante_consulta_as_entregas(dproject, dleader, dstage, dfield):
    post_version(dleader, dproject, dstage, payload(dfield))
    post_version(dleader, dproject, dstage, payload(dfield, link="https://x.dev/2"))

    response = client_for(dleader).get(deliverables_url(dproject))

    assert response.status_code == 200
    assert len(response.data) == 1
    entry = response.data[0]
    assert entry["stage"]["id"] == dstage.pk
    assert entry["stage"]["order"] == dstage.order
    assert entry["stage"]["phase_status"] == "OPEN"
    assert entry["fields"][0]["id"] == dfield.pk
    assert entry["fields"][0]["kind"] == "LINK"
    assert entry["fields"][0]["required"] is True
    assert entry["status"] == "SUBMITTED"
    assert entry["official_version_id"] is None
    assert [v["number"] for v in entry["versions"]] == [2, 1]
    assert entry["versions"][0]["receipt"]["verification_code"]


def test_etapa_sem_envio_aparece_como_nao_enviada(dproject, dleader, dfield):
    response = client_for(dleader).get(deliverables_url(dproject))
    assert response.data[0]["status"] == "NOT_SUBMITTED"
    assert response.data[0]["versions"] == []


def test_status_nao_entregue_depois_do_prazo(dproject, dleader):
    stage = make_stage(dproject, start=-5, end=-1)
    StageSubmissionFieldFactory(stage=stage)
    response = client_for(dleader).get(deliverables_url(dproject))
    assert response.data[0]["status"] == "NOT_DELIVERED"
    assert response.data[0]["official_version_id"] is None


def test_professor_do_curso_e_admin_consultam_entregas(dproject, dstage, dfield):
    link = TeacherCourseFactory(course=dproject.challenge.course)
    admin = UserFactory(role=UserRole.ADMIN)
    for user in (link.teacher.user, admin):
        assert client_for(user).get(deliverables_url(dproject)).status_code == 200


def test_consulta_de_entregas_recusa_quem_nao_pode(dproject, dstage, dfield):
    outsiders = (
        StudentFactory().user,
        TeacherFactory().user,
        ExternalReviewerFactory().user,
    )
    for user in outsiders:
        assert client_for(user).get(deliverables_url(dproject)).status_code == 403


def test_consulta_de_entregas_exige_login(dproject):
    response = APIClient().get(deliverables_url(dproject))
    assert response.status_code == 401
    assert error_code(response) == "not_authenticated"


def test_consulta_de_entregas_de_projeto_inexistente_da_404(dleader):
    assert (
        client_for(dleader).get("/api/projects/999999/deliverables").status_code == 404
    )


# POST multipart com arquivos (P-43, #107)

PDF_BYTES = b"%PDF-1.7 conteudo"


@pytest.fixture
def ffield(dstage):
    return StageSubmissionFieldFactory(
        stage=dstage,
        kind=FieldKind.FILE,
        label="Relatório",
        formats="pdf",
        max_size_mb=1,
    )


def post_multipart(user, project, stage, items, files=(), **extra):
    body = {"items": json.dumps(items), **extra}
    if files:
        body["files[]"] = list(files)
    return client_for(user).post(versions_url(project, stage), body, format="multipart")


def pdf_upload(name="relatorio.pdf", content=PDF_BYTES):
    return SimpleUploadedFile(name, content)


def test_multipart_envia_arquivo(dproject, dleader, dstage, ffield):
    response = post_multipart(
        dleader,
        dproject,
        dstage,
        [{"field_id": ffield.pk, "file_index": 0}],
        [pdf_upload("Meu Relatório.pdf")],
        notes="Com arquivo",
    )

    assert response.status_code == 201, response.data
    assert response.data["notes"] == "Com arquivo"
    item = response.data["items"][0]
    assert item["type"] == "FILE"
    assert item["link"] is None
    assert item["file_name"] == "Meu_Relatório.pdf"
    assert item["size_bytes"] == len(PDF_BYTES)
    assert item["file_url"]


def test_multipart_envia_link_e_arquivo(dproject, dleader, dstage, dfield, ffield):
    response = post_multipart(
        dleader,
        dproject,
        dstage,
        [
            {"field_id": dfield.pk, "link": "https://github.com/equipe/projeto"},
            {"field_id": ffield.pk, "file_index": 0},
        ],
        [pdf_upload()],
    )

    assert response.status_code == 201, response.data
    assert sorted(i["type"] for i in response.data["items"]) == ["FILE", "LINK"]


def test_multipart_aceita_o_nome_files_sem_colchetes(dproject, dleader, dstage, ffield):
    body = {
        "items": json.dumps([{"field_id": ffield.pk, "file_index": 0}]),
        "files": pdf_upload(),
    }
    response = client_for(dleader).post(
        versions_url(dproject, dstage), body, format="multipart"
    )
    assert response.status_code == 201, response.data


def test_multipart_so_com_link_continua_valido(dproject, dleader, dstage, dfield):
    response = post_multipart(
        dleader,
        dproject,
        dstage,
        [{"field_id": dfield.pk, "link": "https://github.com/equipe/projeto"}],
    )
    assert response.status_code == 201, response.data


def test_multipart_extensao_fora_do_formato_da_400(dproject, dleader, dstage, ffield):
    response = post_multipart(
        dleader,
        dproject,
        dstage,
        [{"field_id": ffield.pk, "file_index": 0}],
        [pdf_upload("a.txt", b"texto")],
    )
    assert response.status_code == 400
    assert error_code(response) == "file_format_not_allowed"


def test_multipart_arquivo_grande_da_400(dproject, dleader, dstage, ffield):
    big = pdf_upload(content=b"%PDF" + b"0" * (1024 * 1024 + 1))
    response = post_multipart(
        dleader, dproject, dstage, [{"field_id": ffield.pk, "file_index": 0}], [big]
    )
    assert response.status_code == 400
    assert error_code(response) == "file_too_large"


def test_multipart_arquivo_vazio_da_400(dproject, dleader, dstage, ffield):
    response = post_multipart(
        dleader,
        dproject,
        dstage,
        [{"field_id": ffield.pk, "file_index": 0}],
        [pdf_upload(content=b"")],
    )
    assert response.status_code == 400
    assert error_code(response) == "validation_error"


def test_multipart_campo_de_arquivo_obrigatorio_sem_arquivo_da_400(
    dproject, dleader, dstage, dfield, ffield
):
    response = post_multipart(
        dleader,
        dproject,
        dstage,
        [{"field_id": dfield.pk, "link": "https://github.com/equipe/projeto"}],
    )
    assert response.status_code == 400
    assert error_code(response) == "validation_error"


def test_multipart_indice_fora_da_faixa_da_400(dproject, dleader, dstage, ffield):
    response = post_multipart(
        dleader,
        dproject,
        dstage,
        [{"field_id": ffield.pk, "file_index": 1}],
        [pdf_upload()],
    )
    assert response.status_code == 400
    assert error_code(response) == "validation_error"


def test_multipart_indice_repetido_da_400(dproject, dleader, dstage, ffield):
    other = StageSubmissionFieldFactory(
        stage=dstage, kind=FieldKind.FILE, formats="pdf"
    )
    response = post_multipart(
        dleader,
        dproject,
        dstage,
        [
            {"field_id": ffield.pk, "file_index": 0},
            {"field_id": other.pk, "file_index": 0},
        ],
        [pdf_upload(), pdf_upload()],
    )
    assert response.status_code == 400
    assert error_code(response) == "validation_error"


def test_multipart_arquivo_sobrando_da_400(dproject, dleader, dstage, dfield, ffield):
    response = post_multipart(
        dleader,
        dproject,
        dstage,
        [
            {"field_id": dfield.pk, "link": "https://github.com/equipe/projeto"},
            {"field_id": ffield.pk, "file_index": 0},
        ],
        [pdf_upload(), pdf_upload("extra.pdf")],
    )
    assert response.status_code == 400
    assert error_code(response) == "validation_error"


@pytest.mark.parametrize(
    "item",
    [
        {"link": "https://a.dev", "file_index": 0},
        {},
    ],
)
def test_multipart_item_com_link_e_file_index_ou_nenhum_dos_dois_da_400(
    item, dproject, dleader, dstage, ffield
):
    response = post_multipart(
        dleader,
        dproject,
        dstage,
        [{"field_id": ffield.pk, **item}],
        [pdf_upload()],
    )
    assert response.status_code == 400
    assert error_code(response) == "validation_error"


@pytest.mark.parametrize("raw", ["isto nao e json", "{}", "123", "[1, 2]"])
def test_multipart_items_invalidos_da_400(raw, dproject, dleader, dstage, ffield):
    response = client_for(dleader).post(
        versions_url(dproject, dstage),
        {"items": raw, "files[]": pdf_upload()},
        format="multipart",
    )
    assert response.status_code == 400
    assert error_code(response) == "validation_error"


def test_json_com_file_index_da_400(dproject, dleader, dstage, ffield):
    response = post_version(
        dleader,
        dproject,
        dstage,
        {"items": [{"field_id": ffield.pk, "file_index": 0}]},
    )
    assert response.status_code == 400
    assert error_code(response) == "validation_error"


def test_multipart_de_quem_nao_e_lider_da_403_e_nao_grava(
    dproject, dstage, ffield, delivery_storage_root
):
    member = TeamMemberFactory(team=dproject.team).student.user
    response = post_multipart(
        member,
        dproject,
        dstage,
        [{"field_id": ffield.pk, "file_index": 0}],
        [pdf_upload()],
    )
    assert response.status_code == 403
    assert error_code(response) == "not_team_leader"
    assert stored_keys(delivery_storage_root) == []


def test_multipart_com_prazo_encerrado_da_409_e_nao_grava(
    dproject, dleader, delivery_storage_root
):
    stage = make_stage(dproject, start=-5, end=-1)
    field = StageSubmissionFieldFactory(stage=stage, kind=FieldKind.FILE)
    response = post_multipart(
        dleader,
        dproject,
        stage,
        [{"field_id": field.pk, "file_index": 0}],
        [pdf_upload()],
    )
    assert response.status_code == 409
    assert error_code(response) == "stage_deadline_closed"
    assert stored_keys(delivery_storage_root) == []


def test_multipart_com_armazenamento_fora_do_ar_da_503(
    dproject, dleader, dstage, ffield, delivery_storage_root, monkeypatch
):
    def broken(*args, **kwargs):
        raise OSError("disco cheio")

    monkeypatch.setattr(get_delivery_storage().__class__, "save", broken)

    response = post_multipart(
        dleader,
        dproject,
        dstage,
        [{"field_id": ffield.pk, "file_index": 0}],
        [pdf_upload()],
    )
    assert response.status_code == 503
    assert error_code(response) == "storage_unavailable"
    assert stored_keys(delivery_storage_root) == []


# Download do arquivo da entrega (#107)


def file_item_url(item_id):
    return f"/api/deliverable-items/{item_id}/file"


@pytest.fixture
def sent_file(dproject, dleader, dstage, ffield):
    """Envia um PDF e devolve o item do arquivo, como a API o mostra."""
    response = post_multipart(
        dleader,
        dproject,
        dstage,
        [{"field_id": ffield.pk, "file_index": 0}],
        [pdf_upload("Meu Relatório.pdf")],
    )
    assert response.status_code == 201, response.data
    return response.data["items"][0]


def test_file_url_do_item_e_a_rota_de_download(sent_file):
    assert sent_file["file_url"] == file_item_url(sent_file["id"])


def test_consulta_de_entregas_mostra_o_arquivo_sem_a_chave_do_armazenamento(
    dproject, dleader, sent_file
):
    response = client_for(dleader).get(deliverables_url(dproject))

    item = response.data[0]["versions"][0]["items"][0]
    assert item["file_url"] == file_item_url(sent_file["id"])
    assert item["file_name"] == "Meu_Relatório.pdf"
    assert "deliveries/" not in json.dumps(response.data)


def test_integrante_baixa_o_arquivo(dleader, sent_file):
    response = client_for(dleader).get(sent_file["file_url"])

    assert response.status_code == 200
    assert b"".join(response.streaming_content) == PDF_BYTES
    assert response["Content-Type"] == "application/pdf"
    assert "attachment" in response["Content-Disposition"]
    assert "Meu_Relat" in response["Content-Disposition"]
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Cache-Control"] == "private, no-store"


def test_professor_do_curso_e_admin_baixam_o_arquivo(dproject, sent_file):
    link = TeacherCourseFactory(course=dproject.challenge.course)
    admin = UserFactory(role=UserRole.ADMIN)
    for user in (link.teacher.user, admin):
        response = client_for(user).get(sent_file["file_url"])
        assert response.status_code == 200
        assert b"".join(response.streaming_content) == PDF_BYTES


def test_download_recusa_quem_nao_pode_ver_o_projeto(sent_file):
    outsiders = (StudentFactory().user, TeacherFactory().user)
    for user in outsiders:
        response = client_for(user).get(sent_file["file_url"])
        assert response.status_code == 403
        assert error_code(response) == "project_access_denied"


def test_download_recusa_perfil_sem_permissao(sent_file):
    reviewer = ExternalReviewerFactory().user
    assert client_for(reviewer).get(sent_file["file_url"]).status_code == 403


def test_download_exige_login(sent_file):
    response = APIClient().get(sent_file["file_url"])
    assert response.status_code == 401
    assert error_code(response) == "not_authenticated"


def test_download_de_item_inexistente_da_404(dleader):
    assert client_for(dleader).get(file_item_url(999999)).status_code == 404


def test_download_de_item_de_link_da_404(dproject, dleader, dstage, dfield):
    response = post_version(dleader, dproject, dstage, payload(dfield))
    link_item_id = response.data["items"][0]["id"]
    assert client_for(dleader).get(file_item_url(link_item_id)).status_code == 404


def test_download_com_arquivo_removido_do_armazenamento_da_404(
    dleader, sent_file, delivery_storage_root
):
    for path in delivery_storage_root.rglob("*.pdf"):
        path.unlink()
    response = client_for(dleader).get(sent_file["file_url"])
    assert response.status_code == 404
    assert "deliveries/" not in json.dumps(response.data)


# Canvas e SWOT preenchidos no sistema (RF31, UC34)


@pytest.fixture
def canvas_field(dstage):
    return StageSubmissionFieldFactory(stage=dstage, kind=FieldKind.CANVAS)


def content_payload(field, content, **extra):
    return {"items": [{"field_id": field.pk, "content": content}], **extra}


def test_lider_envia_o_canvas_e_a_consulta_devolve_o_conteudo(
    dproject, dleader, dstage, canvas_field
):
    response = post_version(
        dleader, dproject, dstage, content_payload(canvas_field, valid_canvas())
    )

    assert response.status_code == 201, response.data
    item = response.data["items"][0]
    assert item["type"] == "CANVAS"
    assert item["content"] == valid_canvas()
    assert item["link"] is None

    listed = client_for(dleader).get(deliverables_url(dproject))
    assert listed.data[0]["versions"][0]["items"][0]["content"] == valid_canvas()


def test_item_de_link_devolve_content_nulo(dproject, dleader, dstage, dfield):
    response = post_version(dleader, dproject, dstage, payload(dfield))

    assert response.data["items"][0]["content"] is None


def test_canvas_incompleto_responde_400(dproject, dleader, dstage, canvas_field):
    response = post_version(
        dleader,
        dproject,
        dstage,
        content_payload(canvas_field, {"channels": "só um bloco"}),
    )

    assert response.status_code == 400


def test_item_com_link_e_content_responde_400(dproject, dleader, dstage, canvas_field):
    body = {
        "items": [
            {
                "field_id": canvas_field.pk,
                "link": "https://github.com/equipe/projeto",
                "content": valid_canvas(),
            }
        ]
    }
    response = post_version(dleader, dproject, dstage, body)

    assert response.status_code == 400


def test_canvas_vai_tambem_no_multipart(dproject, dleader, dstage, canvas_field):
    response = post_multipart(
        dleader,
        dproject,
        dstage,
        [{"field_id": canvas_field.pk, "content": valid_canvas()}],
    )

    assert response.status_code == 201, response.data
    assert response.data["items"][0]["content"] == valid_canvas()


# Comprovante da versão (RF31)


def receipt_url(version):
    return f"/api/deliverable-versions/{version.pk}/receipt"


@pytest.fixture
def receipt(dproject, dstage):
    submission = SubmissionFactory(project=dproject, stage=dstage)
    version = SubmissionVersionFactory(submission=submission)
    return SubmissionReceiptFactory(version=version)


def test_lider_consulta_o_comprovante(receipt, dproject, dstage, dleader):
    response = client_for(dleader).get(receipt_url(receipt.version))

    assert response.status_code == 200
    assert response.data["id"] == receipt.pk
    assert response.data["version_id"] == receipt.version_id
    assert response.data["number"] == receipt.version.number
    assert response.data["verification_code"] == receipt.verification_code
    assert response.data["file_url"] is None
    assert response.data["generated_at"] is not None
    assert response.data["team"] == {
        "id": dproject.team.pk,
        "name": dproject.team.name,
        "code": dproject.team.code,
    }
    assert response.data["project"] == {"id": dproject.pk, "title": dproject.title}
    assert response.data["stage"] == {
        "id": dstage.pk,
        "name": dstage.name,
        "order": dstage.order,
    }
    assert response.data["submitted_at"] is not None


def test_integrante_e_admin_consultam_o_comprovante(receipt, dproject):
    member = TeamMemberFactory(team=dproject.team).student.user
    for user in (member, UserFactory(role=UserRole.ADMIN)):
        assert client_for(user).get(receipt_url(receipt.version)).status_code == 200


def test_comprovante_traz_o_mesmo_codigo_do_envio(dproject, dleader, dstage, dfield):
    created = post_version(dleader, dproject, dstage, payload(dfield))

    response = client_for(dleader).get(
        f"/api/deliverable-versions/{created.data['id']}/receipt"
    )

    assert response.status_code == 200
    assert (
        response.data["verification_code"]
        == created.data["receipt"]["verification_code"]
    )


def test_consulta_do_comprovante_exige_login(receipt):
    response = APIClient().get(receipt_url(receipt.version))
    assert response.status_code == 401
    assert error_code(response) == "not_authenticated"


def test_aluno_de_fora_nao_consulta_o_comprovante(receipt):
    response = client_for(StudentFactory().user).get(receipt_url(receipt.version))

    assert response.status_code == 403
    assert error_code(response) == "project_access_denied"


def test_professor_e_avaliador_externo_nao_consultam_o_comprovante(receipt):
    for user in (TeacherFactory().user, ExternalReviewerFactory().user):
        response = client_for(user).get(receipt_url(receipt.version))
        assert response.status_code == 403
        assert error_code(response) == "permission_denied"


def test_comprovante_inexistente_da_404(dleader):
    response = client_for(dleader).get("/api/deliverable-versions/999999/receipt")
    assert response.status_code == 404


def test_versao_sem_comprovante_da_404(dleader, dproject, dstage):
    version = SubmissionVersionFactory(
        submission=SubmissionFactory(project=dproject, stage=dstage)
    )
    assert client_for(dleader).get(receipt_url(version)).status_code == 404


def test_comprovante_continua_visivel_com_equipe_desclassificada():
    project = ProjectFactory(team=TeamFactory(disqualified=True))
    leader = project.team.members.get(role=MemberRole.LEADER).student.user
    stage = make_stage(project)
    version = SubmissionVersionFactory(
        submission=SubmissionFactory(project=project, stage=stage)
    )
    SubmissionReceiptFactory(version=version)
    assert client_for(leader).get(receipt_url(version)).status_code == 200


def test_comprovante_continua_visivel_depois_do_prazo(dproject, dleader):
    stage = make_stage(dproject, start=-3, end=-1)
    version = SubmissionVersionFactory(
        submission=SubmissionFactory(project=dproject, stage=stage)
    )
    SubmissionReceiptFactory(version=version)
    assert client_for(dleader).get(receipt_url(version)).status_code == 200


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_comprovante_nao_aceita_escrita(receipt, dleader, method):
    response = getattr(client_for(dleader), method)(receipt_url(receipt.version))
    assert response.status_code == 405


# --- prorrogação de prazo da equipe (RF14) ---


def extension_url(team):
    return f"/api/admin/teams/{team.pk}/deadline-extensions"


@pytest.fixture
def admin():
    return UserFactory(role=UserRole.ADMIN)


@pytest.fixture
def extension_ctx():
    project = ProjectFactory()
    now = timezone.now()
    stage = StageFactory(
        edition=project.edition,
        starts_at=now - timedelta(days=5),
        ends_at=now - timedelta(days=1),
    )
    body = {
        "stage_id": stage.pk,
        "ends_at": (stage.ends_at + timedelta(days=3)).isoformat(),
        "reason": "Atestado médico do líder.",
    }
    return project, stage, body


def test_prorrogacao_201_como_admin(admin, extension_ctx):
    project, stage, body = extension_ctx

    response = client_for(admin).post(extension_url(project.team), body, format="json")

    assert response.status_code == 201
    saved = DeadlineExtension.objects.get()
    assert response.json() == {
        "id": saved.pk,
        "team_id": project.team_id,
        "project_id": project.pk,
        "stage_id": stage.pk,
        "ends_at": response.json()["ends_at"],
        "reason": "Atestado médico do líder.",
        "granted_by": admin.pk,
        "granted_at": response.json()["granted_at"],
    }
    assert saved.granted_by == admin


def test_prorrogacao_exige_login(extension_ctx):
    project, _, body = extension_ctx
    response = APIClient().post(extension_url(project.team), body, format="json")
    assert response.status_code == 401


@pytest.mark.parametrize(
    "papel",
    [StudentFactory, TeacherFactory, ExternalReviewerFactory],
)
def test_prorrogacao_barra_quem_nao_e_admin(papel, extension_ctx):
    project, _, body = extension_ctx
    response = client_for(papel().user).post(
        extension_url(project.team), body, format="json"
    )
    assert response.status_code == 403
    assert DeadlineExtension.objects.count() == 0


def test_prorrogacao_404_equipe_inexistente(admin, extension_ctx):
    _, _, body = extension_ctx
    response = client_for(admin).post(
        "/api/admin/teams/999999/deadline-extensions", body, format="json"
    )
    assert response.status_code == 404


def test_prorrogacao_404_equipe_sem_projeto(admin, extension_ctx):
    _, _, body = extension_ctx
    response = client_for(admin).post(extension_url(TeamFactory()), body, format="json")
    assert response.status_code == 404
    assert DeadlineExtension.objects.count() == 0


def test_prorrogacao_404_etapa_inexistente(admin, extension_ctx):
    project, _, body = extension_ctx
    response = client_for(admin).post(
        extension_url(project.team), {**body, "stage_id": 999999}, format="json"
    )
    assert response.status_code == 404


@pytest.mark.parametrize(
    "mudanca",
    [
        {"ends_at": "ANTES"},
        {"ends_at": "IGUAL"},
        {"stage_id": "OUTRA_EDICAO"},
        {"reason": ""},
        {"reason": "   "},
        {"reason": None},
        {"ends_at": None},
    ],
)
def test_prorrogacao_400_corpo_ou_regra_invalida(admin, extension_ctx, mudanca):
    project, stage, body = extension_ctx
    valores = {
        "ANTES": (stage.ends_at - timedelta(hours=1)).isoformat(),
        "IGUAL": stage.ends_at.isoformat(),
        "OUTRA_EDICAO": StageFactory().pk,
    }
    corpo = {
        **body,
        **{
            k: valores.get(v, v) if isinstance(v, str) else v
            for k, v in mudanca.items()
        },
    }

    response = client_for(admin).post(extension_url(project.team), corpo, format="json")

    assert response.status_code == 400
    assert DeadlineExtension.objects.count() == 0


def test_prorrogacao_400_sem_campo_obrigatorio(admin, extension_ctx):
    project, _, body = extension_ctx
    body.pop("reason")
    response = client_for(admin).post(extension_url(project.team), body, format="json")
    assert response.status_code == 400


def test_prorrogacao_409_na_segunda_chamada(admin, extension_ctx):
    project, _, body = extension_ctx
    client = client_for(admin)
    client.post(extension_url(project.team), body, format="json")

    response = client.post(extension_url(project.team), body, format="json")

    assert response.status_code == 409
    assert error_code(response) == "deadline_extension_already_granted"
    assert DeadlineExtension.objects.count() == 1


def test_prorrogacao_409_edicao_encerrada(admin, extension_ctx):
    project, _, body = extension_ctx
    project.edition.status = EditionStatus.CLOSED
    project.edition.save()

    response = client_for(admin).post(extension_url(project.team), body, format="json")

    assert response.status_code == 409
    assert error_code(response) == "edition_closed"


def test_prorrogacao_ignora_campos_de_auditoria_no_corpo(admin, extension_ctx):
    project, _, body = extension_ctx
    outro_projeto = ProjectFactory()
    corpo = {
        **body,
        "granted_by": UserFactory(role=UserRole.ADMIN).pk,
        "granted_at": "2020-01-01T00:00:00Z",
        "project_id": outro_projeto.pk,
    }

    response = client_for(admin).post(extension_url(project.team), corpo, format="json")

    assert response.status_code == 201
    saved = DeadlineExtension.objects.get()
    assert saved.granted_by == admin
    assert saved.project == project
    assert saved.granted_at.year != 2020


@pytest.mark.parametrize("metodo", ["get", "put", "patch", "delete"])
def test_prorrogacao_so_aceita_post(admin, extension_ctx, metodo):
    project, _, _ = extension_ctx
    DeadlineExtensionFactory(project=project)
    response = getattr(client_for(admin), metodo)(extension_url(project.team))
    assert response.status_code == 405
