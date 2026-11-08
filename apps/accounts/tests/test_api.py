from django.test import TestCase
from rest_framework.test import APIClient, APIRequestFactory

from apps.accounts.enums import UserRole
from apps.accounts.factories import StudentFactory, TeacherFactory
from apps.accounts.models import EmailDomain, User
from apps.accounts.permissions import IsAdmin, IsStudent, IsTeacher


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
            resposta.data["error"]["message"],
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
            resposta.data["error"]["message"],
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
        self.assertEqual(resposta.data["error"]["code"], "validation_error")
        self.assertEqual(set(resposta.data["error"]["details"]), {"email", "senha"})

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
            resposta.data["error"]["message"],
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
