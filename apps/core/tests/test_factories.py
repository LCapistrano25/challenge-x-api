import pytest

from apps.core.factories import CourseFactory, SdgFactory

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("factory", [CourseFactory, SdgFactory])
def test_factory_gera_registro_valido(factory):
    factory().full_clean()


def test_sdg_reaproveita_ods_do_seed():
    assert SdgFactory(number=9).title == "Indústria, Inovação e Infraestrutura"
