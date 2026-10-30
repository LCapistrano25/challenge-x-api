import pytest
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from apps.accounts.enums import UserRole
from apps.core.factories import CourseFactory
from apps.core.models import Course
from apps.core.use_cases.create_course import create_course

User = get_user_model()


# --- Fixtures ---

@pytest.fixture
def admin_user():
    """Cria um utilizador administrador com o papel correto."""
    return User.objects.create_superuser(email="admin@teste.com")


@pytest.fixture
def normal_user():
    """Cria um utilizador estudante (sem permissão de admin)."""
    return User.objects.create_user(email="estudante@teste.com", role=UserRole.STUDENT)


# --- Testes ---

@pytest.mark.django_db
def test_create_course_success(admin_user):
    """Garante que um administrador consegue criar um curso com dados válidos."""
    course = create_course(actor=admin_user, name="Engenharia de Testes de Software", term_count=8)

    assert course.id is not None
    assert course.name == "Engenharia de Testes de Software"
    assert course.term_count == 8
    assert Course.objects.filter(name="Engenharia de Testes de Software").count() == 1


@pytest.mark.django_db
def test_create_course_fails_if_not_admin(normal_user):
    """Garante que utilizadores comuns não podem criar cursos."""
    with pytest.raises(PermissionError, match="Apenas administradores podem cadastrar cursos."):
        create_course(actor=normal_user, name="Ciência da Computação Inédita", term_count=8)


@pytest.mark.django_db
def test_create_course_fails_if_invalid_term_count(admin_user):
    """Garante que a regra de 8 ou 10 períodos é respeitada."""
    with pytest.raises(ValidationError, match="O curso deve ter exatamente 8 ou 10 períodos."):
        create_course(actor=admin_user, name="Curso Período Inválido", term_count=12)


@pytest.mark.django_db
def test_create_course_fails_if_name_exists(admin_user):
    """Garante que não é possível criar dois cursos com o mesmo nome."""
    CourseFactory(name="Curso Duplicado Super Exclusivo")

    with pytest.raises(ValidationError, match="Já existe um curso cadastrado com este nome."):
        create_course(actor=admin_user, name="Curso Duplicado Super Exclusivo", term_count=10)