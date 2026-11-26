from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, IntegrityError
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import NotAdminActor
from apps.accounts.factories import StudentFactory, TeacherFactory, UserFactory
from apps.editions.enums import EditionStatus, FieldKind
from apps.editions.exceptions import EditionClosed
from apps.editions.factories import (
    CategoryFactory,
    ChallengeFactory,
    EditionFactory,
    StageFactory,
    StageSubmissionFieldFactory,
)
from apps.notifications.models import Notification, NotificationType
from apps.projects.exceptions import (
    CategoryNotAvailable,
    ChallengeNotEligible,
    ChallengeNotSelected,
    DeadlineExtensionAlreadyGranted,
    FileFormatNotAllowed,
    FileTooLarge,
    FormationClosed,
    NotTeamLeader,
    ProjectNotFound,
    ProjectTitleTaken,
    StageDeadlineClosed,
    StageNotFound,
    StageNotOpen,
    StorageUnavailable,
    TeamDisqualified,
    TeamIncomplete,
)
from apps.projects.factories import DeadlineExtensionFactory, ProjectFactory
from apps.projects.files import get_delivery_storage
from apps.projects.models import (
    DeadlineExtension,
    Project,
    Submission,
    SubmissionItem,
    SubmissionReceipt,
    SubmissionVersion,
)
from apps.projects.selectors import get_submission_deadline
from apps.projects.tests.conftest import stored_keys, valid_canvas, valid_swot
from apps.projects.use_cases import save_project_details as save_module
from apps.projects.use_cases.extend_deadline import extend_deadline
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


def test_envio_cria_um_comprovante_com_codigo_hexadecimal(
    delivery_project, delivery_leader, delivery_stage, link_field
):
    version = send(delivery_leader, delivery_project, delivery_stage, link_field)

    assert SubmissionReceipt.objects.filter(version=version).count() == 1
    code = version.receipt.verification_code
    assert len(code) == 32
    assert int(code, 16) >= 0
    assert version.receipt.file_url == ""


def test_dois_envios_geram_codigos_diferentes_e_preservam_o_primeiro(
    delivery_project, delivery_leader, delivery_stage, link_field
):
    first = send(delivery_leader, delivery_project, delivery_stage, link_field)
    original = (
        first.receipt.pk,
        first.receipt.verification_code,
        first.receipt.generated_at,
    )

    second = send(delivery_leader, delivery_project, delivery_stage, link_field)

    assert SubmissionReceipt.objects.count() == 2
    assert second.receipt.verification_code != original[1]
    first.receipt.refresh_from_db()
    assert (
        first.receipt.pk,
        first.receipt.verification_code,
        first.receipt.generated_at,
    ) == original


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
    assert SubmissionReceipt.objects.count() == 0


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
    assert SubmissionReceipt.objects.count() == 0


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


# Enviar a entrega da etapa com arquivos (UC34, RF31)


@pytest.fixture
def file_field(delivery_stage):
    return StageSubmissionFieldFactory(
        stage=delivery_stage, kind=FieldKind.FILE, formats="pdf", max_size_mb=1
    )


def pdf(name="relatorio.pdf", content=b"%PDF-1.7 conteudo"):
    return SimpleUploadedFile(name, content)


def send_file(actor, project, stage, field, upload=None, **extra):
    return submit_stage_delivery(
        actor=actor,
        project=project,
        stage=stage,
        items=[{"field": field, "file": upload or pdf()}],
        **extra,
    )


def test_envio_com_arquivo_cria_item_e_grava_no_armazenamento(
    delivery_project,
    delivery_leader,
    delivery_stage,
    file_field,
    delivery_storage_root,
):
    version = send_file(
        delivery_leader,
        delivery_project,
        delivery_stage,
        file_field,
        pdf("Meu Relatório.pdf"),
    )

    item = version.items.get()
    assert (item.field, item.kind, item.link) == (file_field, "FILE", "")
    assert item.file_name == "Meu_Relatório.pdf"
    assert item.size_bytes == len(b"%PDF-1.7 conteudo")
    assert item.file_url.startswith(
        f"deliveries/{delivery_project.pk}/{delivery_stage.pk}/v1/"
    )
    assert item.file_url.endswith(".pdf")
    assert "Relat" not in item.file_url
    assert stored_keys(delivery_storage_root) == [item.file_url]


def test_envio_com_link_e_arquivo_na_mesma_versao(
    delivery_project, delivery_leader, delivery_stage, link_field, file_field
):
    version = submit_stage_delivery(
        actor=delivery_leader,
        project=delivery_project,
        stage=delivery_stage,
        items=[
            {"field": link_field, "link": "https://github.com/equipe/p"},
            {"field": file_field, "file": pdf()},
        ],
    )
    assert sorted(version.items.values_list("kind", flat=True)) == ["FILE", "LINK"]


def test_segundo_envio_preserva_o_arquivo_da_versao_1(
    delivery_project,
    delivery_leader,
    delivery_stage,
    file_field,
    delivery_storage_root,
):
    first = send_file(delivery_leader, delivery_project, delivery_stage, file_field)
    second = send_file(delivery_leader, delivery_project, delivery_stage, file_field)

    first_item, second_item = first.items.get(), second.items.get()
    assert (first.number, second.number) == (1, 2)
    assert first_item.file_url != second_item.file_url
    assert stored_keys(delivery_storage_root) == sorted(
        [first_item.file_url, second_item.file_url]
    )


@pytest.mark.parametrize(
    "violation",
    ["not_leader", "closed_edition", "disqualified", "incomplete", "deadline"],
)
def test_regra_violada_nao_grava_arquivo(
    violation,
    delivery_project,
    delivery_leader,
    delivery_stage,
    file_field,
    delivery_storage_root,
):
    actor = delivery_leader
    stage, field = delivery_stage, file_field
    expected = {
        "not_leader": NotTeamLeader,
        "closed_edition": EditionClosed,
        "disqualified": TeamDisqualified,
        "incomplete": TeamIncomplete,
        "deadline": StageDeadlineClosed,
    }[violation]
    if violation == "not_leader":
        actor = TeamMemberFactory(team=delivery_project.team).student.user
    elif violation == "closed_edition":
        delivery_project.edition.status = "CLOSED"
        delivery_project.edition.save()
    elif violation == "disqualified":
        team = TeamFactory(edition=delivery_stage.edition, disqualified=True)
        delivery_project = ProjectFactory(team=team)
        actor = team.members.get(role=MemberRole.LEADER).student.user
    elif violation == "incomplete":
        delivery_project.team.situation = TeamSituation.INCOMPLETE
        delivery_project.team.save()
    else:
        stage, _ = closed_delivery_stage(delivery_project)
        field = StageSubmissionFieldFactory(stage=stage, kind=FieldKind.FILE)

    with pytest.raises(expected):
        send_file(actor, delivery_project, stage, field)

    assert stored_keys(delivery_storage_root) == []
    assert SubmissionVersion.objects.count() == 0


@pytest.mark.parametrize(
    ("upload", "error"),
    [
        (pdf("a.txt", b"texto"), FileFormatNotAllowed),
        (pdf("a.pdf", b"%PDF" + b"0" * (1024 * 1024 + 1)), FileTooLarge),
        (pdf("a.pdf", b"texto que nao e pdf"), FileFormatNotAllowed),
        (pdf("a.pdf", b""), ValidationError),
    ],
)
def test_arquivo_invalido_nao_deixa_arquivo_versao_nem_item(
    upload,
    error,
    delivery_project,
    delivery_leader,
    delivery_stage,
    file_field,
    delivery_storage_root,
):
    with pytest.raises(error):
        send_file(delivery_leader, delivery_project, delivery_stage, file_field, upload)

    assert stored_keys(delivery_storage_root) == []
    assert SubmissionVersion.objects.count() == 0
    assert SubmissionItem.objects.count() == 0


def test_campo_de_arquivo_obrigatorio_sem_item_e_recusado(
    delivery_project, delivery_leader, delivery_stage, link_field, file_field
):
    with pytest.raises(ValidationError):
        send(delivery_leader, delivery_project, delivery_stage, link_field)
    assert SubmissionVersion.objects.count() == 0


def test_falha_depois_de_gravar_apaga_o_arquivo_e_as_linhas(
    delivery_project,
    delivery_leader,
    delivery_stage,
    file_field,
    delivery_storage_root,
    monkeypatch,
):
    def broken(*args, **kwargs):
        raise RuntimeError("falha no comprovante")

    monkeypatch.setattr(SubmissionReceipt.objects, "create", broken)

    with pytest.raises(RuntimeError):
        send_file(delivery_leader, delivery_project, delivery_stage, file_field)

    assert stored_keys(delivery_storage_root) == []
    assert Submission.objects.count() == 0
    assert SubmissionVersion.objects.count() == 0
    assert SubmissionItem.objects.count() == 0


def test_falha_do_armazenamento_vira_storage_unavailable_sem_linhas(
    delivery_project,
    delivery_leader,
    delivery_stage,
    file_field,
    delivery_storage_root,
    monkeypatch,
):
    def broken(*args, **kwargs):
        raise OSError("disco cheio")

    monkeypatch.setattr(get_delivery_storage().__class__, "save", broken)

    with pytest.raises(StorageUnavailable):
        send_file(delivery_leader, delivery_project, delivery_stage, file_field)

    assert SubmissionVersion.objects.count() == 0
    assert SubmissionItem.objects.count() == 0
    assert stored_keys(delivery_storage_root) == []


def test_envio_com_canvas_e_swot_grava_o_conteudo(
    delivery_project, delivery_leader, delivery_stage
):
    canvas = StageSubmissionFieldFactory(stage=delivery_stage, kind=FieldKind.CANVAS)
    swot = StageSubmissionFieldFactory(stage=delivery_stage, kind=FieldKind.SWOT)

    version = submit_stage_delivery(
        actor=delivery_leader,
        project=delivery_project,
        stage=delivery_stage,
        items=[
            {"field": canvas, "content": valid_canvas()},
            {"field": swot, "content": valid_swot()},
        ],
    )

    items = {item.field_id: item for item in version.items.all()}
    assert items[canvas.pk].kind == FieldKind.CANVAS
    assert items[canvas.pk].content == valid_canvas()
    assert items[swot.pk].kind == FieldKind.SWOT
    assert items[swot.pk].content == valid_swot()
    assert version.receipt.verification_code


def test_canvas_incompleto_nao_grava_nada(
    delivery_project, delivery_leader, delivery_stage
):
    canvas = StageSubmissionFieldFactory(stage=delivery_stage, kind=FieldKind.CANVAS)

    with pytest.raises(ValidationError):
        submit_stage_delivery(
            actor=delivery_leader,
            project=delivery_project,
            stage=delivery_stage,
            items=[{"field": canvas, "content": {"channels": "só um bloco"}}],
        )

    assert not SubmissionVersion.objects.filter(
        submission__project=delivery_project
    ).exists()


def test_envio_notifica_apenas_integrantes_ativos(
    delivery_project, delivery_leader, delivery_stage, link_field
):
    ativo = TeamMemberFactory(team=delivery_project.team)
    inativo = TeamMemberFactory(
        team=delivery_project.team, active=False, left_at=timezone.now()
    )

    send(delivery_leader, delivery_project, delivery_stage, link_field)

    notifs = Notification.objects.filter(type=NotificationType.DELIVERABLE)
    destinatarios = set(notifs.values_list("user_id", flat=True))
    assert destinatarios == {delivery_leader.id, ativo.student.user_id}
    assert inativo.student.user_id not in destinatarios


def test_envio_nao_quebra_se_notificacao_falhar(
    delivery_project, delivery_leader, delivery_stage, link_field
):
    with patch(
        "apps.notifications.services.Notification.objects.create",
        side_effect=DatabaseError("erro simulado"),
    ):
        version = send(delivery_leader, delivery_project, delivery_stage, link_field)

    assert SubmissionVersion.objects.filter(pk=version.pk).exists()
    assert Notification.objects.count() == 0


# --- extend_deadline (UC14, RF14) ---


@pytest.fixture
def admin():
    return UserFactory(role=UserRole.ADMIN)


def extend(actor, project, stage, **extra):
    fields = {
        "ends_at": stage.ends_at + timedelta(days=3),
        "reason": "Atestado médico do líder.",
        **extra,
    }
    return extend_deadline(actor=actor, project=project, stage=stage, **fields)


def test_extend_deadline_grava_a_prorrogacao(admin, delivery_project):
    stage, _ = closed_delivery_stage(delivery_project)
    novo_prazo = stage.ends_at + timedelta(days=3)

    extensao = extend(admin, delivery_project, stage, ends_at=novo_prazo)

    assert extensao.granted_by == admin
    assert extensao.project == delivery_project
    assert extensao.stage == stage
    assert extensao.ends_at == novo_prazo
    assert extensao.reason == "Atestado médico do líder."
    assert extensao.granted_at is not None
    assert DeadlineExtension.objects.count() == 1


def test_extend_deadline_tira_espacos_da_justificativa(admin, delivery_project):
    stage, _ = closed_delivery_stage(delivery_project)
    assert extend(admin, delivery_project, stage, reason="  Atestado  ").reason == (
        "Atestado"
    )


@pytest.mark.parametrize("papel", [StudentFactory, TeacherFactory])
def test_extend_deadline_exige_admin(papel, delivery_project):
    stage, _ = closed_delivery_stage(delivery_project)
    with pytest.raises(NotAdminActor):
        extend(papel().user, delivery_project, stage)
    assert DeadlineExtension.objects.count() == 0


def test_extend_deadline_barra_segunda_prorrogacao_da_etapa(admin, delivery_project):
    stage, _ = closed_delivery_stage(delivery_project)
    primeira = extend(admin, delivery_project, stage)

    with pytest.raises(DeadlineExtensionAlreadyGranted):
        extend(admin, delivery_project, stage, ends_at=primeira.ends_at + timedelta(1))

    primeira.refresh_from_db()
    assert DeadlineExtension.objects.count() == 1
    assert primeira.ends_at == stage.ends_at + timedelta(days=3)


def test_extend_deadline_corrida_vira_conflito(admin, delivery_project, monkeypatch):
    stage, _ = closed_delivery_stage(delivery_project)

    def corrida(self, *args, **kwargs):
        raise IntegrityError("unique_extension_per_stage")

    monkeypatch.setattr(DeadlineExtension, "save", corrida)

    with pytest.raises(DeadlineExtensionAlreadyGranted):
        extend(admin, delivery_project, stage)


def test_extend_deadline_barra_etapa_de_outra_edicao(admin, delivery_project):
    stage = StageFactory()
    with pytest.raises(ValidationError):
        extend(admin, delivery_project, stage)
    assert DeadlineExtension.objects.count() == 0


@pytest.mark.parametrize("diferenca", [timedelta(0), timedelta(hours=-1)])
def test_extend_deadline_exige_prazo_depois_do_fim_da_etapa(
    admin, delivery_project, diferenca
):
    stage, _ = closed_delivery_stage(delivery_project)
    with pytest.raises(ValidationError):
        extend(admin, delivery_project, stage, ends_at=stage.ends_at + diferenca)
    assert DeadlineExtension.objects.count() == 0


@pytest.mark.parametrize("justificativa", ["", "   "])
def test_extend_deadline_exige_justificativa(admin, delivery_project, justificativa):
    stage, _ = closed_delivery_stage(delivery_project)
    with pytest.raises(ValidationError):
        extend(admin, delivery_project, stage, reason=justificativa)
    assert DeadlineExtension.objects.count() == 0


def test_extend_deadline_barra_edicao_encerrada(admin, delivery_project):
    stage, _ = closed_delivery_stage(delivery_project)
    delivery_project.edition.status = EditionStatus.CLOSED
    delivery_project.edition.save()
    with pytest.raises(EditionClosed):
        extend(admin, delivery_project, stage)


def test_extend_deadline_aceita_equipe_desclassificada(admin):
    project = ProjectFactory(team=TeamFactory(disqualified=True))
    stage, _ = closed_delivery_stage(project)
    assert extend(admin, project, stage).pk is not None


def test_prorrogacao_reabre_o_envio_da_etapa_vencida(
    admin, delivery_project, delivery_leader
):
    stage, field = closed_delivery_stage(delivery_project)
    with pytest.raises(StageDeadlineClosed):
        send(delivery_leader, delivery_project, stage, field)
    novo_prazo = timezone.now() + timedelta(days=1)

    extend(admin, delivery_project, stage, ends_at=novo_prazo)

    assert get_submission_deadline(delivery_project, stage) == novo_prazo
    assert send(delivery_leader, delivery_project, stage, field).number == 1
