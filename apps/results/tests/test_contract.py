"""As respostas de results seguem o contrato (docs/api/openapi.yaml)."""

import pytest

from apps.core.tests.contract import mismatches, schema
from apps.projects.enums import ProjectStatus
from apps.projects.models import Project
from apps.results.tests.test_api import client_for, post, url
from apps.results.tests.test_use_cases import evaluate_final

pytestmark = pytest.mark.django_db


def test_calculo_finalistas_e_homologacao_seguem_o_contrato(
    admin, edition, make_project
):
    project = make_project("3.00", "2.50")
    pending = make_project("1.00")  # pendente: aparece em excluded
    make_project("1.00", "1.00", status=ProjectStatus.DISQUALIFIED)
    client = client_for(admin)

    calculated = post(client, edition, "results/calculate")
    assert mismatches({}, schema("FinalistsSelect")) == []
    chosen = client.post(url(edition, "finalists"), {}, format="json")
    evaluate_final(project)
    awarded = post(client, edition, "awards/calculate")
    # Homologar exige nenhuma nota pendente: o pendente sai da disputa.
    Project.objects.filter(pk=pending.pk).update(status=ProjectStatus.DISQUALIFIED)
    approved = post(client, edition, "results/homologate")

    for response in (calculated, chosen, awarded, approved):
        assert response.status_code == 200
        assert mismatches(response.json(), schema("EditionResults")) == []
    assert approved.json()["results"][0]["project"]["id"] == project.pk
