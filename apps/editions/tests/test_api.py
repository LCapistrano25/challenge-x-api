import pytest
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.factories import ExternalReviewerFactory, TeacherFactory, UserFactory
from apps.core.factories import CourseFactory
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
