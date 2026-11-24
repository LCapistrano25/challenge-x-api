"""As respostas de projects seguem o contrato (docs/api/openapi.yaml)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.factories import UserFactory
from apps.core.tests.contract import mismatches, schema
from apps.editions.factories import StageFactory
from apps.projects.factories import ProjectFactory
from apps.projects.tests.test_api import client_for, extension_url

pytestmark = pytest.mark.django_db


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
