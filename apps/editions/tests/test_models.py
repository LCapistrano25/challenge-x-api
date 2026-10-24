from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.core.models import Course, Sdg
from apps.editions.enums import StageKind
from apps.editions.models import (
    Challenge,
    Criterion,
    Edition,
    EditionSdg,
    Stage,
    StageCriterion,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def edition():
    return Edition.objects.create(year=2026, semester=2)


def stage(edition, order=1, **fields):
    start = timezone.now()
    data = {
        "edition": edition,
        "order": order,
        "name": f"Etapa {order}",
        "kind": StageKind.SUBMISSION,
        "starts_at": start,
        "ends_at": start + timedelta(days=7),
        "max_score": Decimal("3.00"),
    }
    return Stage.objects.create(**{**data, **fields})


# Unicidades exigidas pela issue BM3


def test_edicao_unica_por_ano_e_semestre(edition):
    with pytest.raises(IntegrityError):
        Edition.objects.create(year=2026, semester=2)


def test_ods_unica_por_edicao(edition):
    sdg = Sdg.objects.get(number=9)
    EditionSdg.objects.create(edition=edition, sdg=sdg)
    with pytest.raises(IntegrityError):
        EditionSdg.objects.create(edition=edition, sdg=sdg)


def test_ordem_da_etapa_unica_por_edicao(edition):
    stage(edition, order=1)
    with pytest.raises(IntegrityError):
        stage(edition, order=1)


def test_criterio_unico_por_etapa(edition):
    etapa = stage(edition)
    criterio = Criterion.objects.create(edition=edition, name="Inovação")
    StageCriterion.objects.create(stage=etapa, criterion=criterio, max_score=1)
    with pytest.raises(IntegrityError):
        StageCriterion.objects.create(stage=etapa, criterion=criterio, max_score=1)


# Demais regras de integridade


@pytest.mark.parametrize("semester", [0, 3])
def test_semestre_so_1_ou_2(semester):
    with pytest.raises(IntegrityError):
        Edition.objects.create(year=2027, semester=semester)


def test_maximo_de_integrantes_nao_fica_abaixo_do_minimo():
    with pytest.raises(IntegrityError):
        Edition.objects.create(year=2027, semester=1, min_members=5, max_members=3)


def test_etapa_termina_depois_de_comecar(edition):
    agora = timezone.now()
    with pytest.raises(IntegrityError):
        stage(edition, starts_at=agora, ends_at=agora)


def test_etapa_pontuada_exige_valor(edition):
    with pytest.raises(IntegrityError):
        stage(edition, scored=True, max_score=None)


def test_etapa_de_formacao_sem_pontuacao(edition):
    assert stage(edition, kind=StageKind.FORMATION, scored=False, max_score=None).pk


def test_curso_pode_ter_varios_desafios_na_mesma_ods(edition):
    curso = Course.objects.get(name="Agronomia")
    sdg = Sdg.objects.get(number=9)
    for titulo in ("Desafio A", "Desafio B"):
        Challenge.objects.create(
            edition=edition, course=curso, sdg=sdg, title=titulo, description="."
        )
    assert Challenge.objects.filter(course=curso, sdg=sdg).count() == 2


# Validações do admin (full_clean)


def test_desafio_exige_ods_habilitada_na_edicao(edition):
    curso = Course.objects.get(name="Agronomia")
    sdg = Sdg.objects.get(number=9)
    desafio = Challenge(
        edition=edition, course=curso, sdg=sdg, title="Desafio", description="."
    )
    with pytest.raises(ValidationError, match="não está habilitada"):
        desafio.full_clean()

    EditionSdg.objects.create(edition=edition, sdg=sdg)
    desafio.full_clean()


def test_criterio_da_etapa_e_da_mesma_edicao(edition):
    outra = Edition.objects.create(year=2027, semester=1)
    criterio = Criterion.objects.create(edition=outra, name="Inovação")
    vinculo = StageCriterion(stage=stage(edition), criterion=criterio, max_score=1)
    with pytest.raises(ValidationError, match="outra edição"):
        vinculo.full_clean()
