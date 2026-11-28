import pytest
from django.core.exceptions import ValidationError

from apps.core.exceptions import SdgNumberTaken
from apps.core.models import Sdg
from apps.core.use_cases.create_sdg import create_sdg


@pytest.mark.django_db
def test_create_sdg_success(admin_user):
    """Garante que um admin consegue criar ODS."""
    Sdg.objects.all().delete()  # Limpa as ODS que vêm de fábrica

    sdg = create_sdg(
        actor=admin_user,
        number=1,
        title="Erradicação da Pobreza",
        description="Acabar com a pobreza.",
    )

    assert sdg.id is not None
    assert sdg.number == 1
    assert sdg.title == "Erradicação da Pobreza"


@pytest.mark.django_db
def test_create_sdg_fails_if_not_admin(django_user_model):
    """Garante que utilizadores comuns não criam ODS."""
    Sdg.objects.all().delete()
    normal_user = django_user_model.objects.create(email="comum@teste.com")

    with pytest.raises(
        PermissionError, match="Apenas administradores podem cadastrar ODS."
    ):
        create_sdg(actor=normal_user, number=2, title="Fome Zero")


@pytest.mark.django_db
def test_create_sdg_fails_if_invalid_number(admin_user):
    """Garante que a regra de 1 a 17 é respeitada."""
    # Aqui não apagamos, porque tentar 18 já vai falhar de qualquer modo
    with pytest.raises(
        ValidationError, match="O número da ODS deve estar entre 1 e 17."
    ):
        create_sdg(actor=admin_user, number=18, title="Inválida")


@pytest.mark.django_db
def test_create_sdg_fails_if_duplicate_number(admin_user):
    """Garante que não existem ODS com número repetido."""
    Sdg.objects.all().delete()  # Limpamos para testar a duplicação controlada
    create_sdg(actor=admin_user, number=3, title="Saúde")

    with pytest.raises(SdgNumberTaken):
        create_sdg(actor=admin_user, number=3, title="Outro Título")
