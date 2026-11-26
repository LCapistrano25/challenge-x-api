import pytest
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.factories import (
    ExternalReviewerFactory,
    StudentFactory,
    TeacherCourseFactory,
    TeacherFactory,
    UserFactory,
)
from apps.accounts.models import TeacherCourse
from apps.core.factories import CourseFactory
from apps.core.tests.contract import mismatches, schema
from apps.editions.factories import EditionReviewerFactory

pytestmark = pytest.mark.django_db

KINDS = {
    "students": (StudentFactory, "StudentAdmin"),
    "teachers": (TeacherFactory, "TeacherAdmin"),
    "external-evaluators": (ExternalReviewerFactory, "ExternalEvaluatorAdmin"),
}


def client_for(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    return client


@pytest.fixture
def admin_client():
    return client_for(UserFactory(role=UserRole.ADMIN))


def routes(plural, user_id):
    return [
        ("get", f"/api/admin/{plural}"),
        ("get", f"/api/admin/{plural}/{user_id}"),
        ("patch", f"/api/admin/{plural}/{user_id}"),
        ("patch", f"/api/admin/{plural}/{user_id}/status"),
    ]


@pytest.mark.parametrize("plural", KINDS)
def test_sem_login_recebe_401(plural):
    for method, url in routes(plural, 1):
        assert getattr(client_for(), method)(url, {}, format="json").status_code == 401


@pytest.mark.parametrize("plural", KINDS)
@pytest.mark.parametrize(
    "factory", [StudentFactory, TeacherFactory, ExternalReviewerFactory]
)
def test_papel_diferente_de_admin_recebe_403(plural, factory):
    client = client_for(factory().user)
    for method, url in routes(plural, 1):
        assert getattr(client, method)(url, {}, format="json").status_code == 403


@pytest.mark.parametrize("plural", KINDS)
def test_lista_e_consulta_conformes_ao_contrato(admin_client, plural):
    factory, schema_name = KINDS[plural]
    profile = factory()
    if plural == "teachers":
        TeacherCourseFactory(teacher=profile)
    if plural == "external-evaluators":
        EditionReviewerFactory(reviewer=profile)

    listing = admin_client.get(f"/api/admin/{plural}")
    assert listing.status_code == 200
    assert mismatches(listing.data, schema(f"Paginated{schema_name}")) == []
    assert [item["user_id"] for item in listing.data["results"]] == [profile.pk]

    detail = admin_client.get(f"/api/admin/{plural}/{profile.pk}")
    assert detail.status_code == 200
    assert mismatches(detail.data, schema(schema_name)) == []


@pytest.mark.parametrize("plural", KINDS)
def test_usuario_de_outro_perfil_ou_inexistente_retorna_404(admin_client, plural):
    other = {
        "students": TeacherFactory,
        "teachers": ExternalReviewerFactory,
        "external-evaluators": StudentFactory,
    }[plural]().pk
    admin = UserFactory(role=UserRole.ADMIN).pk
    for user_id in (other, admin, 999999):
        for method, url in routes(plural, user_id)[1:]:
            body = {"active": False} if url.endswith("status") else {"name": "X"}
            response = getattr(admin_client, method)(url, body, format="json")
            assert response.status_code == 404, url
            assert response.data["error"]["code"] == "not_found"


@pytest.mark.parametrize("plural", KINDS)
def test_busca_e_filtro_de_ativos(admin_client, plural):
    factory, _ = KINDS[plural]
    maria = factory(user__name="Maria Souza")
    joao = factory(user__name="João Lima", user__is_active=False)

    def ids(query):
        response = admin_client.get(f"/api/admin/{plural}?{query}")
        assert response.status_code == 200
        return [item["user_id"] for item in response.data["results"]]

    assert ids("") == [joao.pk, maria.pk]
    assert ids("search=souza") == [maria.pk]
    assert ids(f"search={joao.user.email}") == [joao.pk]
    assert ids("active=false") == [joao.pk]
    assert ids("active=true") == [maria.pk]


def test_busca_de_alunos_cobre_matricula(admin_client):
    student = StudentFactory(registration_number="202699999")
    StudentFactory()
    response = admin_client.get("/api/admin/students?search=2026999")
    assert [item["user_id"] for item in response.data["results"]] == [student.pk]


def test_filtro_por_curso_de_alunos_e_professores(admin_client):
    course = CourseFactory()
    student = StudentFactory(course=course)
    StudentFactory()
    teacher = TeacherCourseFactory(course=course).teacher
    TeacherCourseFactory(course=course, active=False)
    TeacherCourseFactory()

    students = admin_client.get(f"/api/admin/students?course_id={course.pk}")
    assert [item["user_id"] for item in students.data["results"]] == [student.pk]
    teachers = admin_client.get(f"/api/admin/teachers?course_id={course.pk}")
    assert [item["user_id"] for item in teachers.data["results"]] == [teacher.pk]


def test_lista_e_paginada(admin_client):
    StudentFactory.create_batch(3)
    response = admin_client.get("/api/admin/students?page_size=2&page=2")
    assert response.status_code == 200
    assert response.data["count"] == 3
    assert len(response.data["results"]) == 1
    assert response.data["previous"] is not None


@pytest.mark.parametrize("plural", KINDS)
def test_patch_sem_campos_retorna_400(admin_client, plural):
    profile = KINDS[plural][0]()
    response = admin_client.patch(f"/api/admin/{plural}/{profile.pk}", {})
    assert response.status_code == 400


def test_admin_atualiza_aluno(admin_client):
    student = StudentFactory(term=2)
    course = CourseFactory(term_count=10)
    email = student.user.email

    response = admin_client.patch(
        f"/api/admin/students/{student.pk}",
        {
            "name": "Maria Souza Lima",
            "registration_number": "202600124",
            "course_id": course.pk,
            "term": 9,
        },
        format="json",
    )

    assert response.status_code == 200
    assert mismatches(response.data, schema("StudentAdmin")) == []
    assert response.data["name"] == "Maria Souza Lima"
    assert response.data["registration_number"] == "202600124"
    assert response.data["course"]["id"] == course.pk
    assert response.data["term"] == 9
    assert response.data["email"] == email


def test_matricula_repetida_retorna_409(admin_client):
    other = StudentFactory()
    student = StudentFactory()
    response = admin_client.patch(
        f"/api/admin/students/{student.pk}",
        {"registration_number": other.registration_number},
        format="json",
    )
    assert response.status_code == 409
    assert response.data["error"]["code"] == "registration_number_taken"


def test_manter_a_propria_matricula_nao_conflita(admin_client):
    student = StudentFactory()
    response = admin_client.patch(
        f"/api/admin/students/{student.pk}",
        {"registration_number": student.registration_number},
        format="json",
    )
    assert response.status_code == 200


def test_periodo_fora_do_curso_retorna_400(admin_client):
    student = StudentFactory(course=CourseFactory(term_count=8))
    response = admin_client.patch(
        f"/api/admin/students/{student.pk}", {"term": 9}, format="json"
    )
    assert response.status_code == 400
    assert "term" in response.data["error"]["details"]


def test_novo_curso_valida_o_periodo_atual(admin_client):
    student = StudentFactory(term=9, course=CourseFactory(term_count=10))
    response = admin_client.patch(
        f"/api/admin/students/{student.pk}",
        {"course_id": CourseFactory(term_count=8).pk},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.parametrize("active", [False, None])
def test_curso_inexistente_ou_inativo_retorna_400(admin_client, active):
    student = StudentFactory()
    course_id = CourseFactory(active=False).pk if active is False else 999999
    response = admin_client.patch(
        f"/api/admin/students/{student.pk}", {"course_id": course_id}, format="json"
    )
    assert response.status_code == 400
    assert "course_id" in response.data["error"]["details"]


def test_admin_atualiza_nome_e_vinculos_do_professor(admin_client):
    kept = TeacherCourseFactory()
    teacher = kept.teacher
    changed = TeacherCourseFactory(teacher=teacher)
    new_course = CourseFactory()

    response = admin_client.patch(
        f"/api/admin/teachers/{teacher.pk}",
        {
            "name": "João Pereira",
            "courses": [
                {"course_id": changed.course_id, "active": False},
                {"course_id": new_course.pk, "active": True},
            ],
        },
        format="json",
    )

    assert response.status_code == 200
    assert mismatches(response.data, schema("TeacherAdmin")) == []
    assert response.data["name"] == "João Pereira"
    links = dict(
        TeacherCourse.objects.filter(teacher=teacher).values_list("course_id", "active")
    )
    assert links == {
        kept.course_id: True,
        changed.course_id: False,
        new_course.pk: True,
    }


def test_professor_com_curso_inexistente_retorna_400(admin_client):
    teacher = TeacherFactory()
    response = admin_client.patch(
        f"/api/admin/teachers/{teacher.pk}",
        {"courses": [{"course_id": 999999, "active": True}]},
        format="json",
    )
    assert response.status_code == 400
    assert not TeacherCourse.objects.filter(teacher=teacher).exists()


def test_professor_com_curso_repetido_retorna_400(admin_client):
    teacher = TeacherFactory()
    course = CourseFactory()
    response = admin_client.patch(
        f"/api/admin/teachers/{teacher.pk}",
        {
            "courses": [
                {"course_id": course.pk, "active": True},
                {"course_id": course.pk, "active": False},
            ]
        },
        format="json",
    )
    assert response.status_code == 400


def test_admin_atualiza_avaliador_e_limpa_instituicao(admin_client):
    reviewer = ExternalReviewerFactory(institution="Antiga")

    response = admin_client.patch(
        f"/api/admin/external-evaluators/{reviewer.pk}",
        {"name": "Ana Ribeiro", "institution": None},
        format="json",
    )

    assert response.status_code == 200
    assert mismatches(response.data, schema("ExternalEvaluatorAdmin")) == []
    assert response.data["name"] == "Ana Ribeiro"
    assert response.data["institution"] is None


@pytest.mark.parametrize("plural", KINDS)
def test_admin_desativa_e_reativa_usuario(admin_client, plural):
    profile = KINDS[plural][0]()
    url = f"/api/admin/{plural}/{profile.pk}/status"

    response = admin_client.patch(url, {"active": False}, format="json")
    assert response.status_code == 200
    assert mismatches(response.data, schema("UserStatus")) == []
    assert response.data == {"user_id": profile.pk, "active": False}
    profile.user.refresh_from_db()
    assert profile.user.is_active is False

    response = admin_client.patch(url, {"active": True}, format="json")
    assert response.data["active"] is True


def test_status_exige_o_campo_active(admin_client):
    student = StudentFactory()
    response = admin_client.patch(
        f"/api/admin/students/{student.pk}/status", {}, format="json"
    )
    assert response.status_code == 400


def test_desativar_derruba_a_sessao_aberta(admin_client):
    student = StudentFactory()
    session = APIClient()
    session.force_login(student.user)
    assert session.get("/api/auth/me").status_code == 200

    admin_client.patch(
        f"/api/admin/students/{student.pk}/status", {"active": False}, format="json"
    )

    assert session.get("/api/auth/me").status_code == 401
