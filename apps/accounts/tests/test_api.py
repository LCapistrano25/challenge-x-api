from datetime import timedelta
from unittest.mock import patch

from django.core import signing
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory

from apps.accounts.enums import UserRole
from apps.accounts.factories import StudentFactory, TeacherFactory
from apps.accounts.models import EmailDomain, ExternalReviewer, Student, User
from apps.accounts.permissions import IsAdmin, IsStudent, IsTeacher
from apps.accounts.use_cases.register_student import EMAIL_CONFIRMATION_SALT
from apps.core.models import Course


def es_id():
    return Course.objects.get(name="Engenharia de Software").pk


class LoginTests(TestCase):
    def test_login_com_dominio_desativado(self):
        EmailDomain.objects.create(
            name="aluno.unicatolica.edu.br",
            active=False,
            role=UserRole.STUDENT,
        )

        User.objects.create_user(
            email="aluno@aluno.unicatolica.edu.br",
            password="TesteForte!2026x",
            role=UserRole.STUDENT,
            is_active=True,
            email_confirmed=True,
        )

        resposta = self.client.post(
            "/api/auth/login",
            {
                "email": "aluno@aluno.unicatolica.edu.br",
                "senha": "TesteForte!2026x",
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(
            resposta.data["erro"],
            "Domínio institucional não autorizado.",
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_com_perfil_incompativel_com_dominio(self):
        EmailDomain.objects.create(
            name="aluno.unicatolica.edu.br",
            active=True,
            role=UserRole.STUDENT,
        )

        User.objects.create_user(
            email="professor@aluno.unicatolica.edu.br",
            password="TesteForte!2026x",
            role=UserRole.TEACHER,
            is_active=True,
        )

        resposta = self.client.post(
            "/api/auth/login",
            {
                "email": "professor@aluno.unicatolica.edu.br",
                "senha": "TesteForte!2026x",
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(
            resposta.data["erro"],
            "Perfil não autorizado para este domínio.",
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_com_campos_vazios(self):
        resposta = self.client.post(
            "/api/auth/login",
            {},
            format="json",
        )

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(
            resposta.data["erro"],
            "Informe e-mail e senha.",
        )

    def test_login_com_conta_inativa(self):
        User.objects.create_user(
            email="inativo@teste.com",
            password="TesteForte!2026x",
            role=UserRole.ADMIN,
            is_active=False,
        )

        resposta = self.client.post(
            "/api/auth/login",
            {
                "email": "inativo@teste.com",
                "senha": "TesteForte!2026x",
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, 401)
        self.assertNotIn("_auth_user_id", self.client.session)

    def setUp(self):
        self.client = APIClient()

        self.usuario = User.objects.create_user(
            email="teste@login.com",
            password="TesteForte!2026x",
            role=UserRole.ADMIN,
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )

    def test_login_com_email_nao_confirmado(self):
        EmailDomain.objects.create(
            name="a.catolica-to.edu.br",
            active=True,
            role=UserRole.STUDENT,
        )

        User.objects.create_user(
            email="aluno@a.catolica-to.edu.br",
            password="TesteForte!2026x",
            role=UserRole.STUDENT,
            is_active=True,
            email_confirmed=False,
        )

        resposta = self.client.post(
            "/api/auth/login",
            {
                "email": "aluno@a.catolica-to.edu.br",
                "senha": "TesteForte!2026x",
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, 403)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_com_senha_incorreta(self):
        resposta = self.client.post(
            "/api/auth/login",
            {
                "email": "teste@login.com",
                "senha": "SenhaErrada!2026",
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, 401)
        self.assertEqual(
            resposta.data["erro"],
            "Credenciais inválidas.",
        )

    def test_login_com_credenciais_validas(self):
        resposta = self.client.post(
            "/api/auth/login",
            {
                "email": "teste@login.com",
                "senha": "TesteForte!2026x",
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            resposta.data["email"],
            "teste@login.com",
        )
        self.assertTrue("_auth_user_id" in self.client.session)


class RegisterTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_cadastro_com_dominio_nao_autorizado(self):
        resposta = self.client.post(
            "/api/auth/register",
            {
                "email": "aluno@gmail.com",
                "senha": "TesteForte!2026x",
                "matricula": "TESTE001",
                "curso": es_id(),
                "periodo": 6,
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("erro", resposta.data)

    def test_cadastro_com_dominio_autorizado(self):
        EmailDomain.objects.create(
            name="aluno.unicatolica.edu.br",
            active=True,
            role=UserRole.STUDENT,
        )

        resposta = self.client.post(
            "/api/auth/register",
            {
                "email": "novo@aluno.unicatolica.edu.br",
                "senha": "TesteForte!2026x",
                "matricula": "TESTE002",
                "curso": es_id(),
                "periodo": 6,
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, 201)
        self.assertTrue(
            User.objects.filter(
                email="novo@aluno.unicatolica.edu.br",
                email_confirmed=False,
                is_active=False,
            ).exists()
        )
        usuario = User.objects.get(email="novo@aluno.unicatolica.edu.br")
        self.assertEqual(usuario.role, UserRole.STUDENT)
        self.assertEqual(usuario.student.registration_number, "TESTE002")

    def test_confirmacao_de_email_ativa_conta(self):
        usuario = User.objects.create_user(
            email="confirmar@aluno.unicatolica.edu.br",
            password="TesteForte!2026x",
            role=UserRole.STUDENT,
            is_active=False,
            email_confirmed=False,
        )
        cadastro = timezone.now() - timedelta(days=1)
        User.objects.filter(pk=usuario.pk).update(updated_at=cadastro)

        token = signing.dumps(
            {"user_id": usuario.pk},
            salt=EMAIL_CONFIRMATION_SALT,
        )

        resposta = self.client.get(
            "/api/auth/confirm-email",
            {"token": token},
        )

        self.assertEqual(resposta.status_code, 200)

        usuario.refresh_from_db()
        self.assertTrue(usuario.email_confirmed)
        self.assertTrue(usuario.is_active)
        self.assertGreater(usuario.updated_at, cadastro)

    def test_confirmacao_com_token_invalido(self):
        resposta = self.client.get(
            "/api/auth/confirm-email",
            {"token": "token-invalido"},
        )

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(
            resposta.data["erro"],
            "Token de confirmação inválido.",
        )

    def test_cadastro_com_dominio_desativado(self):
        EmailDomain.objects.create(
            name="aluno.unicatolica.edu.br",
            active=False,
            role=UserRole.STUDENT,
        )

        resposta = self.client.post(
            "/api/auth/register",
            {
                "email": "bloqueado@aluno.unicatolica.edu.br",
                "senha": "TesteForte!2026x",
                "matricula": "TESTE004",
                "curso": es_id(),
                "periodo": 6,
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(
            User.objects.filter(email="bloqueado@aluno.unicatolica.edu.br").exists()
        )

    def test_cadastro_com_matricula_duplicada(self):
        EmailDomain.objects.create(
            name="aluno.unicatolica.edu.br",
            active=True,
            role=UserRole.STUDENT,
        )

        existente = User.objects.create_user(
            email="existente@aluno.unicatolica.edu.br",
            password="TesteForte!2026x",
            role=UserRole.STUDENT,
        )
        Student.objects.create(
            user=existente, registration_number="TESTE005", course_id=es_id(), term=6
        )

        resposta = self.client.post(
            "/api/auth/register",
            {
                "email": "outro@aluno.unicatolica.edu.br",
                "senha": "TesteForte!2026x",
                "matricula": "TESTE005",
                "curso": es_id(),
                "periodo": 6,
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(User.objects.count(), 1)

    def test_cadastro_com_periodo_invalido(self):
        EmailDomain.objects.create(
            name="aluno.unicatolica.edu.br",
            active=True,
            role=UserRole.STUDENT,
        )

        resposta = self.client.post(
            "/api/auth/register",
            {
                "email": "periodo@aluno.unicatolica.edu.br",
                "senha": "TesteForte!2026x",
                "matricula": "TESTE006",
                "curso": es_id(),
                "periodo": 0,
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(
            User.objects.filter(email="periodo@aluno.unicatolica.edu.br").exists()
        )

    def test_cadastro_com_email_duplicado(self):
        EmailDomain.objects.create(
            name="aluno.unicatolica.edu.br",
            active=True,
            role=UserRole.STUDENT,
        )

        User.objects.create_user(
            email="existente@aluno.unicatolica.edu.br",
            password="TesteForte!2026x",
            role=UserRole.STUDENT,
        )

        resposta = self.client.post(
            "/api/auth/register",
            {
                "email": "EXISTENTE@aluno.unicatolica.edu.br",
                "senha": "TesteForte!2026x",
                "matricula": "TESTE009",
                "curso": es_id(),
                "periodo": 6,
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(User.objects.count(), 1)

    def test_login_logo_apos_cadastro_pede_confirmacao(self):
        EmailDomain.objects.create(
            name="aluno.unicatolica.edu.br",
            active=True,
            role=UserRole.STUDENT,
        )
        dados = {
            "email": "novo@aluno.unicatolica.edu.br",
            "senha": "TesteForte!2026x",
        }
        self.client.post(
            "/api/auth/register",
            {**dados, "matricula": "TESTE010", "curso": es_id(), "periodo": 1},
            format="json",
        )

        resposta = self.client.post("/api/auth/login", dados, format="json")

        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(resposta.data["erro"], "Confirme seu e-mail antes de entrar.")
        self.assertNotIn("_auth_user_id", self.client.session)

        resposta = self.client.post(
            "/api/auth/login",
            {**dados, "senha": "SenhaErrada!2026"},
            format="json",
        )
        self.assertEqual(resposta.status_code, 401)


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
            "/api/auth/login",
            {
                "email": "sessao@teste.com",
                "senha": "TesteForte!2026x",
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

    def test_login_logout_nos_tres_perfis(self):
        EmailDomain.objects.create(
            name="aluno.unicatolica.edu.br",
            active=True,
            role=UserRole.STUDENT,
        )
        EmailDomain.objects.create(
            name="professor.unicatolica.edu.br",
            active=True,
            role=UserRole.TEACHER,
        )

        usuarios = [
            (
                self.usuario,
                "TesteForte!2026x",
                UserRole.ADMIN,
            ),
            (
                User.objects.create_user(
                    email="aluno@aluno.unicatolica.edu.br",
                    password="TesteForte!2026x",
                    role=UserRole.STUDENT,
                    is_active=True,
                    email_confirmed=True,
                ),
                "TesteForte!2026x",
                UserRole.STUDENT,
            ),
            (
                User.objects.create_user(
                    email="professor@professor.unicatolica.edu.br",
                    password="TesteForte!2026x",
                    role=UserRole.TEACHER,
                    is_active=True,
                    email_confirmed=True,
                ),
                "TesteForte!2026x",
                UserRole.TEACHER,
            ),
        ]

        for usuario, senha, perfil in usuarios:
            with self.subTest(role=perfil):
                resposta_csrf = self.client.get("/api/auth/csrf")
                token = resposta_csrf.data["csrfToken"]

                resposta_login = self.client.post(
                    "/api/auth/login",
                    {"email": usuario.email, "senha": senha},
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
            "/api/auth/login",
            {
                "email": "sessao@teste.com",
                "senha": "TesteForte!2026x",
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

    def test_confirmacao_com_token_expirado(self):
        usuario = User.objects.create_user(
            email="expirado@aluno.unicatolica.edu.br",
            password="TesteForte!2026x",
            role=UserRole.STUDENT,
            is_active=False,
            email_confirmed=False,
        )

        token = signing.dumps(
            {"user_id": usuario.pk},
            salt=EMAIL_CONFIRMATION_SALT,
        )

        # Simula um token com mais de 24 horas.
        with patch("apps.accounts.views.signing.loads") as mock_loads:
            mock_loads.side_effect = signing.SignatureExpired

            resposta = self.client.get(
                "/api/auth/confirm-email",
                {"token": token},
            )

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(
            resposta.data["erro"],
            "O link de confirmação expirou.",
        )

        usuario.refresh_from_db()
        self.assertFalse(usuario.email_confirmed)
        self.assertFalse(usuario.is_active)

    def test_confirmacao_de_email_ja_confirmado(self):
        usuario = User.objects.create_user(
            email="confirmado@aluno.unicatolica.edu.br",
            password="TesteForte!2026x",
            role=UserRole.STUDENT,
            is_active=True,
            email_confirmed=True,
        )

        token = signing.dumps(
            {"user_id": usuario.pk},
            salt=EMAIL_CONFIRMATION_SALT,
        )

        resposta = self.client.get(
            "/api/auth/confirm-email",
            {"token": token},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            resposta.data["mensagem"],
            "E-mail já confirmado.",
        )


class AdminAccessTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="admin@teste.com",
            password="TesteForte!2026x",
            role=UserRole.ADMIN,
            is_active=True,
            is_staff=True,
            is_superuser=True,
            email_confirmed=True,
        )
        self.academico = User.objects.create_user(
            email="aluno@teste.com",
            password="TesteForte!2026x",
            role=UserRole.STUDENT,
            is_active=True,
            email_confirmed=True,
        )
        self.professor = User.objects.create_user(
            email="professor@teste.com",
            password="TesteForte!2026x",
            role=UserRole.TEACHER,
            is_active=True,
            email_confirmed=True,
        )

    def test_admin_pode_acessar_rota(self):
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.get("/api/admin/teste-acesso")
        self.assertEqual(resposta.status_code, 200)

    def test_academico_nao_pode_acessar_rota(self):
        self.client.force_authenticate(user=self.academico)
        resposta = self.client.get("/api/admin/teste-acesso")
        self.assertEqual(resposta.status_code, 403)

    def test_professor_nao_pode_acessar_rota(self):
        self.client.force_authenticate(user=self.professor)
        resposta = self.client.get("/api/admin/teste-acesso")
        self.assertEqual(resposta.status_code, 403)

    def test_usuario_nao_autenticado_nao_pode_acessar_rota(self):
        resposta = self.client.get("/api/admin/teste-acesso")
        self.assertIn(resposta.status_code, [401, 403])


class LoginAuditTests(TestCase):
    """Correções da auditoria: e-mail, avaliador, conta pendente e força bruta."""

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=False)

    def login(self, email, senha="TesteForte!2026x"):
        return self.client.post(
            "/api/auth/login", {"email": email, "senha": senha}, format="json"
        )

    def test_email_com_maiuscula_do_admin_entra(self):
        EmailDomain.objects.create(name="prof.edu.br", role=UserRole.TEACHER)
        # O formulário do admin grava pelo save(), sem passar pelo create_user.
        user = User(email="Joao.Silva@Prof.edu.br", role=UserRole.TEACHER)
        user.set_password("TesteForte!2026x")
        user.save()
        TeacherFactory(user=user)

        self.assertEqual(user.email, "joao.silva@prof.edu.br")
        self.assertEqual(self.login("JOAO.SILVA@prof.edu.br").status_code, 200)

    def test_avaliador_externo_entra_sem_dominio_cadastrado(self):
        user = User.objects.create_user(
            "avaliador@empresa.com",
            "TesteForte!2026x",
            role=UserRole.EXTERNAL_REVIEWER,
        )
        ExternalReviewer.objects.create(user=user)

        self.assertEqual(self.login("avaliador@empresa.com").status_code, 200)

    def test_conta_pendente_pode_cadastrar_de_novo(self):
        EmailDomain.objects.create(name="aluno.edu.br", role=UserRole.STUDENT)
        dados = {
            "email": "ana@aluno.edu.br",
            "senha": "TesteForte!2026x",
            "curso": es_id(),
            "periodo": 1,
        }
        self.client.post(
            "/api/auth/register", {**dados, "matricula": "A1"}, format="json"
        )

        resposta = self.client.post(
            "/api/auth/register", {**dados, "matricula": "A2"}, format="json"
        )

        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(User.objects.filter(email="ana@aluno.edu.br").count(), 1)
        self.assertEqual(Student.objects.get().registration_number, "A2")

    def test_conta_confirmada_continua_recusada(self):
        EmailDomain.objects.create(name="aluno.edu.br", role=UserRole.STUDENT)
        StudentFactory(user__email="ana@aluno.edu.br", user__email_confirmed=True)

        resposta = self.client.post(
            "/api/auth/register",
            {
                "email": "ana@aluno.edu.br",
                "senha": "TesteForte!2026x",
                "matricula": "A3",
                "curso": es_id(),
                "periodo": 1,
            },
            format="json",
        )

        self.assertEqual(resposta.status_code, 400)

    def test_login_limita_tentativas_por_email(self):
        for _ in range(5):
            self.assertEqual(self.login("alvo@teste.com", "errada").status_code, 401)

        self.assertEqual(self.login("alvo@teste.com", "errada").status_code, 429)
        # Outro e-mail, mesmo IP: não é barrado (o campus sai por um IP só).
        self.assertEqual(self.login("outro@teste.com", "errada").status_code, 401)
