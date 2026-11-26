"""Testes de API e contrato para os endpoints de cursos (Issue #185)."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.factories import StudentFactory, TeacherFactory, UserFactory
from apps.core.factories import CourseFactory
from apps.core.models import Course
from apps.core.tests.contract import mismatches, schema
from apps.editions.factories import ChallengeFactory

pytestmark = pytest.mark.django_db


def auth_client(user=None) -> APIClient:
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    return client


@pytest.fixture
def admin():
    # Papel ADMIN sem depender de is_staff do Django
    return UserFactory(role=UserRole.ADMIN, is_staff=False)


# Autenticação (401) e autorização (403)


def test_rotas_admin_sem_login_retornam_401_not_authenticated():
    course = CourseFactory()
    client = auth_client()

    responses = [
        client.get("/api/admin/courses"),
        client.post(
            "/api/admin/courses",
            {"name": "Engenharia", "term_count": 8},
            format="json",
        ),
        client.patch(
            f"/api/admin/courses/{course.id}",
            {"active": False},
            format="json",
        ),
        client.delete(f"/api/admin/courses/{course.id}"),
    ]

    for resp in responses:
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "not_authenticated"
        assert mismatches(resp.json(), schema("Error")) == []


@pytest.mark.parametrize("role", [UserRole.STUDENT, UserRole.TEACHER])
def test_rotas_admin_com_papel_errado_retornam_403(role):
    user = UserFactory(role=role)
    course = CourseFactory()
    client = auth_client(user)

    responses = [
        client.get("/api/admin/courses"),
        client.post(
            "/api/admin/courses",
            {"name": "Engenharia", "term_count": 8},
            format="json",
        ),
        client.patch(
            f"/api/admin/courses/{course.id}",
            {"active": False},
            format="json",
        ),
        client.delete(f"/api/admin/courses/{course.id}"),
    ]

    for resp in responses:
        assert resp.status_code == 403
        assert mismatches(resp.json(), schema("Error")) == []


# GET /api/courses (público)


def test_public_list_courses_segue_contrato():
    Course.objects.all().delete()
    active_course = CourseFactory(name="Engenharia de Software", active=True)
    CourseFactory(name="Curso Inativo", active=False)

    resp = auth_client().get("/api/courses")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == active_course.id
    assert mismatches(data[0], schema("CourseSummary")) == []


# GET /api/admin/courses (filtros + contrato)


def test_admin_list_courses_filtros_e_contrato(admin):
    Course.objects.all().delete()
    eng = CourseFactory(name="Engenharia de Software", term_count=8, active=True)
    CourseFactory(name="Engenharia Civil", term_count=10, active=False)
    CourseFactory(name="Direito", term_count=10, active=True)

    client = auth_client(admin)
    resp = client.get("/api/admin/courses?search=Engenharia&active=true")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == eng.id
    assert mismatches(data[0], schema("Course")) == []

    resp_inactive = client.get("/api/admin/courses?active=false")
    assert resp_inactive.status_code == 200
    assert len(resp_inactive.json()) == 1
    assert resp_inactive.json()[0]["active"] is False


# POST /api/admin/courses


def test_admin_create_course_aceita_active_e_segue_contrato(admin):
    client = auth_client(admin)

    resp = client.post(
        "/api/admin/courses",
        {"name": "Sistemas de Informação", "term_count": 8, "active": False},
        format="json",
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["active"] is False
    assert mismatches(data, schema("Course")) == []


def test_admin_create_course_nome_duplicado_retorna_409(admin):
    CourseFactory(name="Curso Duplicado Teste")
    client = auth_client(admin)

    resp = client.post(
        "/api/admin/courses",
        {"name": "curso duplicado teste", "term_count": 10},
        format="json",
    )

    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "course_name_taken"
    assert mismatches(resp.json(), schema("Error")) == []


# PATCH /api/admin/courses/{course_id}


def test_admin_update_course_segue_contrato(admin):
    course = CourseFactory(name="Curso Original Teste", term_count=10, active=True)
    client = auth_client(admin)

    resp = client.patch(
        f"/api/admin/courses/{course.id}",
        {"name": "Curso Atualizado Teste", "term_count": 8, "active": False},
        format="json",
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Curso Atualizado Teste"
    assert data["term_count"] == 8
    assert data["active"] is False
    assert mismatches(data, schema("Course")) == []


def test_admin_update_course_recusa_reduzir_term_count_abaixo_de_aluno(admin):
    course = CourseFactory(term_count=10)
    StudentFactory(course=course, term=9)
    client = auth_client(admin)

    resp = client.patch(
        f"/api/admin/courses/{course.id}",
        {"term_count": 8},
        format="json",
    )

    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "validation_error"
    assert "term_count" in body["error"]["details"]


def test_admin_update_course_nome_duplicado_retorna_409(admin):
    CourseFactory(name="Curso A Teste")
    course = CourseFactory(name="Curso B Teste")
    client = auth_client(admin)

    resp = client.patch(
        f"/api/admin/courses/{course.id}",
        {"name": "curso a teste"},
        format="json",
    )

    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "course_name_taken"
    assert mismatches(resp.json(), schema("Error")) == []


def test_admin_update_e_delete_curso_inexistente_retornam_404_no_padrao(admin):
    client = auth_client(admin)

    patch_resp = client.patch(
        "/api/admin/courses/999999",
        {"active": False},
        format="json",
    )
    delete_resp = client.delete("/api/admin/courses/999999")

    for resp in (patch_resp, delete_resp):
        assert resp.status_code == 404
        assert mismatches(resp.json(), schema("Error")) == []


# DELETE /api/admin/courses/{course_id}


def test_admin_delete_course_sem_vinculos_retorna_204(admin):
    course = CourseFactory()
    client = auth_client(admin)

    resp = client.delete(f"/api/admin/courses/{course.id}")

    assert resp.status_code == 204
    assert not Course.objects.filter(pk=course.pk).exists()


@pytest.mark.parametrize("link_type", ["student", "teacher", "challenge"])
def test_admin_delete_course_com_vinculo_retorna_409_course_in_use(admin, link_type):
    course = CourseFactory()
    if link_type == "student":
        StudentFactory(course=course)
    elif link_type == "teacher":
        teacher = TeacherFactory()
        teacher.courses.add(course)
    else:
        ChallengeFactory(course=course)

    client = auth_client(admin)
    resp = client.delete(f"/api/admin/courses/{course.id}")

    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "course_in_use"
    assert mismatches(resp.json(), schema("Error")) == []
    assert Course.objects.filter(pk=course.pk).exists()
