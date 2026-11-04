import pytest
from django.core.exceptions import ValidationError

from apps.accounts.enums import UserRole
from apps.accounts.factories import UserFactory
from apps.editions import use_cases
from apps.editions.enums import EditionStatus
from apps.editions.exceptions import EditionAlreadyExists, NotAdminActor
from apps.editions.factories import EditionFactory
from apps.editions.models import Edition
from apps.editions.use_cases.create_edition import create_edition

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin():
    return UserFactory(role=UserRole.ADMIN)


# Cadastro de edição (UC18, RF47, RN05)


def test_cria_edicao_em_configuracao_com_limites_padrao(admin):
    edicao = create_edition(actor=admin, year=2030, semester=1, name="Desafio X 2030/1")

    edicao.refresh_from_db()
    assert (edicao.year, edicao.semester) == (2030, 1)
    assert edicao.name == "Desafio X 2030/1"
    assert edicao.status == EditionStatus.SETUP
    assert (edicao.min_members, edicao.max_members) == (3, 5)
    assert edicao.published_at is None
    assert edicao.closed_at is None


def test_nome_pode_ficar_vazio(admin):
    edicao = create_edition(actor=admin, year=2030, semester=2)
    assert edicao.name == ""


@pytest.mark.parametrize("semester", [1, 2])
def test_aceita_os_dois_semestres(admin, semester):
    assert create_edition(actor=admin, year=2030, semester=semester).pk


def test_mesmo_ano_com_outro_semestre_e_aceito(admin):
    EditionFactory(year=2030, semester=1)
    assert create_edition(actor=admin, year=2030, semester=2).pk


@pytest.mark.parametrize("semester", [0, 3, -1])
def test_semestre_invalido_e_recusado(admin, semester):
    with pytest.raises(ValidationError):
        create_edition(actor=admin, year=2030, semester=semester)
    assert not Edition.objects.filter(year=2030).exists()


def test_edicao_duplicada_e_recusada(admin):
    existente = EditionFactory()
    antes = Edition.objects.count()

    with pytest.raises(EditionAlreadyExists):
        create_edition(actor=admin, year=existente.year, semester=existente.semester)

    assert Edition.objects.count() == antes


def test_corrida_na_criacao_vira_edition_already_exists(admin, monkeypatch):
    # A checagem prévia não vê a edição (outra requisição ainda não tinha gravado
    # quando ela rodou); quem recusa é a unicidade do banco.
    monkeypatch.setattr(
        use_cases.create_edition,
        "ensure_edition_identification_is_free",
        lambda *a: None,
    )
    existente = EditionFactory()

    with pytest.raises(EditionAlreadyExists):
        create_edition(actor=admin, year=existente.year, semester=existente.semester)

    # A transação segue utilizável depois do conflito.
    assert Edition.objects.filter(pk=existente.pk).exists()


@pytest.mark.parametrize(
    "role", [UserRole.STUDENT, UserRole.TEACHER, UserRole.EXTERNAL_REVIEWER]
)
def test_quem_nao_e_admin_nao_cadastra(role):
    with pytest.raises(NotAdminActor):
        create_edition(actor=UserFactory(role=role), year=2030, semester=1)
    assert not Edition.objects.filter(year=2030).exists()


def test_sem_ator_nao_cadastra():
    with pytest.raises(NotAdminActor):
        create_edition(actor=None, year=2030, semester=1)
    assert not Edition.objects.filter(year=2030).exists()
