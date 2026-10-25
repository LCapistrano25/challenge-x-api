import pytest
from django.core.exceptions import ValidationError
from rest_framework.test import APIRequestFactory

from apps.accounts.enums import UserRole
from apps.accounts.factories import (
    ExternalReviewerFactory,
    StudentFactory,
    TeacherFactory,
    UserFactory,
)
from apps.accounts.models import ExternalReviewer, Teacher, User
from apps.accounts.permissions import IsAdmin, IsExternalReviewer, IsStudent, IsTeacher

pytestmark = pytest.mark.django_db


def allowed(permission, user):
    request = APIRequestFactory().get("/")
    request.user = user
    return permission().has_permission(request, None)


# 1. Papel ADMIN <=> acesso ao painel


def test_papel_admin_da_acesso_ao_painel():
    user = UserFactory(role=UserRole.ADMIN)
    assert user.is_staff and user.is_superuser


def test_outro_papel_nao_entra_no_painel_mesmo_marcado():
    user = User.objects.create_user(
        "a@teste.com", "x", role=UserRole.STUDENT, is_staff=True
    )
    assert not user.is_staff and not user.is_superuser


def test_trocar_papel_com_update_fields_sincroniza_o_acesso():
    user = UserFactory(role=UserRole.ADMIN)
    user.role = UserRole.TEACHER
    user.save(update_fields=["role"])
    user.refresh_from_db()
    assert not user.is_staff and not user.is_superuser


def test_superusuario_precisa_ser_admin():
    with pytest.raises(ValueError, match="ADMIN"):
        User.objects.create_superuser("s@teste.com", "x", role=UserRole.STUDENT)


# 2. Permissões exigem papel e perfil


@pytest.mark.parametrize(
    ("permission", "role", "profile_factory"),
    [
        (IsStudent, UserRole.STUDENT, StudentFactory),
        (IsTeacher, UserRole.TEACHER, TeacherFactory),
        (IsExternalReviewer, UserRole.EXTERNAL_REVIEWER, ExternalReviewerFactory),
    ],
)
def test_permissao_exige_papel_e_perfil(permission, role, profile_factory):
    assert not allowed(permission, UserFactory(role=role))  # papel sem perfil
    assert allowed(permission, profile_factory().user)


def test_admin_nao_precisa_de_perfil():
    assert allowed(IsAdmin, UserFactory(role=UserRole.ADMIN))


# 3. Admin cria o perfil e não deixa trocar o papel de quem já tem


@pytest.fixture
def admin_client(client):
    client.force_login(UserFactory(role=UserRole.ADMIN))
    return client


def add_user(admin_client, email, role):
    return admin_client.post(
        "/admin/accounts/user/add/",
        {
            "email": email,
            "name": "Pessoa",
            "role": role,
            "password1": "TesteForte!2026x",
            "password2": "TesteForte!2026x",
            "is_active": "on",
        },
        HTTP_HOST="localhost",
    )


@pytest.mark.parametrize(
    ("role", "profile"),
    [(UserRole.TEACHER, Teacher), (UserRole.EXTERNAL_REVIEWER, ExternalReviewer)],
)
def test_admin_cria_o_perfil_junto_com_o_usuario(admin_client, role, profile):
    response = add_user(admin_client, "novo@teste.com", role)
    assert response.status_code == 302
    assert profile.objects.filter(user__email="novo@teste.com").exists()


def test_admin_avisa_para_completar_o_aluno(admin_client):
    response = add_user(admin_client, "aluno@teste.com", UserRole.STUDENT)
    assert response.status_code == 302
    messages = [str(m) for m in response.wsgi_request._messages]
    assert any("Acadêmicos" in m for m in messages)


def test_papel_de_quem_tem_perfil_nao_pode_ser_trocado():
    user = TeacherFactory().user
    user.role = UserRole.STUDENT
    with pytest.raises(ValidationError, match="já tem perfil"):
        user.full_clean()


def test_papel_de_quem_nao_tem_perfil_pode_ser_trocado():
    user = UserFactory(role=UserRole.STUDENT)
    user.role = UserRole.TEACHER
    user.full_clean()
