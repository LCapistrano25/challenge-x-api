import pytest
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from apps.accounts.enums import UserRole
from apps.core.factories import CourseFactory
from apps.core.models import Course
from apps.core.use_cases.create_course import create_course
from rest_framework.test import APIClient
from rest_framework import status

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


# --- Testes de API (Endpoints) ---

@pytest.fixture
def api_client():
    """Fornece um cliente HTTP para simularmos pedidos à API."""
    return APIClient()

@pytest.mark.django_db
def test_api_create_course_success(api_client, admin_user):
    """Testa se o endpoint devolve 201 Created quando os dados estão corretos."""
    api_client.force_authenticate(user=admin_user)
    
    response = api_client.post("/api/admin/courses", {
        "name": "Sistemas de Informação",
        "term_count": 8
    }, format="json")
    
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["name"] == "Sistemas de Informação"

@pytest.mark.django_db
def test_api_create_course_forbidden(api_client, normal_user):
    """Testa se o endpoint devolve 403 Forbidden para utilizadores sem permissão de admin."""
    api_client.force_authenticate(user=normal_user)
    
    response = api_client.post("/api/admin/courses", {
        "name": "História",
        "term_count": 8
    }, format="json")
    
    assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.django_db
def test_api_create_course_bad_request(api_client, admin_user):
    """Testa se o endpoint devolve 400 Bad Request ao violar regras de negócio."""
    api_client.force_authenticate(user=admin_user)
    
    # 12 períodos é inválido (a regra dita 8 ou 10)
    response = api_client.post("/api/admin/courses", {
        "name": "Letras",
        "term_count": 12
    }, format="json")
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_api_list_courses_admin(api_client, admin_user):
    """Testa se o admin consegue listar os cursos no endpoint GET."""
    api_client.force_authenticate(user=admin_user)
    
    from apps.core.models import Course
    Course.objects.all().delete() # Limpa sujeira de outros testes
    Course.objects.create(name="Arquitetura", term_count=10)
    
    response = api_client.get("/api/admin/courses")
    
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]["name"] == "Arquitetura"

@pytest.mark.django_db
def test_api_update_course_admin(api_client, admin_user):
    """Testa se o admin consegue atualizar o nome e os períodos de um curso via PATCH."""
    api_client.force_authenticate(user=admin_user)
    
    from apps.core.models import Course
    # 1. Limpa o banco de testes para evitar conflito de nomes
    Course.objects.all().delete()
    
    # 2. Cria um curso para podermos editar
    course = Course.objects.create(name="Direito", term_count=10)
    
    # 3. Faz o pedido PATCH para alterar o nome e os períodos
    response = api_client.patch(f"/api/admin/courses/{course.id}", {
        "name": "Direito Internacional",
        "term_count": 8
    }, format="json")
    
    # 4. Verifica se deu 200 OK e se os dados mudaram
    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == "Direito Internacional"
    assert response.data["term_count"] == 8

@pytest.mark.django_db
def test_api_delete_course_success(api_client, admin_user):
    """Testa se o admin consegue excluir um curso sem vínculos (204 No Content)."""
    api_client.force_authenticate(user=admin_user)
    
    from apps.core.models import Course
    Course.objects.all().delete()
    
    # Cria um curso isolado, sem professores nem projetos
    course = Course.objects.create(name="Filosofia", term_count=8)
    
    # Faz o pedido DELETE
    response = api_client.delete(f"/api/admin/courses/{course.id}")
    
    # Verifica se a API devolveu 204 No Content
    assert response.status_code == status.HTTP_204_NO_CONTENT
    # Verifica se o curso realmente sumiu do banco de dados
    assert Course.objects.count() == 0