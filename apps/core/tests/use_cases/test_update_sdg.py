import pytest
from django.core.exceptions import ValidationError

from apps.core.models import Sdg
from apps.core.use_cases.update_sdg import update_sdg


@pytest.mark.django_db
def test_update_sdg_success(admin_user):
    """Garante que o admin consegue atualizar uma ODS."""
    sdg = Sdg.objects.first()

    updated_sdg = update_sdg(
        actor=admin_user,
        sdg_id=sdg.id,
        title="Novo Título de ODS",
        description="Uma nova descrição muito melhor.",
    )

    assert updated_sdg.title == "Novo Título de ODS"
    assert updated_sdg.description == "Uma nova descrição muito melhor."


@pytest.mark.django_db
def test_update_sdg_fails_if_not_admin(django_user_model):
    """Garante que utilizadores comuns não podem atualizar ODS."""
    normal_user = django_user_model.objects.create(email="comum2@teste.com")
    sdg = Sdg.objects.first()

    with pytest.raises(
        PermissionError, match="Apenas administradores podem atualizar ODS."
    ):
        update_sdg(actor=normal_user, sdg_id=sdg.id, title="Hackeado")


@pytest.mark.django_db
def test_update_sdg_not_found(admin_user):
    """Garante erro se a ODS não existir."""
    with pytest.raises(ValidationError, match="ODS não encontrada."):
        update_sdg(actor=admin_user, sdg_id=9999, title="Fantasma")
