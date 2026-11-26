import pytest

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import NotAdminActor
from apps.accounts.factories import UserFactory
from apps.editions.factories import CategoryFactory, EditionFactory
from apps.editions.use_cases.create_category import create_category
from apps.editions.use_cases.delete_category import delete_category
from apps.editions.use_cases.update_category import update_category

pytestmark = pytest.mark.django_db


def test_create_category_persiste_valores_padrao():
    edition = EditionFactory()
    category = create_category(
        actor=UserFactory(role=UserRole.ADMIN), edition=edition, name="Protótipos"
    )
    category.refresh_from_db()
    assert category.edition_id == edition.pk
    assert category.active is True
    assert category.description == ""


def test_casos_de_uso_de_categoria_exigem_admin():
    actor = UserFactory(role=UserRole.TEACHER)
    category = CategoryFactory()

    with pytest.raises(NotAdminActor):
        create_category(actor=actor, edition=category.edition, name="Outra")
    with pytest.raises(NotAdminActor):
        update_category(actor=actor, category=category, active=False)
    with pytest.raises(NotAdminActor):
        delete_category(actor=actor, category=category)

    category.refresh_from_db()
    assert category.active is True
    assert category.edition.categories.count() == 1
