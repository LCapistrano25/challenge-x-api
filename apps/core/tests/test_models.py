import pytest
from django.db import IntegrityError, connection

from apps.core.models import Course, Sdg

pytestmark = pytest.mark.django_db


def test_database_connection():
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        assert cursor.fetchone() == (1,)


def course(**fields):
    data = {"name": "Curso de Teste", "term_count": 8}
    return Course.objects.create(**{**data, **fields})


def test_course_name_unico():
    course()
    with pytest.raises(IntegrityError):
        course()


@pytest.mark.parametrize("term_count", [8, 10])
def test_course_aceita_8_ou_10_periodos(term_count):
    assert course(term_count=term_count).pk


@pytest.mark.parametrize("term_count", [0, 9, 12])
def test_course_recusa_outra_quantidade_de_periodos(term_count):
    with pytest.raises(IntegrityError):
        course(term_count=term_count)


def test_sdg_numero_unico():
    with pytest.raises(IntegrityError):
        Sdg.objects.create(number=9, title="Duplicada")


@pytest.mark.parametrize("number", [0, 18])
def test_sdg_recusa_numero_fora_de_1_a_17(number):
    with pytest.raises(IntegrityError):
        Sdg.objects.create(number=number, title="Inválida")


def test_seed_carrega_as_ods_da_edicao_2026():
    assert list(Sdg.objects.values_list("number", flat=True)) == [1, 2, 3, 9, 16]


def test_seed_carrega_os_cursos_da_unicatolica():
    assert Course.objects.count() == 15
    assert Course.objects.get(name="Direito").term_count == 10
    assert Course.objects.get(name="Engenharia de Software").term_count == 8
