import pytest
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.factories import ExternalReviewerFactory, TeacherFactory, UserFactory
from apps.core.factories import CourseFactory
from apps.editions.enums import EditionStatus
from apps.editions.factories import EditionFactory
from apps.editions.models import EditionReviewer

pytestmark = pytest.mark.django_db

# GET /api/admin/editions/{edition_id}/evaluators: avaliadores da edição (RF11)


def url(edition_id):
    return f"/api/admin/editions/{edition_id}/evaluators"


def get(user, edition_id):
    client = APIClient()
    if user:
        client.force_authenticate(user)
    return client.get(url(edition_id))


@pytest.fixture
def admin():
    return UserFactory(role=UserRole.ADMIN)


def test_lista_os_avaliadores_da_edicao_no_formato_do_contrato(admin):
    edition = EditionFactory()
    reviewer = ExternalReviewerFactory(institution="Empresa Parceira")
    course = CourseFactory()
    link = EditionReviewer.objects.create(
        edition=edition, reviewer=reviewer, course=course
    )

    resposta = get(admin, edition.pk)

    assert resposta.status_code == 200
    assert resposta.data == [
        {
            "id": link.pk,
            "edition_id": edition.pk,
            "evaluator": {
                "user_id": reviewer.user.pk,
                "name": reviewer.user.name,
                "email": reviewer.user.email,
                "institution": "Empresa Parceira",
            },
            "course": {"id": course.pk, "name": course.name},
            "created_at": resposta.data[0]["created_at"],
            "updated_at": resposta.data[0]["updated_at"],
        }
    ]


def test_avaliador_de_todos_os_cursos_tem_course_nulo(admin):
    edition = EditionFactory()
    EditionReviewer.objects.create(edition=edition, reviewer=ExternalReviewerFactory())

    resposta = get(admin, edition.pk)

    assert resposta.data[0]["course"] is None


def test_nao_mostra_avaliadores_de_outra_edicao(admin):
    edition = EditionFactory()
    EditionReviewer.objects.create(
        edition=EditionFactory(), reviewer=ExternalReviewerFactory()
    )

    resposta = get(admin, edition.pk)

    assert resposta.status_code == 200
    assert resposta.data == []


def test_edicao_inexistente_recebe_404(admin):
    resposta = get(admin, 999999)

    assert resposta.status_code == 404
    assert resposta.data["error"]["code"] == "not_found"


def test_sem_login_e_recusado():
    resposta = get(None, EditionFactory().pk)

    assert resposta.status_code == 403
    assert resposta.data["error"]["code"] == "not_authenticated"


def test_so_admin_lista_os_avaliadores():
    resposta = get(TeacherFactory().user, EditionFactory().pk)

    assert resposta.status_code == 403
    assert resposta.data["error"]["code"] == "permission_denied"


def test_numero_de_consultas_nao_cresce_com_os_avaliadores(
    admin, django_assert_max_num_queries
):
    edition = EditionFactory()
    for _ in range(5):
        EditionReviewer.objects.create(
            edition=edition, reviewer=ExternalReviewerFactory(), course=CourseFactory()
        )

    # Sessão do admin, edição (404) e a listagem: não uma consulta por avaliador.
    with django_assert_max_num_queries(5):
        resposta = get(admin, edition.pk)

    assert len(resposta.data) == 5


# POST e PATCH: vincular avaliador e alterar a abrangência (RF11)


def send(user, method, path, data):
    client = APIClient()
    if user:
        client.force_authenticate(user)
    return getattr(client, method)(path, data, format="json")


def link_url(link):
    return f"{url(link.edition_id)}/{link.reviewer_id}"


def test_admin_vincula_avaliador(admin):
    edition = EditionFactory()
    reviewer = ExternalReviewerFactory()
    data = {"evaluator_id": reviewer.pk, "course_id": None}

    resposta = send(admin, "post", url(edition.pk), data)

    assert resposta.status_code == 201
    assert resposta.data["evaluator"]["user_id"] == reviewer.pk
    assert resposta.data["course"] is None


def test_vinculo_repetido_recebe_409(admin):
    edition = EditionFactory()
    reviewer = ExternalReviewerFactory()
    EditionReviewer.objects.create(edition=edition, reviewer=reviewer)
    data = {"evaluator_id": reviewer.pk, "course_id": None}

    resposta = send(admin, "post", url(edition.pk), data)

    assert resposta.status_code == 409
    assert resposta.data["error"]["code"] == "evaluator_already_linked"


def test_vinculo_em_edicao_encerrada_recebe_409(admin):
    edition = EditionFactory(status=EditionStatus.CLOSED)
    data = {"evaluator_id": ExternalReviewerFactory().pk, "course_id": None}

    resposta = send(admin, "post", url(edition.pk), data)

    assert resposta.status_code == 409
    assert resposta.data["error"]["code"] == "edition_closed"


def test_vinculo_sem_course_id_e_recusado(admin):
    # O contrato exige o campo: é o null que significa todos os cursos.
    data = {"evaluator_id": ExternalReviewerFactory().pk}

    resposta = send(admin, "post", url(EditionFactory().pk), data)

    assert resposta.status_code == 400
    assert set(resposta.data["error"]["details"]) == {"course_id"}


def test_vinculo_em_edicao_inexistente_recebe_404(admin):
    resposta = send(admin, "post", url(999999), {"evaluator_id": 1, "course_id": None})

    assert resposta.status_code == 404


def test_so_admin_vincula_avaliador():
    data = {"evaluator_id": 1, "course_id": None}

    resposta = send(TeacherFactory().user, "post", url(EditionFactory().pk), data)

    assert resposta.status_code == 403


def test_admin_altera_a_abrangencia(admin):
    link = EditionReviewer.objects.create(
        edition=EditionFactory(), reviewer=ExternalReviewerFactory()
    )
    course = CourseFactory()

    resposta = send(admin, "patch", link_url(link), {"course_id": course.pk})

    assert resposta.status_code == 200
    assert resposta.data["course"] == {"id": course.pk, "name": course.name}


def test_alterar_vinculo_inexistente_recebe_404(admin):
    edition = EditionFactory()
    path = f"{url(edition.pk)}/{ExternalReviewerFactory().pk}"

    resposta = send(admin, "patch", path, {"course_id": None})

    assert resposta.status_code == 404
    assert resposta.data["error"]["code"] == "not_found"


def test_so_admin_altera_a_abrangencia():
    link = EditionReviewer.objects.create(
        edition=EditionFactory(), reviewer=ExternalReviewerFactory()
    )

    resposta = send(TeacherFactory().user, "patch", link_url(link), {"course_id": None})

    assert resposta.status_code == 403
