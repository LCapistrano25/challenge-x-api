from django.db import IntegrityError
from django.test import TestCase

from apps.accounts.enums import UserRole
from apps.accounts.models import EmailDomain, User


class UserManagerTests(TestCase):
    def test_create_user_normaliza_email(self):
        user = User.objects.create_user(
            "Aluno@Aluno.Unicatolica.edu.br", "TesteForte!2026x"
        )

        self.assertEqual(user.email, "aluno@aluno.unicatolica.edu.br")
        self.assertTrue(user.check_password("TesteForte!2026x"))

    def test_create_superuser_e_admin(self):
        user = User.objects.create_superuser("admin@teste.com", "TesteForte!2026x")

        self.assertEqual(user.role, UserRole.ADMIN)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_role_comporta_external_reviewer(self):
        user = User.objects.create_user(
            "avaliador@empresa.com",
            "TesteForte!2026x",
            role=UserRole.EXTERNAL_REVIEWER,
        )

        user.refresh_from_db()
        self.assertEqual(user.role, UserRole.EXTERNAL_REVIEWER)


class ConstraintTests(TestCase):
    def test_email_unico(self):
        User.objects.create_user("a@teste.com", "x")

        with self.assertRaises(IntegrityError):
            User.objects.create_user("a@teste.com", "x")

    def test_dominio_unico(self):
        EmailDomain.objects.create(name="teste.edu.br", role=UserRole.STUDENT)

        with self.assertRaises(IntegrityError):
            EmailDomain.objects.create(name="teste.edu.br", role=UserRole.TEACHER)
