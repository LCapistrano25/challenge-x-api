import pytest
from django.core.exceptions import ValidationError

from apps.core.exceptions import SdgInUse
from apps.core.models import Sdg
from apps.core.use_cases.delete_sdg import delete_sdg
from apps.editions.factories import ChallengeFactory, EditionSdgFactory


@pytest.mark.django_db
def test_delete_sdg_success(admin_user):
    """Garante que o admin consegue excluir uma ODS sem vínculos."""
    sdg = Sdg.objects.first()
    sdg_id = sdg.id

    delete_sdg(actor=admin_user, sdg_id=sdg_id)

    assert not Sdg.objects.filter(id=sdg_id).exists()


@pytest.mark.django_db
def test_delete_sdg_fails_if_not_admin(django_user_model):
    """Garante que utilizadores comuns não excluem ODS."""
    normal_user = django_user_model.objects.create(email="comum3@teste.com")
    sdg = Sdg.objects.first()

    with pytest.raises(
        PermissionError, match="Apenas administradores podem excluir ODS."
    ):
        delete_sdg(actor=normal_user, sdg_id=sdg.id)


@pytest.mark.django_db
def test_delete_sdg_not_found(admin_user):
    """Garante erro se tentar apagar uma ODS que não existe."""
    with pytest.raises(ValidationError, match="ODS não encontrada."):
        delete_sdg(actor=admin_user, sdg_id=9999)


@pytest.mark.django_db
@pytest.mark.parametrize("link", ["challenge", "edition"])
def test_delete_sdg_in_use_raises_sdg_in_use(admin_user, link):
    """ODS usada por desafio ou habilitada em edição não é excluída (#280)."""
    sdg = Sdg.objects.first()
    if link == "challenge":
        ChallengeFactory(sdg=sdg)
    else:
        EditionSdgFactory(sdg=sdg)

    with pytest.raises(SdgInUse):
        delete_sdg(actor=admin_user, sdg_id=sdg.id)
    assert Sdg.objects.filter(id=sdg.id).exists()
