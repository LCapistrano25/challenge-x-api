from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import NotAdminActor
from apps.accounts.factories import UserFactory
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.enums import EditionStatus
from apps.editions.exceptions import (
    EditionAlreadyExists,
    EditionClosed,
    EditionError,
    EditionPublished,
    InvalidTeamLimits,
    TeamLimitsLocked,
)
from apps.editions.factories import (
    EditionFactory,
    StageCriterionFactory,
    StageFactory,
)
from apps.editions.rules import (
    ensure_criterion_fits_stage,
    ensure_edition_identification_is_free,
    ensure_edition_not_closed,
    ensure_stage_max_score_fits,
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
        (EditionClosed, "edition_closed"),
        (EditionPublished, "edition_published"),
        (InvalidTeamLimits, "validation_error"),
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


@pytest.mark.parametrize(
    ("status", "error_class"),
    [
        (EditionStatus.PUBLISHED, EditionPublished),
        (EditionStatus.CLOSED, TeamLimitsLocked),
    ],
)
def test_edicao_publicada_ou_encerrada_trava_os_limites(status, error_class):
    with pytest.raises(error_class) as error:
        ensure_team_limits_editable(EditionFactory(status=status))
    assert type(error.value) is error_class


# Edição encerrada (RF47, RN33)


@pytest.mark.parametrize("status", [EditionStatus.SETUP, EditionStatus.PUBLISHED])
def test_edicao_nao_encerrada_aceita_alteracao(status):
    ensure_edition_not_closed(EditionFactory(status=status))


def test_edicao_encerrada_recusa_qualquer_alteracao():
    with pytest.raises(EditionClosed):
        ensure_edition_not_closed(EditionFactory(status=EditionStatus.CLOSED))


def test_edicao_encerrada_nao_e_o_mesmo_erro_dos_limites_travados():
    assert not issubclass(EditionClosed, TeamLimitsLocked)
    assert EditionClosed.http_status == TeamLimitsLocked.http_status == 409


# Soma das notas das etapas e dos critérios (INT-01, INT-02)


def test_etapas_pontuadas_ate_10_passam():
    edicao = EditionFactory()
    StageFactory(edition=edicao, max_score=Decimal("6.00"))
    ensure_stage_max_score_fits(
        StageFactory.build(edition=edicao, max_score=Decimal("4.00"))
    )


def test_etapas_pontuadas_acima_de_10_falham():
    edicao = EditionFactory()
    StageFactory(edition=edicao, max_score=Decimal("6.00"))
    StageFactory(edition=edicao, scored=False, max_score=None, kind="FINAL")
    with pytest.raises(ValidationError, match="10 pontos"):
        ensure_stage_max_score_fits(
            StageFactory.build(edition=edicao, max_score=Decimal("4.01"))
        )


def test_etapa_nao_pode_ficar_menor_que_seus_criterios():
    criterio = StageCriterionFactory(max_score=Decimal("3.00"))
    etapa = criterio.stage
    etapa.max_score = Decimal("2.00")
    with pytest.raises(ValidationError, match="critérios"):
        ensure_stage_max_score_fits(etapa)


def test_criterios_ate_o_valor_da_etapa_passam_e_acima_falham():
    etapa = StageFactory(max_score=Decimal("3.00"))
    primeiro = StageCriterionFactory(stage=etapa, max_score=Decimal("2.00"))
    ensure_criterion_fits_stage(primeiro)  # ele mesmo não conta duas vezes
    ensure_criterion_fits_stage(
        StageCriterionFactory.build(stage=etapa, max_score=Decimal("1.00"))
    )
    with pytest.raises(ValidationError, match="valor da etapa"):
        ensure_criterion_fits_stage(
            StageCriterionFactory.build(stage=etapa, max_score=Decimal("1.01"))
        )
