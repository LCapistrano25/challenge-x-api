from django.test import TestCase

from apps.accounts.enums import UserRole
from apps.accounts.models import EmailDomain
from apps.accounts.rules import (
    DomainRoleMismatch,
    InvalidEmailDomain,
    ensure_institutional_domain,
)


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
