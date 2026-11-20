import importlib

import pytest
from django.apps import apps as django_apps
from django.core.exceptions import ValidationError

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import (
    EmailDomainNotFound,
    EmailDomainTaken,
    NotAdminActor,
)
from apps.accounts.factories import EmailDomainFactory, UserFactory
from apps.accounts.models import EmailDomain
from apps.accounts.selectors import list_email_domains
from apps.accounts.use_cases.create_email_domain import create_email_domain
from apps.accounts.use_cases.update_email_domain import update_email_domain

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin():
    return UserFactory(role=UserRole.ADMIN)


# UC02 — Configurar domínios institucionais (RF02, RN02)


def test_admin_cadastra_dominio_normalizado(admin):
    domain = create_email_domain(
        actor=admin,
        name=" A.Catolica-TO.edu.br ",
        role=UserRole.STUDENT,
    )

    assert domain.name == "a.catolica-to.edu.br"
    assert domain.role == UserRole.STUDENT
    assert domain.active is True


def test_nao_admin_nao_cadastra_nem_edita_dominio():
    student = UserFactory(role=UserRole.STUDENT)
    domain = EmailDomainFactory()

    with pytest.raises(NotAdminActor):
        create_email_domain(actor=student, name="novo.edu.br", role=UserRole.STUDENT)

    with pytest.raises(NotAdminActor):
        update_email_domain(actor=student, domain_id=domain.pk, active=False)


@pytest.mark.parametrize(
    "invalid_name",
    ["", "   ", "@aluno.edu.br", "localhost", "-a.edu.br", "a b.edu.br"],
)
def test_recusa_dominio_invalido_no_cadastro(admin, invalid_name):
    with pytest.raises(ValidationError):
        create_email_domain(actor=admin, name=invalid_name, role=UserRole.STUDENT)


@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.EXTERNAL_REVIEWER])
def test_recusa_perfil_nao_institucional(admin, role):
    with pytest.raises(ValidationError):
        create_email_domain(actor=admin, name="inst.edu.br", role=role)


def test_recusa_dominio_duplicado_case_insensitive(admin):
    create_email_domain(actor=admin, name="a.catolica-to.edu.br", role=UserRole.STUDENT)

    with pytest.raises(EmailDomainTaken):
        create_email_domain(
            actor=admin, name=" A.CATOLICA-TO.EDU.BR ", role=UserRole.TEACHER
        )


def test_admin_edita_e_desativa_dominio(admin):
    domain = EmailDomainFactory(
        name="antigo.edu.br", role=UserRole.STUDENT, active=True
    )

    updated = update_email_domain(
        actor=admin,
        domain_id=domain.pk,
        name="Novo.EDU.BR",
        role=UserRole.TEACHER,
        active=False,
    )

    assert updated.name == "novo.edu.br"
    assert updated.role == UserRole.TEACHER
    assert updated.active is False


def test_editar_para_mesmo_nome_e_permitido(admin):
    domain = EmailDomainFactory(name="mesmo.edu.br", role=UserRole.STUDENT)

    updated = update_email_domain(actor=admin, domain_id=domain.pk, name="MESMO.edu.br")

    assert updated.name == "mesmo.edu.br"


def test_recusa_editar_para_nome_de_outro_dominio(admin):
    EmailDomainFactory(name="existente.edu.br", role=UserRole.STUDENT)
    domain = EmailDomainFactory(name="outro.edu.br", role=UserRole.TEACHER)

    with pytest.raises(EmailDomainTaken):
        update_email_domain(actor=admin, domain_id=domain.pk, name="EXISTENTE.edu.br")


def test_recusa_editar_dominio_inexistente(admin):
    with pytest.raises(EmailDomainNotFound):
        update_email_domain(actor=admin, domain_id=999999, active=False)


def test_list_email_domains_filtra_por_ativo_e_perfil():
    d1 = EmailDomainFactory(name="b.edu.br", role=UserRole.STUDENT, active=True)
    d2 = EmailDomainFactory(name="a.edu.br", role=UserRole.TEACHER, active=False)

    assert list(list_email_domains()) == [d2, d1]
    assert list(list_email_domains(active=True)) == [d1]
    assert list(list_email_domains(role=UserRole.TEACHER)) == [d2]


def test_migracao_passa_nomes_antigos_para_minusculas():
    migration = importlib.import_module(
        "apps.accounts.migrations.0005_emaildomain_unique_email_domain_name_ci"
    )
    domain = EmailDomainFactory(name="x.edu.br")
    # update() ignora o save() que normaliza: simula o dado antigo do admin.
    EmailDomain.objects.filter(pk=domain.pk).update(name="Mixed.EDU.br")

    migration.lowercase_domain_names(django_apps, None)

    domain.refresh_from_db()
    assert domain.name == "mixed.edu.br"


def test_migracao_para_com_mensagem_se_ha_dominios_repetidos_na_caixa():
    migration = importlib.import_module(
        "apps.accounts.migrations.0005_emaildomain_unique_email_domain_name_ci"
    )

    class Domain:
        def __init__(self, name):
            self.name = name

        def save(self, **_):
            pass

    class FakeModel:
        # A constraint nova impede criar o par no banco de teste.
        objects = type(
            "Manager",
            (),
            {"order_by": lambda self, *_: [Domain("A.edu.br"), Domain("a.edu.br")]},
        )()

    fake_apps = type("Apps", (), {"get_model": lambda self, *_: FakeModel})()

    with pytest.raises(RuntimeError, match="Domínios repetidos"):
        migration.lowercase_domain_names(fake_apps, None)
