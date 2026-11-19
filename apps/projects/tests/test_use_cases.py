from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.factories import UserFactory
from apps.editions.exceptions import EditionClosed
from apps.editions.factories import (
    CategoryFactory,
    ChallengeFactory,
    EditionFactory,
    StageFactory,
    StageSubmissionFieldFactory,
)
from apps.projects.exceptions import (
    CategoryNotAvailable,
    ChallengeNotEligible,
    ChallengeNotSelected,
    FormationClosed,
    NotTeamLeader,
    ProjectNotFound,
    ProjectTitleTaken,
    StageDeadlineClosed,
    StageNotFound,
    StageNotOpen,
    TeamDisqualified,
    TeamIncomplete,
)
from apps.projects.factories import DeadlineExtensionFactory, ProjectFactory
from apps.projects.models import (
    Project,
    Submission,
    SubmissionItem,
    SubmissionReceipt,
    SubmissionVersion,
)
from apps.projects.use_cases import save_project_details as save_module
from apps.projects.use_cases.invalidate_challenge import invalidate_challenge
from apps.projects.use_cases.save_project_details import save_project_details
from apps.projects.use_cases.select_category import select_category
from apps.projects.use_cases.select_challenge import select_challenge
from apps.projects.use_cases.submit_stage_delivery import submit_stage_delivery
from apps.teams.enums import MemberRole, TeamSituation
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


# Escolher a categoria (UC39, RF30, RF49)


@pytest.fixture
def category(team):
    return CategoryFactory(edition=team.edition)


def test_categoria_grava_no_projeto(team, leader, challenge, category):
    project_with_challenge(team, challenge)

    result = select_category(actor=leader, team=team, category=category)

    result.refresh_from_db()
    assert result.category == category


def test_categoria_pode_ser_trocada(team, leader, challenge, category):
    project_with_challenge(team, challenge, category=category)
    outra = CategoryFactory(edition=team.edition)

    result = select_category(actor=leader, team=team, category=outra)

    assert Project.objects.get(pk=result.pk).category == outra


def test_categoria_repetida_nao_e_erro(team, leader, challenge, category):
    project_with_challenge(team, challenge)
    select_category(actor=leader, team=team, category=category)

    result = select_category(actor=leader, team=team, category=category)

    assert Project.objects.get(pk=result.pk).category == category


def test_categoria_preserva_desafio_titulo_resumo_e_objetivo(
    team, leader, challenge, category
):
    project_with_challenge(
        team, challenge, title="Meu projeto", summary="Resumo", objective="Meta"
    )

    result = select_category(actor=leader, team=team, category=category)

    result.refresh_from_db()
    assert (result.challenge, result.title, result.summary, result.objective) == (
        challenge,
        "Meu projeto",
        "Resumo",
        "Meta",
    )


def test_categoria_recusa_quem_nao_e_lider(team, challenge, category):
    project_with_challenge(team, challenge)
    membro = TeamMemberFactory(team=team)
    with pytest.raises(NotTeamLeader):
        select_category(actor=membro.student.user, team=team, category=category)


def test_categoria_recusa_admin(team, challenge, category):
    project_with_challenge(team, challenge)
    with pytest.raises(NotTeamLeader):
        select_category(
            actor=UserFactory(role=UserRole.ADMIN), team=team, category=category
        )


def test_categoria_recusa_fora_do_prazo(team, leader, challenge, category):
    project_with_challenge(team, challenge)
    stage = team.edition.stages.get()
    stage.starts_at = timezone.now() - timedelta(days=3)
    stage.ends_at = timezone.now() - timedelta(days=1)
    stage.save()
    with pytest.raises(FormationClosed):
        select_category(actor=leader, team=team, category=category)


def test_categoria_recusa_sem_etapa_de_formacao(team, leader, challenge, category):
    project_with_challenge(team, challenge)
    team.edition.stages.all().delete()
    with pytest.raises(FormationClosed):
        select_category(actor=leader, team=team, category=category)


def test_categoria_recusa_equipe_sem_projeto(team, leader, category):
    with pytest.raises(ProjectNotFound):
        select_category(actor=leader, team=team, category=category)


def test_categoria_recusa_categoria_inativa(team, leader, challenge):
    project_with_challenge(team, challenge)
    inativa = CategoryFactory(edition=team.edition, active=False)
    with pytest.raises(CategoryNotAvailable):
        select_category(actor=leader, team=team, category=inativa)


def test_categoria_recusa_categoria_de_outra_edicao(team, leader, challenge):
    project_with_challenge(team, challenge)
    with pytest.raises(CategoryNotAvailable):
        select_category(actor=leader, team=team, category=CategoryFactory())


def test_falha_nao_grava_a_categoria(team, leader, challenge, category):
    project = project_with_challenge(team, challenge, category=category)
    inativa = CategoryFactory(edition=team.edition, active=False)

    with pytest.raises(CategoryNotAvailable):
        select_category(actor=leader, team=team, category=inativa)

    project.refresh_from_db()
    assert project.category == category


# Enviar a entrega da etapa (UC34, RF31)


@pytest.fixture
def delivery_project():
    return ProjectFactory()


@pytest.fixture
def delivery_leader(delivery_project):
    return delivery_project.team.members.get(role=MemberRole.LEADER).student.user


@pytest.fixture
def delivery_stage(delivery_project):
    now = timezone.now()
    return StageFactory(
        edition=delivery_project.edition,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=1),
    )


@pytest.fixture
def link_field(delivery_stage):
    return StageSubmissionFieldFactory(stage=delivery_stage)


def send(actor, project, stage, field, link="https://github.com/equipe/p", **extra):
    return submit_stage_delivery(
        actor=actor,
        project=project,
        stage=stage,
        items=[{"field": field, "link": link}],
        **extra,
    )


def test_envio_cria_entrega_versao_item_e_comprovante(
    delivery_project, delivery_leader, delivery_stage, link_field
):
    version = send(
        delivery_leader, delivery_project, delivery_stage, link_field, notes="Primeira"
    )

    assert version.number == 1
    assert version.notes == "Primeira"
    assert version.submitted_by == delivery_leader.student
    assert version.submission.project == delivery_project
    assert version.submission.stage == delivery_stage
    item = version.items.get()
    assert (item.field, item.kind, item.link) == (
        link_field,
        "LINK",
        "https://github.com/equipe/p",
    )
    assert version.receipt.file_url == ""
    assert version.receipt.verification_code


def test_segundo_envio_cria_versao_2_e_preserva_a_1(
    delivery_project, delivery_leader, delivery_stage, link_field
):
    first = send(delivery_leader, delivery_project, delivery_stage, link_field)
    second = send(
        delivery_leader,
        delivery_project,
        delivery_stage,
        link_field,
        link="https://x.dev/2",
    )

    assert (first.number, second.number) == (1, 2)
    assert first.submission == second.submission
    assert first.items.get().link == "https://github.com/equipe/p"
    assert Submission.objects.count() == 1


def test_reenvio_igual_cria_outra_versao(
    delivery_project, delivery_leader, delivery_stage, link_field
):
    send(delivery_leader, delivery_project, delivery_stage, link_field)
    send(delivery_leader, delivery_project, delivery_stage, link_field)
    assert SubmissionVersion.objects.count() == 2


def test_envio_recusa_membro_comum(delivery_project, delivery_stage, link_field):
    member = TeamMemberFactory(team=delivery_project.team).student.user
    with pytest.raises(NotTeamLeader):
        send(member, delivery_project, delivery_stage, link_field)


def test_envio_recusa_admin(delivery_project, delivery_stage, link_field):
    admin = UserFactory(role=UserRole.ADMIN)
    with pytest.raises(NotTeamLeader):
        send(admin, delivery_project, delivery_stage, link_field)


def test_envio_recusa_lider_inativo(
    delivery_project, delivery_leader, delivery_stage, link_field
):
    delivery_project.team.members.filter(role=MemberRole.LEADER).update(
        active=False, left_at=timezone.now()
    )
    with pytest.raises(NotTeamLeader):
        send(delivery_leader, delivery_project, delivery_stage, link_field)


def test_envio_recusa_edicao_encerrada(
    delivery_project, delivery_leader, delivery_stage, link_field
):
    edition = delivery_project.edition
    edition.status = "CLOSED"
    edition.save()
    with pytest.raises(EditionClosed):
        send(delivery_leader, delivery_project, delivery_stage, link_field)


def test_envio_recusa_equipe_desclassificada(delivery_stage, link_field):
    team = TeamFactory(edition=delivery_stage.edition, disqualified=True)
    project = ProjectFactory(team=team)
    leader = team.members.get(role=MemberRole.LEADER).student.user
    with pytest.raises(TeamDisqualified):
        send(leader, project, delivery_stage, link_field)


@pytest.mark.parametrize(
    "situation", [TeamSituation.INCOMPLETE, TeamSituation.REQUIREMENTS_NOT_MET]
)
def test_envio_recusa_equipe_incompleta(
    situation, delivery_project, delivery_leader, delivery_stage, link_field
):
    delivery_project.team.situation = situation
    delivery_project.team.save()
    with pytest.raises(TeamIncomplete):
        send(delivery_leader, delivery_project, delivery_stage, link_field)


@pytest.mark.parametrize("missing", ["challenge", "title", "summary"])
def test_envio_recusa_projeto_incompleto(
    missing, delivery_project, delivery_leader, delivery_stage, link_field
):
    setattr(delivery_project, missing, None if missing == "challenge" else "")
    delivery_project.save()
    with pytest.raises(ValidationError):
        send(delivery_leader, delivery_project, delivery_stage, link_field)


def test_envio_recusa_etapa_de_formacao(delivery_project, delivery_leader):
    stage = StageFactory(formation=True, edition=delivery_project.edition)
    field = StageSubmissionFieldFactory(stage=stage)
    with pytest.raises(StageNotFound):
        send(delivery_leader, delivery_project, stage, field)


def test_envio_recusa_etapa_de_outra_edicao(delivery_project, delivery_leader):
    stage = StageFactory()
    field = StageSubmissionFieldFactory(stage=stage)
    with pytest.raises(StageNotFound):
        send(delivery_leader, delivery_project, stage, field)


def closed_delivery_stage(project):
    now = timezone.now()
    stage = StageFactory(
        edition=project.edition,
        starts_at=now - timedelta(days=5),
        ends_at=now - timedelta(days=1),
    )
    return stage, StageSubmissionFieldFactory(stage=stage)


def test_envio_recusa_prazo_encerrado(delivery_project, delivery_leader):
    stage, field = closed_delivery_stage(delivery_project)
    with pytest.raises(StageDeadlineClosed):
        send(delivery_leader, delivery_project, stage, field)


def test_envio_com_prorrogacao_funciona(delivery_project, delivery_leader):
    stage, field = closed_delivery_stage(delivery_project)
    DeadlineExtensionFactory(
        project=delivery_project,
        stage=stage,
        ends_at=timezone.now() + timedelta(days=1),
    )
    assert send(delivery_leader, delivery_project, stage, field).number == 1


def test_envio_recusa_antes_do_inicio(delivery_project, delivery_leader):
    now = timezone.now()
    stage = StageFactory(
        edition=delivery_project.edition,
        starts_at=now + timedelta(days=1),
        ends_at=now + timedelta(days=5),
    )
    field = StageSubmissionFieldFactory(stage=stage)
    with pytest.raises(StageNotOpen):
        send(delivery_leader, delivery_project, stage, field)


def test_envio_recusa_itens_invalidos(
    delivery_project, delivery_leader, delivery_stage, link_field
):
    with pytest.raises(ValidationError):
        submit_stage_delivery(
            actor=delivery_leader,
            project=delivery_project,
            stage=delivery_stage,
            items=[],
        )


def test_falha_nao_grava_nada(delivery_project, delivery_leader):
    stage, field = closed_delivery_stage(delivery_project)
    with pytest.raises(StageDeadlineClosed):
        send(delivery_leader, delivery_project, stage, field)

    assert Submission.objects.count() == 0
    assert SubmissionVersion.objects.count() == 0
    assert SubmissionItem.objects.count() == 0
    assert SubmissionReceipt.objects.count() == 0
