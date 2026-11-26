from importlib import import_module

import pytest
from django.core.exceptions import ValidationError

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import NotAdminActor
from apps.accounts.factories import UserFactory
from apps.editions.enums import EditionStatus
from apps.editions.exceptions import (
    CriterionInUseByEvaluations,
    CriterionLinkedToStage,
    CriterionNameTaken,
    EditionClosed,
    TiebreakOrderTaken,
)
from apps.editions.factories import (
    CriterionFactory,
    EditionFactory,
    StageCriterionFactory,
)
from apps.editions.models import Criterion
from apps.editions.use_cases.create_criterion import create_criterion
from apps.editions.use_cases.delete_criterion import delete_criterion
from apps.editions.use_cases.update_criterion import update_criterion
from apps.evaluations.factories import EvaluationFactory

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "fields",
    [
        {"name": None},
        {"name": "   "},
        {"name": "x" * 151},
        {"tiebreak_order": 0},
        {"tiebreak_order": 32768},
    ],
)
def test_criar_criterio_recusa_valores_invalidos_sem_persistir(fields):
    admin = UserFactory(role=UserRole.ADMIN)
    edition = EditionFactory()
    with pytest.raises(ValidationError):
        create_criterion(actor=admin, edition=edition, **({"name": "Novo"} | fields))
    assert not Criterion.objects.filter(edition=edition).exists()


@pytest.mark.parametrize(
    "fields",
    [
        {"name": None},
        {"name": "   "},
        {"name": "x" * 151},
        {"tiebreak_order": 0},
        {"tiebreak_order": 32768},
    ],
)
def test_atualizar_criterio_recusa_valores_invalidos_sem_persistir(fields):
    admin = UserFactory(role=UserRole.ADMIN)
    criterion = CriterionFactory()
    before = Criterion.objects.values().get(pk=criterion.pk)
    with pytest.raises(ValidationError):
        update_criterion(actor=admin, criterion=criterion, **fields)
    assert Criterion.objects.values().get(pk=criterion.pk) == before


@pytest.mark.parametrize(
    ("name", "order", "error"),
    [
        ("EXISTENTE", None, CriterionNameTaken),
        ("Outro", 1, TiebreakOrderTaken),
    ],
)
@pytest.mark.parametrize("operation", ["create", "update"])
def test_casos_de_uso_traduzem_violacao_real_do_banco(
    monkeypatch, name, order, error, operation
):
    existing = CriterionFactory(name="Existente", tiebreak_order=1)
    target = CriterionFactory(edition=existing.edition)
    actor = UserFactory(role=UserRole.ADMIN)
    module = import_module(f"apps.editions.use_cases.{operation}_criterion")
    monkeypatch.setattr(
        module, "ensure_criterion_values_are_unique", lambda **kwargs: None
    )

    with pytest.raises(error):
        if operation == "create":
            create_criterion(
                actor=actor, edition=existing.edition, name=name, tiebreak_order=order
            )
        else:
            update_criterion(
                actor=actor, criterion=target, name=name, tiebreak_order=order
            )

    assert Criterion.objects.filter(edition=existing.edition).count() == 2
    assert Criterion.objects.get(pk=target.pk).name == target.name


def test_casos_de_uso_recusam_ator_sem_papel_admin():
    criterion = CriterionFactory()
    actor = UserFactory(role=UserRole.STUDENT)
    criteria = (
        Criterion.objects.filter(edition=criterion.edition).order_by("pk").values()
    )
    before = list(criteria)
    with pytest.raises(NotAdminActor):
        create_criterion(actor=actor, edition=criterion.edition, name="Novo")
    assert list(criteria.all()) == before
    with pytest.raises(NotAdminActor):
        update_criterion(actor=actor, criterion=criterion, name="Novo")
    assert list(criteria.all()) == before
    with pytest.raises(NotAdminActor):
        delete_criterion(actor=actor, criterion=criterion)
    assert list(criteria.all()) == before


@pytest.fixture
def admin():
    return UserFactory(role=UserRole.ADMIN)


def test_criar_criterio_persiste_valores(admin):
    edition = EditionFactory()
    criterion = create_criterion(
        actor=admin,
        edition=edition,
        name="  Original  ",
        rubric=" texto ",
        tiebreak_order=1,
    )
    criterion.refresh_from_db()
    assert (
        criterion.edition_id,
        criterion.name,
        criterion.rubric,
        criterion.tiebreak_order,
    ) == (edition.pk, "Original", " texto ", 1)


def test_atualizar_criterio_persiste_mudanca_parcial(admin):
    criterion = CriterionFactory(rubric="Faixas", tiebreak_order=1)
    update_criterion(
        actor=admin, criterion=criterion, name="  Novo  ", tiebreak_order=None
    )
    criterion.refresh_from_db()
    assert (criterion.name, criterion.rubric, criterion.tiebreak_order) == (
        "Novo",
        "Faixas",
        None,
    )


def test_excluir_criterio_sem_vinculo(admin):
    criterion = CriterionFactory()
    pk = criterion.pk
    delete_criterion(actor=admin, criterion=criterion)
    assert not Criterion.objects.filter(pk=pk).exists()


def test_casos_de_uso_recusam_edicao_encerrada(admin):
    criterion = CriterionFactory(edition__status=EditionStatus.CLOSED)
    criteria = (
        Criterion.objects.filter(edition=criterion.edition).order_by("pk").values()
    )
    before = list(criteria)
    with pytest.raises(EditionClosed):
        create_criterion(actor=admin, edition=criterion.edition, name="Outro")
    assert list(criteria.all()) == before
    with pytest.raises(EditionClosed):
        update_criterion(actor=admin, criterion=criterion, name="Novo")
    assert list(criteria.all()) == before
    with pytest.raises(EditionClosed):
        delete_criterion(actor=admin, criterion=criterion)
    assert list(criteria.all()) == before


@pytest.mark.parametrize(
    ("fields", "error"),
    [
        ({"name": "  EXISTENTE  "}, CriterionNameTaken),
        ({"name": "Outro", "tiebreak_order": 1}, TiebreakOrderTaken),
    ],
)
def test_casos_de_uso_recusam_unicidade_antes_da_gravacao(admin, fields, error):
    existing = CriterionFactory(name="Existente", tiebreak_order=1)
    target = CriterionFactory(edition=existing.edition)
    criteria = (
        Criterion.objects.filter(edition=existing.edition).order_by("pk").values()
    )
    before = list(criteria)
    with pytest.raises(error):
        create_criterion(actor=admin, edition=existing.edition, **fields)
    assert list(criteria.all()) == before
    with pytest.raises(error):
        update_criterion(actor=admin, criterion=target, **fields)
    assert list(criteria.all()) == before


def test_atualizar_criterio_com_avaliacao_preserva_registro(admin):
    criterion = CriterionFactory()
    link = StageCriterionFactory(criterion=criterion, stage__edition=criterion.edition)
    EvaluationFactory(stage=link.stage)
    before = Criterion.objects.values().get(pk=criterion.pk)
    with pytest.raises(CriterionInUseByEvaluations):
        update_criterion(actor=admin, criterion=criterion, name="Novo")
    assert Criterion.objects.values().get(pk=criterion.pk) == before


def test_excluir_criterio_vinculado_preserva_registro(admin):
    criterion = CriterionFactory()
    link = StageCriterionFactory(criterion=criterion, stage__edition=criterion.edition)
    before = Criterion.objects.values().get(pk=criterion.pk)
    link_before = type(link).objects.values().get(pk=link.pk)
    with pytest.raises(CriterionLinkedToStage):
        delete_criterion(actor=admin, criterion=criterion)
    assert Criterion.objects.values().get(pk=criterion.pk) == before
    assert type(link).objects.values().get(pk=link.pk) == link_before
