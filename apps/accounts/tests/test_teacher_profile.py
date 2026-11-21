import pytest
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import (
    DomainRoleMismatch,
    NotTeacherActor,
    RegistrationRejected,
    TeacherProfileExists,
)
from apps.accounts.factories import (
    EmailDomainFactory,
    StudentFactory,
    TeacherFactory,
    UserFactory,
)
from apps.accounts.models import Teacher, TeacherCourse
from apps.accounts.use_cases.register_teacher import register_teacher
from apps.core.factories import CourseFactory

# Perfil do professor no primeiro acesso (UC10, RF10, RF36.1, P-04)


@pytest.fixture
def actor(db):
    EmailDomainFactory(name="p.edu.br", role=UserRole.TEACHER)
    return UserFactory(email="bia@p.edu.br", role=UserRole.TEACHER)


@pytest.fixture
def courses(db):
    return CourseFactory.create_batch(2)


def test_cria_o_perfil_com_os_vinculos_ativos(actor, courses):
    teacher = register_teacher(actor=actor, course_ids=[c.pk for c in courses])

    assert teacher.user == actor
    assert set(teacher.course_links.values_list("course", "active")) == {
        (courses[0].pk, True),
        (courses[1].pk, True),
    }


def test_recusa_quem_nao_e_professor(actor, courses):
    actor.role = UserRole.STUDENT
    actor.save()

    with pytest.raises(NotTeacherActor):
        register_teacher(actor=actor, course_ids=[courses[0].pk])


def test_recusa_email_fora_do_dominio_de_professor(courses, db):
    actor = UserFactory(email="bia@gmail.com", role=UserRole.TEACHER)
    EmailDomainFactory(name="gmail.com", role=UserRole.STUDENT)

    with pytest.raises(DomainRoleMismatch):
        register_teacher(actor=actor, course_ids=[courses[0].pk])


def test_escolha_e_unica(actor, courses):
    register_teacher(actor=actor, course_ids=[courses[0].pk])

    # Depois do primeiro acesso, só o admin altera os cursos (P-04).
    with pytest.raises(TeacherProfileExists):
        register_teacher(actor=actor, course_ids=[courses[1].pk])
    assert TeacherCourse.objects.count() == 1


@pytest.mark.parametrize("problem", ["inativo", "inexistente", "vazio"])
def test_recusa_curso_invalido_sem_criar_nada(actor, courses, problem):
    course_ids = [courses[0].pk]
    if problem == "inativo":
        courses[1].active = False
        courses[1].save()
        course_ids.append(courses[1].pk)
    elif problem == "inexistente":
        course_ids.append(999_999)
    else:
        course_ids = []

    with pytest.raises(RegistrationRejected, match="Curso inválido."):
        register_teacher(actor=actor, course_ids=course_ids)
    assert not Teacher.objects.exists()


def test_configuracao_simultanea_vira_conflito(actor, courses, monkeypatch):
    TeacherFactory(user=actor)

    class NothingFound:
        def exists(self):
            return False

    # Simula a corrida: a checagem não vê o outro perfil; o banco desempata.
    monkeypatch.setattr(Teacher.objects, "filter", lambda **kwargs: NothingFound())
    with pytest.raises(TeacherProfileExists):
        register_teacher(actor=actor, course_ids=[courses[0].pk])


# POST /api/auth/teachers

URL = "/api/auth/teachers"


def post(user, body):
    client = APIClient()
    client.force_authenticate(user)
    return client.post(URL, body, format="json")


def test_professor_sem_perfil_configura_os_cursos(actor, courses):
    resposta = post(actor, {"course_ids": [c.pk for c in courses]})

    assert resposta.status_code == 201
    assert resposta.data == {"teacher": {"user_id": actor.pk}}


def test_professor_com_perfil_recebe_409(actor, courses):
    TeacherFactory(user=actor)

    resposta = post(actor, {"course_ids": [courses[0].pk]})

    assert resposta.status_code == 409
    assert resposta.data["error"]["code"] == "teacher_profile_exists"


@pytest.mark.parametrize("course_ids", [[], "1", ["x"]])
def test_corpo_invalido_recebe_400(actor, course_ids):
    resposta = post(actor, {"course_ids": course_ids})

    assert resposta.status_code == 400


def test_curso_repetido_recebe_400(actor, courses):
    resposta = post(actor, {"course_ids": [courses[0].pk, courses[0].pk]})

    assert resposta.status_code == 400
    assert not Teacher.objects.exists()


@pytest.mark.django_db
def test_aluno_nao_configura_perfil_de_professor():
    resposta = post(StudentFactory().user, {"course_ids": [1]})

    assert resposta.status_code == 403


@pytest.mark.django_db
def test_exige_login():
    resposta = APIClient().post(URL, {"course_ids": [1]}, format="json")

    assert resposta.status_code == 401
