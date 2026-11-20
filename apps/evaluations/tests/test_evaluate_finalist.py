from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.factories import ExternalReviewerFactory, StudentFactory, UserFactory
from apps.core.factories import CourseFactory
from apps.editions.enums import EditionStatus
from apps.editions.exceptions import EditionClosed
from apps.editions.factories import EditionReviewerFactory
from apps.evaluations.enums import FinalEvaluationStatus
from apps.evaluations.exceptions import (
    FinalEvaluationAlreadyFinalized,
    FinalFormNotPublished,
    FinalistNotFound,
    NotExternalReviewerActor,
)
from apps.evaluations.factories import FinalFormFactory, FinalQuestionFactory
from apps.evaluations.models import FinalEvaluation
from apps.evaluations.use_cases.evaluate_finalist import evaluate_finalist
from apps.projects.factories import ProjectFactory
from apps.results.factories import ProjectResultFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def project():
    project = ProjectFactory()
    project.edition.status = EditionStatus.PUBLISHED
    project.edition.save()
    ProjectResultFactory(project=project, finalist=True)
    return project


@pytest.fixture
def reviewer(project):
    reviewer = ExternalReviewerFactory()
    EditionReviewerFactory(edition=project.edition, reviewer=reviewer)
    return reviewer


@pytest.fixture
def form(project):
    form = FinalFormFactory(edition=project.edition, published=True)
    FinalQuestionFactory(form=form, order=1, max_score=Decimal("10.00"))
    FinalQuestionFactory(form=form, order=2, text=True)
    return form


def respostas(form, value="8.00", text="Bom pitch."):
    nota, texto = form.questions.all()
    return [
        {"question": nota, "value": Decimal(value), "text": ""},
        {"question": texto, "value": None, "text": text},
    ]


def avaliar(reviewer, project, answers, finalize=False):
    return evaluate_finalist(
        actor=reviewer.user, project=project, answers=answers, finalize=finalize
    )


# evaluate_finalist


def test_salva_rascunho_e_atualiza_sem_duplicar(project, reviewer, form):
    avaliar(reviewer, project, respostas(form)[:1])
    avaliacao = avaliar(reviewer, project, respostas(form, value="9.00"))

    assert avaliacao.status == FinalEvaluationStatus.PENDING
    assert avaliacao.finalized_at is None
    assert FinalEvaluation.objects.count() == 1
    assert avaliacao.answers.count() == 2


def test_finaliza_com_todas_as_respostas(project, reviewer, form):
    avaliacao = avaliar(reviewer, project, respostas(form), finalize=True)

    assert avaliacao.status == FinalEvaluationStatus.EVALUATED
    assert avaliacao.finalized_at is not None


def test_pergunta_fora_da_lista_sai_do_rascunho(project, reviewer, form):
    avaliar(reviewer, project, respostas(form))
    avaliacao = avaliar(reviewer, project, respostas(form)[:1])

    assert avaliacao.answers.count() == 1


def test_nao_finaliza_sem_responder_todas_as_perguntas(project, reviewer, form):
    with pytest.raises(ValidationError):
        avaliar(reviewer, project, respostas(form)[:1], finalize=True)


def test_nota_acima_do_maximo_e_recusada(project, reviewer, form):
    with pytest.raises(ValidationError):
        avaliar(reviewer, project, respostas(form, value="10.01"))


def test_pergunta_repetida_e_recusada(project, reviewer, form):
    answers = respostas(form)[:1] * 2
    with pytest.raises(ValidationError):
        avaliar(reviewer, project, answers)


def test_avaliacao_finalizada_nao_muda(project, reviewer, form):
    avaliar(reviewer, project, respostas(form), finalize=True)
    with pytest.raises(FinalEvaluationAlreadyFinalized):
        avaliar(reviewer, project, respostas(form, value="1.00"))


def test_so_avaliador_externo_avalia(project, form):
    with pytest.raises(NotExternalReviewerActor):
        evaluate_finalist(
            actor=StudentFactory().user,
            project=project,
            answers=respostas(form),
        )


def test_avaliador_sem_vinculo_com_a_edicao_nao_avalia(project, form):
    with pytest.raises(FinalistNotFound):
        avaliar(ExternalReviewerFactory(), project, respostas(form))


def test_projeto_que_nao_e_finalista_nao_e_avaliado(project, reviewer, form):
    project.result.finalist = False
    project.result.save()
    with pytest.raises(FinalistNotFound):
        avaliar(reviewer, project, respostas(form))


def test_vinculo_de_outro_curso_nao_cobre_o_projeto(project, form):
    reviewer = ExternalReviewerFactory()
    EditionReviewerFactory(
        edition=project.edition, reviewer=reviewer, course=CourseFactory()
    )
    with pytest.raises(FinalistNotFound):
        avaliar(reviewer, project, respostas(form))


def test_vinculo_do_curso_do_desafio_cobre_o_projeto(project, form):
    reviewer = ExternalReviewerFactory()
    EditionReviewerFactory(
        edition=project.edition, reviewer=reviewer, course=project.challenge.course
    )
    assert avaliar(reviewer, project, respostas(form))


def test_formulario_nao_publicado_trava_a_avaliacao(project, reviewer, form):
    form.published = False
    form.save()
    with pytest.raises(FinalFormNotPublished):
        avaliar(reviewer, project, respostas(form))


def test_edicao_encerrada_nao_aceita_avaliacao(project, reviewer, form):
    project.edition.status = EditionStatus.CLOSED
    project.edition.save()
    with pytest.raises(EditionClosed):
        avaliar(reviewer, project, respostas(form))


# API


def client_for(user):
    client = APIClient()
    client.force_login(user)
    return client


def corpo(form, status="EVALUATED", value="8.00"):
    nota, texto = form.questions.all()
    return {
        "status": status,
        "comment": "Apresentação objetiva.",
        "answers": [
            {"question_id": nota.pk, "value": value},
            {"question_id": texto.pk, "text": "Bom pitch."},
        ],
    }


def url(project):
    return f"/api/evaluator/finalists/{project.pk}/final-evaluation"


def test_api_painel_lista_so_finalistas_da_abrangencia(project, reviewer, form):
    outro = ProjectFactory(edition=project.edition)
    ProjectResultFactory(project=outro)  # não é finalista

    response = client_for(reviewer.user).get("/api/evaluator/finalists")

    assert response.status_code == 200
    ids = [row["project"]["id"] for row in response.data["results"]]
    assert ids == [project.pk]
    assert response.data["results"][0]["my_evaluation_status"] == "PENDING"


def test_api_painel_filtra_por_curso(project, reviewer, form):
    response = client_for(reviewer.user).get(
        "/api/evaluator/finalists", {"course_id": CourseFactory().pk}
    )

    assert response.data["results"] == []


def test_api_painel_sem_formulario_publicado_da_409(project, reviewer):
    FinalFormFactory(edition=project.edition)
    response = client_for(reviewer.user).get("/api/evaluator/finalists")

    assert response.status_code == 409
    assert response.data["error"]["code"] == "final_form_not_published"


def test_api_painel_nao_vaza_nota_nem_entrega(project, reviewer, form):
    response = client_for(reviewer.user).get("/api/evaluator/finalists")

    chaves = set(response.data["results"][0]["project"])
    assert not {"score", "final_score", "stages", "deliverables"} & chaves


def test_api_get_devolve_formulario_e_avaliacao(project, reviewer, form):
    client = client_for(reviewer.user)
    antes = client.get(url(project))
    client.put(url(project), corpo(form, "PENDING"), format="json")
    depois = client.get(url(project))

    assert antes.status_code == 200 and antes.data["evaluation"] is None
    assert len(antes.data["form"]["questions"]) == 2
    assert depois.data["evaluation"]["status"] == "PENDING"
    assert len(depois.data["evaluation"]["answers"]) == 2


def test_api_put_finaliza_e_depois_da_409(project, reviewer, form):
    client = client_for(reviewer.user)
    first = client.put(url(project), corpo(form), format="json")
    again = client.put(url(project), corpo(form), format="json")

    assert first.status_code == 200
    assert first.data["status"] == "EVALUATED"
    assert again.status_code == 409
    assert again.data["error"]["code"] == "final_evaluation_already_finalized"


def test_api_put_com_pergunta_de_outro_formulario_da_400(project, reviewer, form):
    outra = FinalQuestionFactory()
    body = corpo(form)
    body["answers"][0]["question_id"] = outra.pk

    response = client_for(reviewer.user).put(url(project), body, format="json")

    assert response.status_code == 400


def test_api_put_nota_invalida_da_400(project, reviewer, form):
    response = client_for(reviewer.user).put(
        url(project), corpo(form, value="11.00"), format="json"
    )

    assert response.status_code == 400


def test_api_projeto_fora_da_abrangencia_da_404(project, form):
    outro = ExternalReviewerFactory()
    client = client_for(outro.user)

    assert client.get(url(project)).status_code == 404
    assert client.put(url(project), corpo(form), format="json").status_code == 404


def test_api_projeto_inexistente_da_404(reviewer, form):
    response = client_for(reviewer.user).get(
        "/api/evaluator/finalists/999999/final-evaluation"
    )

    assert response.status_code == 404


def test_api_so_avaliador_externo_acessa(project, form):
    admin = client_for(UserFactory(role=UserRole.ADMIN))
    aluno = client_for(StudentFactory().user)

    for client in (admin, aluno):
        assert client.get("/api/evaluator/finalists").status_code == 403
        assert client.get(url(project)).status_code == 403
        assert client.put(url(project), corpo(form), format="json").status_code == 403
    assert APIClient().get("/api/evaluator/finalists").status_code in (401, 403)
