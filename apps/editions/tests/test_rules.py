import pytest

from apps.accounts.enums import UserRole
from apps.accounts.factories import UserFactory
from apps.editions.enums import EditionStatus
from apps.editions.exceptions import (
    EditionAlreadyExists,
    EditionError,
    InvalidTeamLimits,
    NotAdminActor,
    TeamLimitsLocked,
)
from apps.editions.factories import EditionFactory
from apps.editions.rules import (
    ensure_actor_is_admin,
    ensure_edition_identification_is_free,
    ensure_team_limits_editable,
    ensure_team_limits_valid,
)

pytestmark = pytest.mark.django_db


# Exceções de domínio


@pytest.mark.parametrize(
    ("exception", "code"),
    [
        (EditionAlreadyExists, "edition_exists"),
        (TeamLimitsLocked, "team_limits_locked"),
        (InvalidTeamLimits, "invalid_team_limits"),
        (NotAdminActor, "not_admin_actor"),
    ],
)
def test_excecao_tem_codigo_proprio_e_herda_de_edition_error(exception, code):
    assert issubclass(exception, EditionError)
    assert exception.code == code
    assert str(exception()) == exception.default_message


def test_excecao_aceita_mensagem_personalizada():
    assert str(EditionAlreadyExists("Outra mensagem.")) == "Outra mensagem."


# Ator administrador


def test_admin_passa():
    ensure_actor_is_admin(UserFactory(role=UserRole.ADMIN))


@pytest.mark.parametrize(
    "role", [UserRole.STUDENT, UserRole.TEACHER, UserRole.EXTERNAL_REVIEWER]
)
def test_outros_papeis_nao_passam(role):
    with pytest.raises(NotAdminActor):
        ensure_actor_is_admin(UserFactory(role=role))


def test_sem_ator_nao_passa():
    with pytest.raises(NotAdminActor):
        ensure_actor_is_admin(None)


# Identificação única da edição (RN05)


def test_ano_e_semestre_livres_passam():
    edition = EditionFactory()
    ensure_edition_identification_is_free(edition.year + 10, edition.semester)


def test_mesmo_ano_com_outro_semestre_passa():
    edition = EditionFactory(year=2040, semester=1)
    ensure_edition_identification_is_free(edition.year, 2)


def test_ano_e_semestre_repetidos_falham():
    edition = EditionFactory()
    with pytest.raises(EditionAlreadyExists):
        ensure_edition_identification_is_free(edition.year, edition.semester)


# Limites da equipe (RN07)


@pytest.mark.parametrize("limits", [(3, 5), (2, 4), (1, 1), (4, 4)])
def test_limites_validos_passam(limits):
    ensure_team_limits_valid(*limits)


@pytest.mark.parametrize(
    "limits", [(0, 5), (-1, 5), (3, 0), (3, -1), (0, 0), (6, 5), (5, 4)]
)
def test_limites_invalidos_falham(limits):
    with pytest.raises(InvalidTeamLimits):
        ensure_team_limits_valid(*limits)


# Limites só mudam em edição em configuração (RF48, RN33)


def test_edicao_em_configuracao_aceita_mudar_limites():
    ensure_team_limits_editable(EditionFactory(status=EditionStatus.SETUP))


@pytest.mark.parametrize("status", [EditionStatus.PUBLISHED, EditionStatus.CLOSED])
def test_edicao_publicada_ou_encerrada_trava_os_limites(status):
    with pytest.raises(TeamLimitsLocked):
        ensure_team_limits_editable(EditionFactory(status=status))
