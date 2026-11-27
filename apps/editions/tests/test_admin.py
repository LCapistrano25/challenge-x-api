import pytest
from django.contrib import admin
from django.urls import reverse

from apps.accounts.enums import UserRole
from apps.accounts.factories import UserFactory
from apps.editions.enums import EditionStatus
from apps.editions.factories import EditionFactory
from apps.editions.models import Edition

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_user_client(client):
    client.force_login(UserFactory(role=UserRole.ADMIN))
    return client


def test_status_da_edicao_e_somente_leitura_no_admin():
    edition_admin = admin.site._registry[Edition]

    assert {"status", "published_at", "closed_at"} <= set(edition_admin.readonly_fields)


def test_limites_congelam_apos_publicar(admin_user_client):
    edition_admin = admin.site._registry[Edition]
    request = admin_user_client.get("/").wsgi_request

    setup = edition_admin.get_readonly_fields(request, EditionFactory())
    published = edition_admin.get_readonly_fields(
        request, EditionFactory(status=EditionStatus.PUBLISHED)
    )

    assert "max_members" not in setup
    assert {"min_members", "max_members"} <= set(published)


def test_edicao_encerrada_nao_e_alterada_pelo_admin(admin_user_client):
    edition = EditionFactory(status=EditionStatus.CLOSED, name="Original")

    response = admin_user_client.post(
        reverse("admin:editions_edition_change", args=[edition.pk]),
        {"name": "Reaberta"},
    )

    assert response.status_code == 403
    edition.refresh_from_db()
    assert edition.name == "Original"
    assert edition.status == EditionStatus.CLOSED
