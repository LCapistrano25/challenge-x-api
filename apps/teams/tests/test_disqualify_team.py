import pytest
from django.core.exceptions import ValidationError

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import NotAdminActor
from apps.accounts.factories import UserFactory
from apps.editions.enums import EditionStatus
from apps.editions.factories import EditionFactory
from apps.projects.enums import ProjectStatus
from apps.projects.factories import ProjectFactory
from apps.projects.models import Project
from apps.teams.enums import TeamStatus
from apps.teams.factories import TeamFactory
from apps.teams.use_cases.disqualify_team import (
    EditionClosed,
    TeamNotFound,
    disqualify_team,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin():
    return UserFactory(role=UserRole.ADMIN)


@pytest.fixture
def equipe():
    edition = EditionFactory(status=EditionStatus.PUBLISHED)
    return TeamFactory(edition=edition)


def test_desclassifica_equipe_com_justificativa(admin, equipe):
    result = disqualify_team(
        actor=admin,
        team_id=equipe.pk,
        reason=" Descumprimento das regras. ",
    )

    result.refresh_from_db()

    assert result.status == TeamStatus.DISQUALIFIED
    assert result.disqualification_reason == "Descumprimento das regras."
    assert result.disqualified_by == admin
    assert result.disqualified_at is not None


def test_usuario_que_nao_e_admin_nao_pode_desclassificar(equipe):
    student = UserFactory(role=UserRole.STUDENT)

    with pytest.raises(NotAdminActor):
        disqualify_team(
            actor=student,
            team_id=equipe.pk,
            reason="Descumprimento das regras.",
        )

    equipe.refresh_from_db()
    assert equipe.status == TeamStatus.ACTIVE


def test_equipe_inexistente_nao_pode_ser_desclassificada(admin):
    with pytest.raises(TeamNotFound, match="Equipe não encontrada."):
        disqualify_team(
            actor=admin,
            team_id=999999,
            reason="Descumprimento das regras.",
        )


@pytest.mark.parametrize("reason", ["", "   "])
def test_justificativa_vazia_e_rejeitada(admin, equipe, reason):
    with pytest.raises(
        ValidationError,
        match="A justificativa da desclassificação é obrigatória.",
    ):
        disqualify_team(actor=admin, team_id=equipe.pk, reason=reason)

    equipe.refresh_from_db()
    assert equipe.status == TeamStatus.ACTIVE


def test_equipe_que_nao_esta_ativa_nao_pode_ser_desclassificada(admin):
    edition = EditionFactory(status=EditionStatus.PUBLISHED)
    equipe = TeamFactory(edition=edition, status=TeamStatus.DISBANDED)

    with pytest.raises(
        ValidationError,
        match="Não é possível desclassificar uma equipe que não está ativa.",
    ):
        disqualify_team(
            actor=admin,
            team_id=equipe.pk,
            reason="Descumprimento das regras.",
        )

    equipe.refresh_from_db()
    assert equipe.status == TeamStatus.DISBANDED


def test_equipe_de_edicao_nao_publicada_nao_pode_ser_desclassificada(admin):
    edition = EditionFactory(status=EditionStatus.CLOSED)
    equipe = TeamFactory(edition=edition)

    with pytest.raises(
        EditionClosed,
        match="A edição está encerrada e não pode ser alterada.",
    ):
        disqualify_team(
            actor=admin,
            team_id=equipe.pk,
            reason="Descumprimento das regras.",
        )


def test_desclassifica_projeto_vinculado_a_equipe(admin, equipe):
    project = ProjectFactory(team=equipe)

    disqualify_team(
        actor=admin,
        team_id=equipe.pk,
        reason="Descumprimento das regras.",
    )

    equipe.refresh_from_db()
    project.refresh_from_db()

    assert equipe.status == TeamStatus.DISQUALIFIED
    assert project.status == ProjectStatus.DISQUALIFIED


def test_falha_ao_desclassificar_projeto_reverte_equipe(admin, equipe, monkeypatch):
    project = ProjectFactory(team=equipe)

    def fail_save(*args, **kwargs):
        raise RuntimeError("Falha ao salvar projeto.")

    monkeypatch.setattr(Project, "save", fail_save)

    with pytest.raises(RuntimeError, match="Falha ao salvar projeto."):
        disqualify_team(
            actor=admin,
            team_id=equipe.pk,
            reason="Descumprimento das regras.",
        )

    equipe.refresh_from_db()
    project.refresh_from_db()

    assert equipe.status == TeamStatus.ACTIVE
    assert project.status == ProjectStatus.IN_PROGRESS
