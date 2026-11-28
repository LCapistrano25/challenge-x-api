from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.factories import UserFactory
from apps.editions.factories import EditionFactory
from apps.editions.models import Stage
from apps.editions.use_cases.create_stage import create_stage
from apps.editions.use_cases.update_stage import update_stage

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin():
    return UserFactory(role=UserRole.ADMIN)


def _stage(admin, **extra):
    now = timezone.now()
    data = {
        "order": 1,
        "name": "Ideia",
        "kind": "SUBMISSION",
        "starts_at": now,
        "ends_at": now + timedelta(days=1),
        "scored": False,
    }
    return create_stage(actor=admin, edition=EditionFactory(), **(data | extra))


@pytest.mark.parametrize("name", ["", "   "])
def test_etapa_recusa_nome_em_branco(admin, name):
    with pytest.raises(ValidationError):
        _stage(admin, name=name)
    assert not Stage.objects.exists()


def test_api_recusa_nome_em_branco_e_remove_espacos_das_pontas(admin):
    stage = _stage(admin)
    client = APIClient()
    client.force_authenticate(admin)
    url = f"/api/admin/stages/{stage.pk}"
    assert client.patch(url, {"name": "  "}, format="json").status_code == 400
    response = client.patch(url, {"name": "  Final  "}, format="json")
    assert response.status_code == 200
    assert response.json()["name"] == "Final"


def test_mudar_somente_campos_atualiza_a_data_da_etapa(admin):
    stage = _stage(admin)
    # Recua a data: no Windows duas gravações seguidas podem ter o mesmo horário.
    before = timezone.now() - timedelta(hours=1)
    Stage.objects.filter(pk=stage.pk).update(updated_at=before)
    update_stage(actor=admin, stage=stage, submission_fields=[{"kind": "LINK"}])
    assert Stage.objects.get(pk=stage.pk).updated_at > before
