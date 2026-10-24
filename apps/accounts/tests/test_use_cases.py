from unittest.mock import patch

from django.test import TestCase

from apps.accounts.enums import UserRole
from apps.accounts.models import EmailDomain, User
from apps.accounts.rules import (
    DomainRoleMismatch,
    InvalidEmailDomain,
    ensure_institutional_domain,
)
from apps.accounts.use_cases.register_student import (
    RegistrationRejected,
    register_student,
)


class RegisterStudentTests(TestCase):
    def test_cadastro_simultaneo_vira_rejeicao_e_nao_erro_500(self):
        EmailDomain.objects.create(name="aluno.edu.br", role=UserRole.STUDENT)
        User.objects.create_user("ana@aluno.edu.br", "x", registration_number="1")

        # Simula a corrida: a checagem de duplicidade não vê o outro cadastro.
        with (
            patch.object(User.objects, "filter") as filter_,
            self.assertRaises(RegistrationRejected),
        ):
            filter_.return_value.exists.return_value = False
            register_student(
                email="ana@aluno.edu.br",
                password="TesteForte!2026x",
                registration_number="2",
                course="ES",
                term=1,
                confirmation_url="http://testserver/confirm",
            )

        self.assertEqual(User.objects.count(), 1)


class EnsureInstitutionalDomainTests(TestCase):
    def test_aceita_dominio_do_perfil(self):
        EmailDomain.objects.create(
            name="professor.unicatolica.edu.br",
            active=True,
            role=UserRole.TEACHER,
        )

        ensure_institutional_domain(
            "Docente@Professor.Unicatolica.edu.br", UserRole.TEACHER
        )

    def test_rejeita_dominio_de_outro_perfil(self):
        EmailDomain.objects.create(
            name="professor.unicatolica.edu.br",
            active=True,
            role=UserRole.TEACHER,
        )

        with self.assertRaises(DomainRoleMismatch):
            ensure_institutional_domain(
                "docente@professor.unicatolica.edu.br", UserRole.STUDENT
            )

    def test_rejeita_dominio_inexistente(self):
        with self.assertRaises(InvalidEmailDomain):
            ensure_institutional_domain("usuario@gmail.com", UserRole.STUDENT)

    def test_rejeita_dominio_desativado(self):
        EmailDomain.objects.create(
            name="professor.unicatolica.edu.br",
            active=False,
            role=UserRole.TEACHER,
        )

        with self.assertRaises(InvalidEmailDomain):
            ensure_institutional_domain(
                "docente@professor.unicatolica.edu.br", UserRole.TEACHER
            )
