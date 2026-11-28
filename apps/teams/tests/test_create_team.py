from datetime import timedelta
from unittest.mock import patch

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.factories import StudentFactory, UserFactory
from apps.editions.enums import EditionStatus
from apps.editions.factories import EditionFactory, StageFactory
from apps.teams.enums import InvitationStatus, MemberRole, TeamStatus
from apps.teams.factories import TeamFactory, TeamMemberFactory
from apps.teams.models import Invitation, Team, TeamMember
from apps.teams.use_cases.create_team import (
    FormationClosed,
    TeamCreationRejected,
    TeamInvitationsRequired,
    create_team,
)
from apps.teams.use_cases.invite_member import InvitationRejected

pytestmark = pytest.mark.django_db


def convites(quantidade=2):
    """Convites para alunos novos: com min_members=3 o líder convida ao menos 2."""
    return [{"student_id": StudentFactory().pk} for _ in range(quantidade)]


def abre_formacao(edition):
    # Formação só abre em edição publicada (#301).
    edition.status = EditionStatus.PUBLISHED
    edition.save(update_fields=["status"])
    now = timezone.now()
    StageFactory(
        edition=edition,
        formation=True,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=7),
    )


def test_aluno_cria_equipe_e_se_torna_lider():
    student = StudentFactory()
    edition = EditionFactory(status=EditionStatus.PUBLISHED)

    now = timezone.now()
    StageFactory(
        edition=edition,
        formation=True,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=7),
    )

    invited = convites()
    team = create_team(
        actor=student.user,
        edition_id=edition.id,
        name="Equipe Teste",
        invitations=invited,
    )

    assert isinstance(team, Team)
    assert team.name == "Equipe Teste"
    assert team.edition == edition
    assert team.code

    membership = TeamMember.objects.get(
        team=team,
        student=student,
        active=True,
    )
    assert membership.role == MemberRole.LEADER
    assert membership.left_at is None
    pendentes = Invitation.objects.filter(team=team, status=InvitationStatus.PENDING)
    assert {i.student_id for i in pendentes} == {d["student_id"] for d in invited}


def test_usuario_que_nao_e_aluno_nao_pode_criar_equipe():
    user = UserFactory(role=UserRole.TEACHER)
    edition = EditionFactory(status=EditionStatus.PUBLISHED)

    with pytest.raises(
        TeamCreationRejected,
        match="Somente alunos podem criar equipes.",
    ):
        create_team(
            actor=user,
            edition_id=edition.id,
            name="Equipe Teste",
        )

    assert Team.objects.count() == 0


def test_nao_pode_criar_equipe_fora_do_periodo_de_formacao():
    student = StudentFactory()
    edition = EditionFactory(status=EditionStatus.PUBLISHED)

    now = timezone.now()
    StageFactory(
        edition=edition,
        formation=True,
        starts_at=now - timedelta(days=10),
        ends_at=now - timedelta(days=5),
    )

    with pytest.raises(
        TeamCreationRejected,
        match="Não existe prazo de formação aberto para esta edição.",
    ):
        create_team(
            actor=student.user,
            edition_id=edition.id,
            name="Equipe Teste",
        )

    assert Team.objects.count() == 0


def test_aluno_nao_pode_criar_equipe_se_ja_participa_de_uma_ativa():
    student = StudentFactory()
    edition = EditionFactory(status=EditionStatus.PUBLISHED)

    now = timezone.now()
    StageFactory(
        edition=edition,
        formation=True,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=7),
    )

    team = TeamFactory(edition=edition)

    TeamMemberFactory(
        team=team,
        student=student,
    )

    with pytest.raises(
        TeamCreationRejected,
        match="Você já participa de uma equipe ativa nesta edição.",
    ):
        create_team(
            actor=student.user,
            edition_id=edition.id,
            name="Nova Equipe",
        )

    assert Team.objects.filter(edition=edition).count() == 1


def test_nao_pode_criar_equipe_com_nome_vazio():
    student = StudentFactory()
    edition = EditionFactory(status=EditionStatus.PUBLISHED)

    now = timezone.now()
    StageFactory(
        edition=edition,
        formation=True,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=7),
    )

    with pytest.raises(
        TeamCreationRejected,
        match="O nome da equipe é obrigatório.",
    ):
        create_team(
            actor=student.user,
            edition_id=edition.id,
            name="   ",
        )

    assert Team.objects.count() == 0


def test_nao_cria_equipe_so_com_o_lider():
    student = StudentFactory()
    edition = EditionFactory(min_members=3, max_members=5)
    abre_formacao(edition)

    with pytest.raises(TeamInvitationsRequired, match="Convide de 2 a 4 alunos"):
        create_team(actor=student.user, edition_id=edition.id, name="Equipe Inicial")

    assert Team.objects.count() == 0


@pytest.mark.parametrize("quantidade", [1, 5])
def test_quantidade_de_convites_fora_do_limite_da_edicao_e_recusada(quantidade):
    student = StudentFactory()
    edition = EditionFactory(min_members=3, max_members=5)
    abre_formacao(edition)

    with pytest.raises(TeamInvitationsRequired):
        create_team(
            actor=student.user,
            edition_id=edition.id,
            name="Equipe Inicial",
            invitations=convites(quantidade),
        )

    assert Team.objects.count() == 0
    assert Invitation.objects.count() == 0


def test_edicao_com_minimo_1_ainda_exige_ao_menos_um_convite():
    student = StudentFactory()
    edition = EditionFactory(min_members=1, max_members=5)
    abre_formacao(edition)

    with pytest.raises(TeamInvitationsRequired, match="Convide de 1 a 4 alunos"):
        create_team(actor=student.user, edition_id=edition.id, name="Equipe Solo")

    team = create_team(
        actor=student.user,
        edition_id=edition.id,
        name="Equipe Solo",
        invitations=convites(1),
    )
    assert Invitation.objects.filter(team=team).count() == 1


def test_convite_recusado_desfaz_a_criacao_da_equipe():
    student = StudentFactory()
    edition = EditionFactory(min_members=3, max_members=5)
    abre_formacao(edition)
    ocupado = StudentFactory()
    TeamMemberFactory(team=TeamFactory(edition=edition), student=ocupado)
    teams_antes = Team.objects.count()

    with pytest.raises(InvitationRejected, match="já participa de uma equipe"):
        create_team(
            actor=student.user,
            edition_id=edition.id,
            name="Equipe Inicial",
            invitations=[{"student_id": StudentFactory().pk}]
            + [{"student_id": ocupado.pk}],
        )

    assert Team.objects.count() == teams_antes
    assert Invitation.objects.count() == 0


def test_nome_de_equipe_desfeita_pode_ser_reutilizado():
    student = StudentFactory()
    edition = EditionFactory(status=EditionStatus.PUBLISHED)
    abre_formacao(edition)
    TeamFactory(edition=edition, name="Equipe Aurora", status=TeamStatus.DISBANDED)

    team = create_team(
        actor=student.user,
        edition_id=edition.id,
        name="Equipe Aurora",
        invitations=convites(),
    )

    assert team.status == TeamStatus.ACTIVE


def test_nao_pode_criar_equipe_com_nome_duplicado_na_edicao():
    student = StudentFactory()
    edition = EditionFactory(status=EditionStatus.PUBLISHED)

    now = timezone.now()
    StageFactory(
        edition=edition,
        formation=True,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=7),
    )

    TeamFactory(
        edition=edition,
        name="Equipe Teste",
    )

    with pytest.raises(
        TeamCreationRejected,
        match="Já existe uma equipe com esse nome nesta edição.",
    ):
        create_team(
            actor=student.user,
            edition_id=edition.id,
            name="Equipe Teste",
        )

    assert (
        Team.objects.filter(
            edition=edition,
            name="Equipe Teste",
        ).count()
        == 1
    )


def test_nao_pode_criar_equipe_para_edicao_inexistente():
    student = StudentFactory()

    with pytest.raises(
        TeamCreationRejected,
        match="Edição não encontrada.",
    ):
        create_team(
            actor=student.user,
            edition_id=999999,
            name="Equipe Teste",
        )

    assert Team.objects.count() == 0


def test_nao_pode_criar_equipe_sem_perfil_de_aluno():
    user = UserFactory(role=UserRole.STUDENT)
    edition = EditionFactory(status=EditionStatus.PUBLISHED)

    with pytest.raises(
        TeamCreationRejected,
        match="O perfil de aluno não foi encontrado.",
    ):
        create_team(
            actor=user,
            edition_id=edition.id,
            name="Equipe Teste",
        )

    assert Team.objects.count() == 0


def test_remove_espacos_do_nome_da_equipe():
    student = StudentFactory()
    edition = EditionFactory(status=EditionStatus.PUBLISHED)

    now = timezone.now()
    StageFactory(
        edition=edition,
        formation=True,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=7),
    )

    team = create_team(
        actor=student.user,
        edition_id=edition.id,
        name="  Equipe Teste  ",
        invitations=convites(),
    )

    assert team.name == "Equipe Teste"


def test_tenta_novo_codigo_quando_codigo_ja_existe(monkeypatch):
    existing_team = TeamFactory()
    student = StudentFactory()
    edition = EditionFactory(status=EditionStatus.PUBLISHED)

    now = timezone.now()
    StageFactory(
        edition=edition,
        formation=True,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=7),
    )

    codes = iter([existing_team.code, "NOVO01"])

    monkeypatch.setattr(
        "apps.teams.use_cases.create_team._generate_team_code",
        lambda: next(codes),
    )

    team = create_team(
        actor=student.user,
        edition_id=edition.id,
        name="Nova Equipe",
        invitations=convites(),
    )

    assert team.code == "NOVO01"
    assert team.code != existing_team.code


def test_rejeita_criacao_quando_nao_consegue_gerar_codigo_unico(
    monkeypatch,
):
    existing_team = TeamFactory()
    student = StudentFactory()
    edition = EditionFactory(status=EditionStatus.PUBLISHED)

    now = timezone.now()
    StageFactory(
        edition=edition,
        formation=True,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=7),
    )

    monkeypatch.setattr(
        "apps.teams.use_cases.create_team._generate_team_code",
        lambda: existing_team.code,
    )

    with pytest.raises(
        TeamCreationRejected,
        match="Não foi possível gerar um código de convite único.",
    ):
        create_team(
            actor=student.user,
            edition_id=edition.id,
            name="Nova Equipe",
            invitations=convites(),
        )

    assert Team.objects.count() == 1


def test_reverte_criacao_da_equipe_se_falhar_ao_criar_lider():
    student = StudentFactory()
    edition = EditionFactory(status=EditionStatus.PUBLISHED)

    now = timezone.now()
    StageFactory(
        edition=edition,
        formation=True,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=7),
    )

    with patch(
        "apps.teams.use_cases.create_team.TeamMember.objects.create",
        side_effect=IntegrityError("Erro simulado"),
    ):
        with pytest.raises(
            TeamCreationRejected,
            match="Não foi possível criar a equipe.",
        ):
            create_team(
                actor=student.user,
                edition_id=edition.id,
                name="Equipe Teste",
                invitations=convites(),
            )

    assert Team.objects.count() == 0
    assert TeamMember.objects.count() == 0


# Formação só em edição publicada (#301)


@pytest.mark.parametrize("status", [EditionStatus.SETUP, EditionStatus.CLOSED])
def test_edicao_nao_publicada_nao_forma_equipe_mesmo_com_etapa_aberta(status):
    edition = EditionFactory(status=status)
    now = timezone.now()
    StageFactory(
        edition=edition,
        formation=True,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=7),
    )

    with pytest.raises(FormationClosed):
        create_team(
            actor=StudentFactory().user,
            edition_id=edition.id,
            name="Equipe Fora de Hora",
            invitations=convites(),
        )

    assert not Team.objects.filter(edition=edition).exists()
