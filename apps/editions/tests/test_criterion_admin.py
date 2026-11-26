import pytest
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.urls import reverse

from apps.accounts.enums import UserRole
from apps.accounts.factories import UserFactory
from apps.editions.enums import EditionStatus
from apps.editions.factories import (
    CriterionFactory,
    EditionFactory,
    StageCriterionFactory,
)
from apps.editions.models import Criterion
from apps.evaluations.factories import EvaluationFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(client):
    client.force_login(
        UserFactory(role=UserRole.ADMIN, is_staff=True, is_superuser=True)
    )
    return client


def test_admin_cria_criterio(admin_client):
    edition = EditionFactory()
    response = admin_client.post(
        reverse("admin:editions_criterion_add"),
        {
            "edition": edition.pk,
            "name": "  Novo  ",
            "rubric": "Faixas",
            "tiebreak_order": 1,
        },
    )
    assert response.status_code == 302
    criterion = Criterion.objects.get(edition=edition)
    assert (criterion.name, criterion.rubric, criterion.tiebreak_order) == (
        "Novo",
        "Faixas",
        1,
    )


def test_admin_bloqueia_criacao_em_edicao_encerrada(admin_client):
    edition = EditionFactory(status=EditionStatus.CLOSED)
    response = admin_client.post(
        reverse("admin:editions_criterion_add"),
        {
            "edition": edition.pk,
            "name": "Novo",
        },
    )
    assert response.status_code == 200
    assert "encerrada" in str(response.context["adminform"].form.errors)
    assert not Criterion.objects.filter(edition=edition).exists()


@pytest.mark.parametrize(
    "scenario", ["allowed", "closed", "from_closed", "to_closed", "evaluation"]
)
def test_admin_altera_criterio_conforme_edicao_e_avaliacoes(admin_client, scenario):
    origin_status = (
        EditionStatus.CLOSED
        if scenario in {"closed", "from_closed"}
        else EditionStatus.SETUP
    )
    criterion = CriterionFactory(edition__status=origin_status)
    destination = criterion.edition
    if scenario in {"from_closed", "to_closed"}:
        status = (
            EditionStatus.CLOSED if scenario == "to_closed" else EditionStatus.SETUP
        )
        destination = EditionFactory(status=status)
    if scenario == "evaluation":
        link = StageCriterionFactory(
            criterion=criterion, stage__edition=criterion.edition
        )
        EvaluationFactory(stage=link.stage, finalized=True)
    before = Criterion.objects.values().get(pk=criterion.pk)

    response = admin_client.post(
        reverse("admin:editions_criterion_change", args=[criterion.pk]),
        {
            "edition": destination.pk,
            "name": "Revisado",
            "rubric": "Nova rubrica",
        },
    )

    if scenario == "allowed":
        assert response.status_code == 302
        criterion.refresh_from_db()
        assert (criterion.name, criterion.rubric) == ("Revisado", "Nova rubrica")
    else:
        assert response.status_code == 200
        errors = str(response.context["adminform"].form.errors)
        assert ("avaliações" if scenario == "evaluation" else "encerrada") in errors
        assert Criterion.objects.values().get(pk=criterion.pk) == before


@pytest.mark.parametrize("bulk", [False, True])
@pytest.mark.parametrize("closed", [False, True])
def test_admin_exclui_apenas_criterios_de_edicao_aberta(admin_client, bulk, closed):
    criterion = CriterionFactory(
        edition__status=EditionStatus.CLOSED if closed else EditionStatus.SETUP
    )
    allowed = CriterionFactory()
    if bulk:
        response = admin_client.post(
            reverse("admin:editions_criterion_changelist"),
            {
                "action": "delete_selected",
                ACTION_CHECKBOX_NAME: [criterion.pk, allowed.pk],
                "post": "yes",
            },
        )
        assert Criterion.objects.filter(pk=allowed.pk).exists() == closed
    else:
        response = admin_client.post(
            reverse("admin:editions_criterion_delete", args=[criterion.pk]),
            {"post": "yes"},
        )
    assert response.status_code == (403 if closed else 302)
    assert Criterion.objects.filter(pk=criterion.pk).exists() == closed
