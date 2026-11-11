from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.factories import UserFactory
from apps.editions.factories import (
    CategoryFactory,
    ChallengeFactory,
    EditionFactory,
    StageFactory,
)
from apps.projects.exceptions import (
    ChallengeNotEligible,
    ChallengeNotSelected,
    FormationClosed,
    NotTeamLeader,
    ProjectTitleTaken,
)
from apps.projects.factories import ProjectFactory
from apps.projects.models import Project
from apps.projects.use_cases import save_project_details as save_module
from apps.projects.use_cases.invalidate_challenge import invalidate_challenge
from apps.projects.use_cases.save_project_details import save_project_details
from apps.projects.use_cases.select_challenge import select_challenge
from apps.teams.enums import MemberRole
from apps.teams.factories import TeamFactory, TeamMemberFactory

pytestmark = pytest.mark.django_db


def open_formation(edition):
    now = timezone.now()
    return StageFactory(
        formation=True,
        edition=edition,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=1),
    )


@pytest.fixture
def team():
    team = TeamFactory()
    open_formation(team.edition)
    return team


@pytest.fixture
def leader(team):
    return team.members.get(role=MemberRole.LEADER).student.user


@pytest.fixture
def challenge(team):
    course = team.members.get(role=MemberRole.LEADER).student.course
    return ChallengeFactory(edition=team.edition, course=course)


def project_with_challenge(team, challenge, **fields):
    return ProjectFactory(team=team, challenge=challenge, **fields)


# Escolher o desafio (UC32, RF29)


def test_escolher_cria_o_projeto_da_equipe(team, leader, challenge):
    project = select_challenge(actor=leader, team=team, challenge=challenge)

    project.refresh_from_db()
    assert project.team == team
    assert project.edition == team.edition
    assert project.challenge == challenge
    assert project.title == ""
    assert project.summary == ""


def test_escolher_atualiza_o_projeto_existente_sem_perder_os_dados(
    team, leader, challenge
):
    outro = ChallengeFactory(edition=team.edition, course=challenge.course)
    categoria = CategoryFactory(edition=team.edition)
    existente = project_with_challenge(
        team, challenge, title="Meu projeto", category=categoria
    )

    project = select_challenge(actor=leader, team=team, challenge=outro)

    assert project.pk == existente.pk
    project.refresh_from_db()
    assert project.challenge == outro
    assert (project.title, project.summary) == ("Meu projeto", "Resumo da proposta.")
    assert project.category == categoria
    assert Project.objects.filter(team=team).count() == 1


def test_escolher_recusa_quem_nao_e_lider(team, challenge):
    membro = TeamMemberFactory(team=team)
    with pytest.raises(NotTeamLeader):
        select_challenge(actor=membro.student.user, team=team, challenge=challenge)
    assert not Project.objects.exists()


def test_escolher_recusa_fora_do_prazo():
    team = TeamFactory()  # sem etapa de formação aberta
    course = team.members.get(role=MemberRole.LEADER).student.course
    desafio = ChallengeFactory(edition=team.edition, course=course)
    lider = team.members.get(role=MemberRole.LEADER).student.user

    with pytest.raises(FormationClosed):
        select_challenge(actor=lider, team=team, challenge=desafio)
    assert not Project.objects.exists()


def test_escolher_recusa_desafio_de_curso_sem_integrante(team, leader):
    estranho = ChallengeFactory(edition=team.edition)
    with pytest.raises(ChallengeNotEligible):
        select_challenge(actor=leader, team=team, challenge=estranho)
    assert not Project.objects.exists()


def test_escolher_recusa_desafio_inativo(team, leader, challenge):
    challenge.active = False
    challenge.save()
    with pytest.raises(ChallengeNotEligible):
        select_challenge(actor=leader, team=team, challenge=challenge)


def test_escolher_recusa_desafio_de_outra_edicao(team, leader, challenge):
    outra = ChallengeFactory(edition=EditionFactory(), course=challenge.course)
    with pytest.raises(ChallengeNotEligible):
        select_challenge(actor=leader, team=team, challenge=outra)


# Cadastrar os dados do projeto (UC33, RF30)


@pytest.fixture
def project(team, challenge):
    return project_with_challenge(team, challenge, title="", summary="")


def test_salvar_grava_titulo_resumo_e_objetivo(team, leader, project):
    result = save_project_details(
        actor=leader,
        team=team,
        title="  Água   limpa ",
        summary=" Sensores no campus. ",
        objective="Reduzir o desperdício.",
    )

    result.refresh_from_db()
    assert result.pk == project.pk
    assert result.title == "Água limpa"
    assert result.summary == "Sensores no campus."
    assert result.objective == "Reduzir o desperdício."


def test_salvar_atualiza_os_dados_ja_cadastrados(team, leader, project):
    save_project_details(actor=leader, team=team, title="Primeiro", summary="A")
    save_project_details(actor=leader, team=team, title="Segundo", summary="B")

    project.refresh_from_db()
    assert (project.title, project.summary) == ("Segundo", "B")
    assert Project.objects.count() == 1


def test_salvar_o_proprio_titulo_de_novo_nao_conflita(team, leader, project):
    save_project_details(actor=leader, team=team, title="Igual", summary="A")
    save_project_details(actor=leader, team=team, title="IGUAL", summary="B")

    project.refresh_from_db()
    assert project.title == "IGUAL"


def test_salvar_nao_altera_desafio_nem_categoria(team, leader, project, challenge):
    categoria = CategoryFactory(edition=team.edition)
    project.category = categoria
    project.save()

    save_project_details(actor=leader, team=team, title="Novo", summary="Resumo")

    project.refresh_from_db()
    assert project.challenge == challenge
    assert project.category == categoria


@pytest.mark.parametrize("titulo", ["agua limpa", "AGUA LIMPA", "  agua   limpa  "])
def test_salvar_recusa_titulo_repetido_na_edicao(team, leader, project, titulo):
    ProjectFactory(team=TeamFactory(edition=team.edition), title="Agua Limpa")

    with pytest.raises(ProjectTitleTaken):
        save_project_details(actor=leader, team=team, title=titulo, summary="x")

    project.refresh_from_db()
    assert project.title == ""


def test_salvar_aceita_titulo_igual_em_outra_edicao(team, leader, project):
    ProjectFactory(title="Agua Limpa")  # outra edição, via TeamFactory

    save_project_details(actor=leader, team=team, title="Agua Limpa", summary="x")

    project.refresh_from_db()
    assert project.title == "Agua Limpa"


@pytest.mark.parametrize(
    ("title", "summary", "campo"),
    [("", "Resumo", "title"), ("   ", "Resumo", "title"), ("Título", "  ", "summary")],
)
def test_salvar_recusa_titulo_ou_resumo_em_branco(
    team, leader, project, title, summary, campo
):
    with pytest.raises(ValidationError) as erro:
        save_project_details(actor=leader, team=team, title=title, summary=summary)
    assert campo in erro.value.message_dict


def test_salvar_exige_desafio_escolhido(team, leader, project):
    project.challenge = None
    project.save()
    with pytest.raises(ChallengeNotSelected):
        save_project_details(actor=leader, team=team, title="Novo", summary="x")


def test_salvar_exige_que_o_projeto_exista(team, leader):
    with pytest.raises(ChallengeNotSelected):
        save_project_details(actor=leader, team=team, title="Novo", summary="x")
    assert not Project.objects.exists()


def test_salvar_recusa_quem_nao_e_lider(team, project):
    membro = TeamMemberFactory(team=team)
    with pytest.raises(NotTeamLeader):
        save_project_details(
            actor=membro.student.user, team=team, title="Novo", summary="x"
        )


def test_salvar_recusa_admin(team, project):
    with pytest.raises(NotTeamLeader):
        save_project_details(
            actor=UserFactory(role=UserRole.ADMIN), team=team, title="N", summary="x"
        )


def test_salvar_recusa_fora_do_prazo(team, leader, project):
    team.edition.stages.all().delete()
    with pytest.raises(FormationClosed):
        save_project_details(actor=leader, team=team, title="Novo", summary="x")


def test_corrida_no_titulo_vira_project_title_taken(team, leader, project, monkeypatch):
    # A checagem prévia não vê o outro projeto (ele ainda não tinha sido gravado
    # quando ela rodou); quem recusa é a unicidade do banco.
    ProjectFactory(team=TeamFactory(edition=team.edition), title="Concorrente")
    monkeypatch.setattr(save_module, "ensure_project_title_is_free", lambda *a: None)

    with pytest.raises(ProjectTitleTaken):
        save_project_details(actor=leader, team=team, title="concorrente", summary="x")


def test_integrity_error_de_outra_causa_nao_e_engolido(
    team, leader, project, monkeypatch
):
    def quebra(self, *args, **kwargs):
        raise IntegrityError("outra constraint")

    monkeypatch.setattr(Project, "save", quebra)
    with pytest.raises(IntegrityError):
        save_project_details(actor=leader, team=team, title="Novo", summary="x")


# Invalidar o desafio (RF26, regra 5)


def test_invalidar_tira_o_desafio_e_mantem_o_resto(team, challenge):
    categoria = CategoryFactory(edition=team.edition)
    project = project_with_challenge(
        team, challenge, title="Meu projeto", category=categoria
    )

    invalidate_challenge(project=project)

    project.refresh_from_db()
    assert project.challenge is None
    assert (project.title, project.summary) == ("Meu projeto", "Resumo da proposta.")
    assert project.category == categoria


def test_invalidar_projeto_sem_desafio_nao_faz_nada(team):
    project = ProjectFactory(team=team, challenge=None)
    antes = project.updated_at

    invalidate_challenge(project=project, actor=None)

    project.refresh_from_db()
    assert project.challenge is None
    assert project.updated_at == antes


def test_depois_de_invalidar_o_lider_escolhe_de_novo(team, leader, challenge):
    project = project_with_challenge(team, challenge)
    invalidate_challenge(project=project)

    select_challenge(actor=leader, team=team, challenge=challenge)

    project.refresh_from_db()
    assert project.challenge == challenge
