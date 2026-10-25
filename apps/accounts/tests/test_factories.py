import pytest

from apps.accounts.factories import (
    EmailDomainFactory,
    ExternalReviewerFactory,
    StudentFactory,
    TeacherCourseFactory,
    TeacherFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "factory",
    [
        UserFactory,
        EmailDomainFactory,
        StudentFactory,
        TeacherFactory,
        TeacherCourseFactory,
        ExternalReviewerFactory,
    ],
)
def test_factory_gera_registro_valido(factory):
    factory().full_clean()


def test_usuario_da_factory_tem_senha_utilizavel():
    assert UserFactory().check_password("TesteForte!2026x")
