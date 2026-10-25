from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.accounts.enums import UserRole
from apps.accounts.models import ExternalReviewer, Student, Teacher, User


@override_settings(DEBUG=True)
class SeedUsersTests(TestCase):
    def test_cria_um_usuario_de_cada_perfil(self):
        call_command("seed_users", password="TesteForte!2026x", stdout=None)
        call_command("seed_users", password="TesteForte!2026x", stdout=None)

        self.assertEqual(
            sorted(User.objects.values_list("role", flat=True)), sorted(UserRole.values)
        )
        self.assertEqual(Student.objects.count(), 1)
        self.assertEqual(Teacher.objects.get().courses.count(), 1)
        self.assertEqual(ExternalReviewer.objects.count(), 1)

    def test_login_do_aluno_do_seed(self):
        call_command("seed_users", password="TesteForte!2026x", stdout=None)

        resposta = self.client.post(
            "/api/auth/login",
            {"email": "aluno@aluno.desafiox.local", "senha": "TesteForte!2026x"},
            content_type="application/json",
            HTTP_HOST="localhost",
        )

        self.assertEqual(resposta.status_code, 200)

    @override_settings(DEBUG=False)
    def test_recusa_fora_do_modo_debug(self):
        with self.assertRaises(CommandError):
            call_command("seed_users", password="x", stdout=None)
