import pytest
from django.test import TestCase
from rest_framework.test import APIClient, APIRequestFactory

from apps.accounts.enums import UserRole
from apps.accounts.factories import (
    EmailDomainFactory,
    ExternalReviewerFactory,
    StudentFactory,
    TeacherFactory,
    UserFactory,
)
from apps.accounts.models import Student, User
from apps.accounts.permissions import IsAdmin, IsStudent, IsTeacher
from apps.core.models import Course
from apps.editions.enums import EditionStatus
from apps.editions.factories import EditionFactory
from apps.editions.models import EditionReviewer

# POST /api/auth/sessions/password: só administrador e avaliador externo (RF01, RF41)

LOGIN_URL = "/api/auth/sessions/password"
PASSWORD = "TesteForte!2026x"


def login(email, password=PASSWORD):
    client = APIClient()
    resposta = client.post(
        LOGIN_URL, {"email": email, "password": password}, format="json"
    )
    return client, resposta


def reviewer_in_edition(status=EditionStatus.PUBLISHED):
    reviewer = ExternalReviewerFactory()
    EditionReviewer.objects.create(
        edition=EditionFactory(status=status), reviewer=reviewer
    )
    return reviewer.user


@pytest.mark.django_db
def test_admin_entra_com_senha():
    admin = UserFactory(role=UserRole.ADMIN)

    client, resposta = login(admin.email)

    assert resposta.status_code == 200
    assert "_auth_user_id" in client.session


@pytest.mark.django_db
def test_avaliador_vinculado_a_edicao_vigente_entra():
    client, resposta = login(reviewer_in_edition().email)

    assert resposta.status_code == 200
    assert "_auth_user_id" in client.session


@pytest.mark.django_db
@pytest.mark.parametrize("status", [None, EditionStatus.CLOSED])
def test_avaliador_fora_da_edicao_vigente_nao_entra(status):
    user = (
        ExternalReviewerFactory().user
        if status is None
        else reviewer_in_edition(status)
    )

    client, resposta = login(user.email)

    assert resposta.status_code == 403
    assert resposta.data["error"]["code"] == "reviewer_not_in_current_edition"
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
@pytest.mark.parametrize("factory", [StudentFactory, TeacherFactory])
def test_aluno_e_professor_nao_entram_com_senha(factory):
    # Os dois entram pela Microsoft; a resposta não revela o motivo.
    client, resposta = login(factory().user.email)

    assert resposta.status_code == 401
    assert resposta.data["error"]["code"] == "invalid_credentials"
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_conta_inativa_recebe_o_mesmo_401():
    inativo = UserFactory(role=UserRole.ADMIN, is_active=False)

    client, resposta = login(inativo.email)

    assert resposta.status_code == 401
    assert resposta.data["error"]["code"] == "invalid_credentials"


@pytest.mark.django_db
def test_senha_incorreta_recebe_o_mesmo_401():
    admin = UserFactory(role=UserRole.ADMIN)

    client, resposta = login(admin.email, "SenhaErrada!2026")

    assert resposta.status_code == 401
    assert resposta.data["error"]["code"] == "invalid_credentials"


@pytest.mark.django_db
def test_login_sem_campos_detalha_a_validacao():
    client = APIClient()

    resposta = client.post(LOGIN_URL, {}, format="json")

    assert resposta.status_code == 400
    assert resposta.data["error"]["code"] == "validation_error"
    assert set(resposta.data["error"]["details"]) == {"email", "password"}


class PermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.admin = User.objects.create_user(
            email="admin@teste.com",
            password="TesteForte!2026x",
            role=UserRole.ADMIN,
            is_active=True,
        )

        # As permissões exigem o perfil, não só o papel.
        self.academico = StudentFactory().user
        self.professor = TeacherFactory().user

    def test_is_admin(self):
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = self.admin

        self.assertTrue(IsAdmin().has_permission(request, None))

    def test_is_academico(self):
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = self.academico

        self.assertTrue(IsStudent().has_permission(request, None))

    def test_is_professor(self):
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = self.professor

        self.assertTrue(IsTeacher().has_permission(request, None))

    def test_academico_nao_pode_ser_admin(self):
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = self.academico

        self.assertFalse(IsAdmin().has_permission(request, None))

    def test_professor_nao_pode_ser_admin(self):
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = self.professor

        self.assertFalse(IsAdmin().has_permission(request, None))

    def test_academico_nao_pode_ser_professor(self):
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = self.academico

        self.assertFalse(IsTeacher().has_permission(request, None))


class SessionTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.enforce_csrf_checks = True

        self.usuario = User.objects.create_user(
            email="sessao@teste.com",
            password="TesteForte!2026x",
            role=UserRole.ADMIN,
            is_active=True,
            is_staff=True,
            is_superuser=True,
            email_confirmed=True,
        )

    def test_login_cria_sessao_real(self):
        resposta_csrf = self.client.get("/api/auth/csrf")
        self.assertEqual(resposta_csrf.status_code, 200)

        token = resposta_csrf.data["csrfToken"]

        resposta = self.client.post(
            LOGIN_URL,
            {
                "email": "sessao@teste.com",
                "password": "TesteForte!2026x",
            },
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data["perfil"], UserRole.ADMIN)
        self.assertIn("_auth_user_id", self.client.session)

        resposta_me = self.client.get("/api/auth/me")
        self.assertEqual(resposta_me.status_code, 200)
        self.assertEqual(resposta_me.data["perfil"], UserRole.ADMIN)

    def test_login_logout_nos_perfis_com_senha(self):
        usuarios = [
            (self.usuario, "TesteForte!2026x", UserRole.ADMIN),
            (reviewer_in_edition(), "TesteForte!2026x", UserRole.EXTERNAL_REVIEWER),
        ]

        for usuario, senha, perfil in usuarios:
            with self.subTest(role=perfil):
                resposta_csrf = self.client.get("/api/auth/csrf")
                token = resposta_csrf.data["csrfToken"]

                resposta_login = self.client.post(
                    LOGIN_URL,
                    {"email": usuario.email, "password": senha},
                    format="json",
                    HTTP_X_CSRFTOKEN=token,
                )

                self.assertEqual(resposta_login.status_code, 200)
                self.assertEqual(resposta_login.data["perfil"], perfil)
                self.assertIn("_auth_user_id", self.client.session)

                resposta_me = self.client.get("/api/auth/me")
                self.assertEqual(resposta_me.status_code, 200)
                self.assertEqual(resposta_me.data["perfil"], perfil)

                resposta_csrf = self.client.get("/api/auth/csrf")
                token = resposta_csrf.data["csrfToken"]

                resposta_logout = self.client.post(
                    "/api/auth/logout",
                    {},
                    format="json",
                    HTTP_X_CSRFTOKEN=token,
                )

                self.assertEqual(resposta_logout.status_code, 204)
                self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_sem_csrf_e_bloqueado(self):
        resposta = self.client.post(
            LOGIN_URL,
            {
                "email": "sessao@teste.com",
                "password": "TesteForte!2026x",
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, 403)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_me_sem_autenticacao(self):
        resposta = self.client.get("/api/auth/me")
        self.assertIn(resposta.status_code, [401, 403])

    def test_logout_sem_csrf_e_bloqueado(self):
        self.client.force_login(self.usuario)

        resposta = self.client.post(
            "/api/auth/logout",
            {},
            format="json",
        )

        self.assertEqual(resposta.status_code, 403)
        self.assertIn("_auth_user_id", self.client.session)

    def test_logout_com_csrf_valido(self):
        self.client.force_login(self.usuario)

        resposta_csrf = self.client.get("/api/auth/csrf")
        self.assertEqual(resposta_csrf.status_code, 200)

        token = resposta_csrf.data["csrfToken"]

        resposta = self.client.post(
            "/api/auth/logout",
            {},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(resposta.status_code, 204)
        self.assertNotIn("_auth_user_id", self.client.session)

        resposta_me = self.client.get("/api/auth/me")
        self.assertIn(resposta_me.status_code, [401, 403])

    def test_logout_com_csrf_invalido(self):
        self.client.force_login(self.usuario)

        resposta = self.client.post(
            "/api/auth/logout",
            {},
            format="json",
            HTTP_X_CSRFTOKEN="token-invalido",
        )

        self.assertEqual(resposta.status_code, 403)
        self.assertIn("_auth_user_id", self.client.session)

    def test_logout_sem_autenticacao(self):
        resposta = self.client.post("/api/auth/logout")
        self.assertIn(resposta.status_code, [401, 403])

    def test_sessao_tem_expiracao_de_30_minutos(self):
        self.client.force_login(self.usuario)

        sessao = self.client.session

        self.assertEqual(sessao.get_expiry_age(), 1800)

    def test_requisicao_renova_sessao(self):
        self.client.force_login(self.usuario)

        idade_antes = self.client.session.get_expiry_age()

        resposta = self.client.get("/api/auth/me")

        self.assertEqual(resposta.status_code, 200)

        idade_depois = self.client.session.get_expiry_age()

        self.assertEqual(idade_antes, 1800)
        self.assertEqual(idade_depois, 1800)


# POST /api/auth/students: autocadastro do aluno autenticado (RF19)

STUDENTS_URL = "/api/auth/students"


@pytest.fixture
def course(db):
    return Course.objects.get(name="Engenharia de Software")  # 8 períodos


@pytest.fixture
def aluno(db):
    EmailDomainFactory(name="aluno.edu.br", role=UserRole.STUDENT)
    return UserFactory(email="ana@aluno.edu.br", role=UserRole.STUDENT)


@pytest.fixture
def client(aluno):
    client = APIClient()
    client.force_authenticate(aluno)
    return client


@pytest.fixture
def post(client, course):
    def call(**fields):
        data = {
            "registration_number": "202600123",
            "course_id": course.pk,
            "term": 4,
            **fields,
        }
        return client.post(STUDENTS_URL, data, format="json")

    return call


def test_autocadastro_cria_perfil_e_devolve_user_id(post, aluno):
    resposta = post()

    assert resposta.status_code == 201
    assert resposta.data == {"student": {"user_id": aluno.pk}}
    student = Student.objects.get(user=aluno)
    assert (student.registration_number, student.term) == ("202600123", 4)


def test_autocadastro_sem_login_e_recusado(post, client):
    client.force_authenticate(None)

    resposta = post()

    assert resposta.status_code == 403
    assert resposta.data["error"]["code"] == "not_authenticated"


def test_autocadastro_de_professor_e_recusado(post, client):
    client.force_authenticate(TeacherFactory().user)

    resposta = post()

    assert resposta.status_code == 403
    assert resposta.data["error"]["code"] == "permission_denied"


def test_autocadastro_de_quem_ja_tem_perfil_recebe_409(post):
    post()

    resposta = post(registration_number="202600999")

    assert resposta.status_code == 409
    assert resposta.data["error"]["code"] == "student_profile_exists"


def test_autocadastro_com_matricula_em_uso_recebe_409(post):
    StudentFactory(registration_number="202600123")

    resposta = post()

    assert resposta.status_code == 409
    assert resposta.data["error"]["code"] == "registration_number_taken"


def test_autocadastro_sem_campos_detalha_a_validacao(client, aluno):
    resposta = client.post(STUDENTS_URL, {}, format="json")

    assert resposta.status_code == 400
    assert resposta.data["error"]["code"] == "validation_error"
    assert set(resposta.data["error"]["details"]) == {
        "registration_number",
        "course_id",
        "term",
    }


def test_autocadastro_com_periodo_fora_do_curso_detalha_o_campo(post):
    resposta = post(term=9)

    assert resposta.status_code == 400
    assert resposta.data["error"]["code"] == "validation_error"
    assert "term" in resposta.data["error"]["details"]
    assert not Student.objects.exists()


def test_autocadastro_com_curso_inativo_recebe_400(post, course):
    course.active = False
    course.save()

    resposta = post()

    assert resposta.status_code == 400
    assert resposta.data["error"]["code"] == "registration_rejected"
    assert not Student.objects.exists()
