import pytest
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import NotAdminActor
from apps.accounts.factories import StudentFactory, UserFactory
from apps.editions.enums import EditionStatus
from apps.editions.exceptions import EditionClosed
from apps.editions.factories import EditionFactory
from apps.evaluations.enums import QuestionKind
from apps.evaluations.exceptions import (
    FinalFormAlreadyPublished,
    FinalFormEmpty,
    FinalFormHasAnswers,
)
from apps.evaluations.factories import (
    FinalAnswerFactory,
    FinalEvaluationFactory,
    FinalFormFactory,
    FinalQuestionFactory,
)
from apps.evaluations.models import FinalForm
from apps.evaluations.use_cases.configure_final_form import configure_final_form
from apps.evaluations.use_cases.publish_final_form import publish_final_form

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin():
    return UserFactory(role=UserRole.ADMIN)


def perguntas():
    return [
        {"order": 1, "prompt": "Pitch", "kind": QuestionKind.SCORE, "max_score": 10},
        {"order": 2, "prompt": "Texto", "kind": QuestionKind.TEXT, "max_score": None},
    ]


def client_for(user):
    client = APIClient()
    client.force_login(user)
    return client


def body():
    questions = [
        {"order": 1, "prompt": "Pitch", "kind": "SCORE", "max_score": "10.00"},
        {"order": 2, "prompt": "Texto", "kind": "TEXT"},
    ]
    return {"title": "Final", "questions": questions}


def url(edition, publish=False):
    suffix = "/publish" if publish else ""
    return f"/api/admin/editions/{edition.pk}/final-form{suffix}"


def publicar_com_resposta():
    resposta = FinalAnswerFactory()
    form = resposta.evaluation.form
    form.published = True
    form.save()
    return form


# configure_final_form


def test_cria_o_formulario_com_as_perguntas(admin):
    edition = EditionFactory()
    form = configure_final_form(
        actor=admin, edition=edition, title="Final", questions=perguntas()
    )
    assert form.edition == edition and not form.published
    assert form.questions.count() == 2


def test_substitui_as_perguntas_no_segundo_envio(admin):
    edition = EditionFactory()
    configure_final_form(actor=admin, edition=edition, title="A", questions=perguntas())
    form = configure_final_form(
        actor=admin, edition=edition, title="B", questions=perguntas()[:1]
    )
    assert form.title == "B" and form.questions.count() == 1
    assert FinalForm.objects.count() == 1


def test_nao_admin_nao_configura():
    with pytest.raises(NotAdminActor):
        configure_final_form(
            actor=StudentFactory().user,
            edition=EditionFactory(),
            title="",
            questions=perguntas(),
        )


def test_edicao_encerrada_nao_aceita_formulario(admin):
    edition = EditionFactory(status=EditionStatus.CLOSED)
    with pytest.raises(EditionClosed):
        configure_final_form(
            actor=admin, edition=edition, title="", questions=perguntas()
        )


def test_publicado_com_resposta_nao_muda(admin):
    form = publicar_com_resposta()
    with pytest.raises(FinalFormHasAnswers):
        configure_final_form(
            actor=admin, edition=form.edition, title="", questions=perguntas()
        )


def test_publicado_sem_resposta_ainda_muda(admin):
    form = FinalFormFactory(published=True)
    FinalQuestionFactory(form=form)
    configure_final_form(
        actor=admin, edition=form.edition, title="Novo", questions=perguntas()
    )
    form.refresh_from_db()
    assert form.title == "Novo" and form.questions.count() == 2


def test_rascunho_com_avaliacao_ainda_muda(admin):
    avaliacao = FinalEvaluationFactory()
    assert not avaliacao.form.published
    configure_final_form(
        actor=admin, edition=avaliacao.form.edition, title="", questions=perguntas()
    )


# publish_final_form


def test_publica_formulario_com_perguntas(admin):
    form = FinalFormFactory()
    FinalQuestionFactory(form=form)
    assert publish_final_form(actor=admin, form=form).published


def test_nao_publica_formulario_vazio(admin):
    with pytest.raises(FinalFormEmpty):
        publish_final_form(actor=admin, form=FinalFormFactory())


def test_nao_publica_duas_vezes(admin):
    form = FinalFormFactory(published=True)
    FinalQuestionFactory(form=form)
    with pytest.raises(FinalFormAlreadyPublished):
        publish_final_form(actor=admin, form=form)


def test_nao_admin_nao_publica():
    form = FinalFormFactory()
    FinalQuestionFactory(form=form)
    with pytest.raises(NotAdminActor):
        publish_final_form(actor=StudentFactory().user, form=form)


def test_edicao_encerrada_nao_publica(admin):
    form = FinalFormFactory(edition=EditionFactory(status=EditionStatus.CLOSED))
    FinalQuestionFactory(form=form)
    with pytest.raises(EditionClosed):
        publish_final_form(actor=admin, form=form)


# API


def test_api_put_get_e_publish(admin):
    edition = EditionFactory()
    client = client_for(admin)
    assert client.get(url(edition)).status_code == 404

    put = client.put(url(edition), body(), format="json")
    assert put.status_code == 200
    assert [q["order"] for q in put.data["questions"]] == [1, 2]
    assert put.data["questions"][0]["max_score"] == "10.00"
    assert put.data["questions"][1]["max_score"] is None
    assert client.get(url(edition)).data["title"] == "Final"

    publish = client.post(url(edition, publish=True))
    assert publish.status_code == 200 and publish.data["published"] is True
    again = client.post(url(edition, publish=True))
    assert again.status_code == 409
    assert again.data["error"]["code"] == "final_form_already_published"


def test_api_publish_vazio_da_409(admin):
    form = FinalFormFactory()
    response = client_for(admin).post(url(form.edition, publish=True))
    assert response.status_code == 409
    assert response.data["error"]["code"] == "final_form_empty"


def test_api_put_com_resposta_da_409(admin):
    form = publicar_com_resposta()
    response = client_for(admin).put(url(form.edition), body(), format="json")
    assert response.status_code == 409
    assert response.data["error"]["code"] == "final_form_has_answers"


def test_api_put_em_edicao_encerrada_da_409(admin):
    edition = EditionFactory(status=EditionStatus.CLOSED)
    response = client_for(admin).put(url(edition), body(), format="json")
    assert response.status_code == 409
    assert response.data["error"]["code"] == "edition_closed"


@pytest.mark.parametrize(
    "questions",
    [
        [],
        [{"order": 1, "prompt": "x", "kind": "SCORE"}],
        [{"order": 1, "prompt": "x", "kind": "SCORE", "max_score": "0"}],
        [{"order": 1, "prompt": "x", "kind": "TEXT", "max_score": "5"}],
        [
            {"order": 1, "prompt": "x", "kind": "TEXT"},
            {"order": 1, "prompt": "y", "kind": "TEXT"},
        ],
    ],
)
def test_api_put_invalido_da_400(admin, questions):
    response = client_for(admin).put(
        url(EditionFactory()), {"title": "t", "questions": questions}, format="json"
    )
    assert response.status_code == 400


def test_api_edicao_inexistente_da_404(admin):
    client = client_for(admin)
    put = client.put("/api/admin/editions/999999/final-form", body(), format="json")
    publish = client.post("/api/admin/editions/999999/final-form/publish")
    assert put.status_code == 404 and publish.status_code == 404


def test_api_so_admin_acessa():
    edition = EditionFactory()
    student = client_for(StudentFactory().user)
    assert student.get(url(edition)).status_code == 403
    assert student.put(url(edition), body(), format="json").status_code == 403
    assert student.post(url(edition, publish=True)).status_code == 403
    assert APIClient().get(url(edition)).status_code == 401


def test_put_mantem_o_id_da_pergunta_que_continua(admin):
    edition = EditionFactory()
    form = configure_final_form(
        actor=admin, edition=edition, title="", questions=perguntas()
    )
    ids = {q.order: q.pk for q in form.questions.all()}

    nova = perguntas()[:1]
    nova[0]["prompt"] = "Pitch revisado"
    configure_final_form(actor=admin, edition=edition, title="", questions=nova)

    restante = form.questions.get()
    assert restante.pk == ids[1] and restante.prompt == "Pitch revisado"


def test_formulario_sem_titulo_e_aceito(admin):
    edition = EditionFactory()
    sem_titulo = {"questions": body()["questions"]}

    response = client_for(admin).put(url(edition), sem_titulo, format="json")

    assert response.status_code == 200, response.data
    assert response.data["title"] is None
