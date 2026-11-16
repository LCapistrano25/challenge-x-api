from datetime import timedelta
from unittest.mock import patch

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.factories import StudentFactory, UserFactory
from apps.editions.factories import EditionFactory, StageFactory
from apps.teams.enums import MemberRole
from apps.teams.factories import TeamFactory, TeamMemberFactory
from apps.teams.models import Team, TeamMember
from apps.teams.use_cases.create_team import (
    TeamCreationRejected,
    create_team,
)

pytestmark = pytest.mark.django_db


def test_aluno_cria_equipe_e_se_torna_lider():
    student = StudentFactory()
    edition = EditionFactory()

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
        name="Equipe Teste",
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


def test_usuario_que_nao_e_aluno_nao_pode_criar_equipe():
    user = UserFactory(role=UserRole.TEACHER)
    edition = EditionFactory()

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
    edition = EditionFactory()

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
    edition = EditionFactory()

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
    edition = EditionFactory()

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


def test_permite_criar_equipe_abaixo_do_minimo_durante_formacao():
    student = StudentFactory()
    edition = EditionFactory(
        min_members=3,
        max_members=5,
    )

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
        name="Equipe Inicial",
    )

    assert (
        TeamMember.objects.filter(
            team=team,
            active=True,
        ).count()
        == 1
    )

    assert TeamMember.objects.filter(
        team=team,
        student=student,
        role=MemberRole.LEADER,
        active=True,
    ).exists()


def test_nao_pode_criar_equipe_com_nome_duplicado_na_edicao():
    student = StudentFactory()
    edition = EditionFactory()

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
    edition = EditionFactory()

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
    edition = EditionFactory()

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
    )

    assert team.name == "Equipe Teste"


def test_tenta_novo_codigo_quando_codigo_ja_existe(monkeypatch):
    existing_team = TeamFactory()
    student = StudentFactory()
    edition = EditionFactory()

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
    )

    assert team.code == "NOVO01"
    assert team.code != existing_team.code


def test_rejeita_criacao_quando_nao_consegue_gerar_codigo_unico(
    monkeypatch,
):
    existing_team = TeamFactory()
    student = StudentFactory()
    edition = EditionFactory()

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
        )

    assert Team.objects.count() == 1


def test_reverte_criacao_da_equipe_se_falhar_ao_criar_lider():
    student = StudentFactory()
    edition = EditionFactory()

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
            )

    assert Team.objects.count() == 0
    assert TeamMember.objects.count() == 0
