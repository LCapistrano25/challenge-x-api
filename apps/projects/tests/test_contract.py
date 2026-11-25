"""As respostas de projects seguem o contrato (docs/api/openapi.yaml)."""

from datetime import timedelta

import pytest
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.accounts.enums import UserRole
from apps.accounts.factories import UserFactory
from apps.core.tests.contract import mismatches, schema
from apps.editions.factories import StageFactory, StageSubmissionFieldFactory
from apps.projects.factories import (
    ProjectFactory,
    SubmissionFactory,
    SubmissionVersionFactory,
)
from apps.projects.tests.conftest import valid_canvas
from apps.projects.tests.test_api import (  # noqa: F401
    canvas_field,
    client_for,
    deliverables_url,
    dfield,
    dleader,
    dproject,
    dstage,
    extension_url,
    ffield,
    make_stage,
    payload,
    pdf_upload,
    post_multipart,
    post_version,
)

pytestmark = pytest.mark.django_db


def deliverables_schema():
    return {"type": "array", "items": schema("StageDeliverable")}


def test_envio_em_json_segue_o_contrato(dproject, dleader, dstage, dfield):  # noqa: F811
    body = payload(dfield)
    assert mismatches(body, schema("DeliverableSubmission")) == []

    response = post_version(dleader, dproject, dstage, body)

    assert response.status_code == 201
    assert mismatches(response.json(), schema("DeliverableVersion")) == []
    assert response.json()["number"] == 1
    assert response.json()["notes"] is None


def test_consulta_de_entregas_segue_o_contrato(
    dproject,  # noqa: F811
    dleader,  # noqa: F811
    dstage,  # noqa: F811
    dfield,  # noqa: F811
    ffield,  # noqa: F811
    canvas_field,  # noqa: F811
):
    unscored = make_stage(
        dproject, scored=False, max_score=None, evaluation_ends_at=None
    )
    StageSubmissionFieldFactory(stage=unscored)
    sent = post_multipart(
        dleader,
        dproject,
        dstage,
        [
            {"field_id": dfield.pk, "link": "https://github.com/equipe/projeto"},
            {"field_id": ffield.pk, "file_index": 0},
            {"field_id": canvas_field.pk, "content": valid_canvas()},
        ],
        [pdf_upload()],
    )
    assert sent.status_code == 201, sent.data
    assert mismatches(sent.json(), schema("DeliverableVersion")) == []

    response = client_for(dleader).get(deliverables_url(dproject))

    assert response.status_code == 200
    assert mismatches(response.json(), deliverables_schema()) == []
    scored, empty = response.json()
    # Tipos e valores que o contract.py não confere.
    assert scored["stage"]["order"] == dstage.order
    assert scored["stage"]["max_score"] == "3.00"
    assert (
        parse_datetime(scored["stage"]["evaluation_ends_at"])
        == dstage.evaluation_ends_at
    )
    assert scored["versions"][0]["number"] == 1
    assert sorted(i["type"] for i in scored["versions"][0]["items"]) == [
        "CANVAS",
        "FILE",
        "LINK",
    ]
    assert empty["stage"]["max_score"] is None
    assert empty["stage"]["evaluation_ends_at"] is None
    assert empty["versions"] == []
    assert empty["official_version_id"] is None


def test_versao_sem_comprovante_segue_o_contrato(
    dproject,  # noqa: F811
    dleader,  # noqa: F811
    dstage,  # noqa: F811
    dfield,  # noqa: F811
):
    submission = SubmissionFactory(project=dproject, stage=dstage)
    SubmissionVersionFactory(submission=submission)

    response = client_for(dleader).get(deliverables_url(dproject))

    assert mismatches(response.json(), deliverables_schema()) == []
    assert response.json()[0]["versions"][0]["receipt"] is None


def test_prorrogacao_segue_o_contrato():
    project = ProjectFactory()
    stage = StageFactory(
        edition=project.edition,
        starts_at=timezone.now() - timedelta(days=5),
        ends_at=timezone.now() - timedelta(days=1),
    )
    body = {
        "stage_id": stage.pk,
        "ends_at": (stage.ends_at + timedelta(days=3)).isoformat(),
        "reason": "Atestado médico do líder.",
    }

    assert mismatches(body, schema("DeadlineExtensionWrite")) == []
    response = client_for(UserFactory(role=UserRole.ADMIN)).post(
        extension_url(project.team), body, format="json"
    )

    assert response.status_code == 201
    assert mismatches(response.json(), schema("DeadlineExtension")) == []
