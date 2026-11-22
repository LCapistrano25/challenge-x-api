import pytest

from apps.core.models import Sdg
from apps.core.use_cases.list_public_sdgs import list_public_sdgs
from apps.core.use_cases.list_sdgs import list_sdgs


@pytest.mark.django_db
def test_list_sdgs_admin(admin_user):
    """Garante que o admin lista todas as ODS."""
    sdgs = list_sdgs(actor=admin_user)

    # A base de dados preenche 5 ODS inicialmente
    assert sdgs.count() == 5


@pytest.mark.django_db
def test_list_sdgs_fails_if_not_admin(django_user_model):
    """Garante que utilizadores comuns não listam as ODS de admin."""
    normal_user = django_user_model.objects.create(email="comum4@teste.com")

    with pytest.raises(
        PermissionError, match="Apenas administradores podem listar ODS."
    ):
        list_sdgs(actor=normal_user)


@pytest.mark.django_db
def test_list_public_sdgs():
    """Garante que o endpoint público só lista as ODS ativas."""
    # Vamos desativar a primeira ODS para testar o filtro
    sdg = Sdg.objects.first()
    sdg.active = False
    sdg.save()

    ativas = list_public_sdgs()

    assert ativas.count() == 4  # Eram 5, desativámos 1
    assert sdg not in ativas
