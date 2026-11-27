import pytest
from django.contrib import admin
from django.urls import reverse

from apps.accounts.enums import UserRole
from apps.accounts.factories import UserFactory
from apps.evaluations.models import Evaluation, StageScore

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(client):
    client.force_login(UserFactory(role=UserRole.ADMIN))
    return client


@pytest.mark.parametrize("model", [Evaluation, StageScore])
def test_avaliacao_e_nota_sao_somente_leitura_no_admin(admin_client, model):
    model_admin = admin.site._registry[model]
    request = admin_client.get("/").wsgi_request

    assert not model_admin.has_add_permission(request)
    assert not model_admin.has_change_permission(request)
    assert not model_admin.has_delete_permission(request)


def test_itens_da_avaliacao_nao_sao_editaveis_pelo_inline(admin_client):
    request = admin_client.get("/").wsgi_request
    evaluation_admin = admin.site._registry[Evaluation]
    inline = evaluation_admin.get_inline_instances(request)

    assert all(not item.has_change_permission(request) for item in inline)


def test_lista_de_avaliacoes_continua_consultavel(admin_client):
    response = admin_client.get(reverse("admin:evaluations_evaluation_changelist"))

    assert response.status_code == 200
