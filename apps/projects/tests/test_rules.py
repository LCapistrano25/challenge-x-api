from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.factories import StudentFactory, UserFactory
from apps.core.factories import CourseFactory
from apps.editions.enums import FieldKind, StageKind
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
    FileFormatNotAllowed,
    FileTooLarge,
    FormationClosed,
    NotTeamLeader,
    ProjectNotFound,
    StageDeadlineClosed,
    StageNotFound,
    StageNotOpen,
    TeamDisqualified,
    TeamIncomplete,
)
from apps.projects.factories import DeadlineExtensionFactory, ProjectFactory
from apps.projects.rules import (
    CONTENT_TEXT_MAX_LENGTH,
    SWOT_QUADRANT_MAX_ITEMS,
    ensure_actor_is_team_leader,
    ensure_category_available,
    ensure_challenge_eligible,
    ensure_file_matches_field,
    ensure_formation_period_is_open,
    ensure_items_match_stage_fields,
    ensure_project_has_challenge,
    ensure_stage_accepts_delivery,
    ensure_stage_deadline_open,
    ensure_team_has_project,
    ensure_team_not_disqualified,
    ensure_team_not_incomplete,
)
from apps.projects.tests.conftest import valid_canvas, valid_swot
from apps.teams.enums import MemberRole, TeamSituation
from apps.teams.factories import TeamFactory, TeamMemberFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def team():
    return TeamFactory()


def leader_user(team):
    return team.members.get(role=MemberRole.LEADER).student.user


def leader_course(team):
    return team.members.get(role=MemberRole.LEADER).student.course


def leave(member):
    member.active = False
    member.left_at = timezone.now()
    member.save()


# Líder da equipe (RF29, RF30)


def test_lider_ativo_passa(team):
    ensure_actor_is_team_leader(team, leader_user(team))


def test_integrante_comum_nao_e_lider(team):
    membro = TeamMemberFactory(team=team)
    with pytest.raises(NotTeamLeader):
        ensure_actor_is_team_leader(team, membro.student.user)


def test_ex_lider_inativo_nao_e_lider(team):
    leave(team.members.get(role=MemberRole.LEADER))
    with pytest.raises(NotTeamLeader):
        ensure_actor_is_team_leader(team, leader_user(team))


def test_lider_de_outra_equipe_nao_e_lider(team):
    with pytest.raises(NotTeamLeader):
        ensure_actor_is_team_leader(team, leader_user(TeamFactory()))


def test_admin_nao_e_lider(team):
    with pytest.raises(NotTeamLeader):
        ensure_actor_is_team_leader(team, UserFactory(role=UserRole.ADMIN))


def test_sem_ator_nao_e_lider(team):
    with pytest.raises(NotTeamLeader):
        ensure_actor_is_team_leader(team, None)


# Prazo de formação (RF29)


def formation(edition, start, end):
    now = timezone.now()
    return StageFactory(
        formation=True, edition=edition, starts_at=now + start, ends_at=now + end
    )


def test_prazo_aberto_passa(team):
    formation(team.edition, -timedelta(days=1), timedelta(days=1))
    ensure_formation_period_is_open(team.edition)


def test_prazo_que_ainda_nao_comecou_esta_fechado(team):
    formation(team.edition, timedelta(days=1), timedelta(days=2))
    with pytest.raises(FormationClosed):
        ensure_formation_period_is_open(team.edition)


def test_prazo_encerrado_esta_fechado(team):
    formation(team.edition, -timedelta(days=2), -timedelta(days=1))
    with pytest.raises(FormationClosed):
        ensure_formation_period_is_open(team.edition)


def test_sem_etapa_de_formacao_esta_fechado(team):
    with pytest.raises(FormationClosed):
        ensure_formation_period_is_open(team.edition)


def test_etapa_de_formacao_de_outra_edicao_nao_vale(team):
    formation(EditionFactory(), -timedelta(days=1), timedelta(days=1))
    with pytest.raises(FormationClosed):
        ensure_formation_period_is_open(team.edition)


def test_etapa_que_nao_e_de_formacao_nao_vale(team):
    now = timezone.now()
    StageFactory(
        edition=team.edition,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=1),
    )
    with pytest.raises(FormationClosed):
        ensure_formation_period_is_open(team.edition)


# Desafio elegível (RF29)


def test_desafio_de_curso_de_integrante_ativo_passa(team):
    desafio = ChallengeFactory(edition=team.edition, course=leader_course(team))
    ensure_challenge_eligible(team, desafio)


def test_desafio_de_curso_de_outro_integrante_ativo_passa(team):
    curso = CourseFactory()
    TeamMemberFactory(team=team, student=StudentFactory(course=curso))
    desafio = ChallengeFactory(edition=team.edition, course=curso)
    ensure_challenge_eligible(team, desafio)


def test_desafio_de_curso_sem_integrante_e_recusado(team):
    with pytest.raises(ChallengeNotEligible):
        ensure_challenge_eligible(team, ChallengeFactory(edition=team.edition))


def test_desafio_de_curso_so_de_ex_integrante_e_recusado(team):
    curso = CourseFactory()
    leave(TeamMemberFactory(team=team, student=StudentFactory(course=curso)))
    desafio = ChallengeFactory(edition=team.edition, course=curso)
    with pytest.raises(ChallengeNotEligible):
        ensure_challenge_eligible(team, desafio)


def test_desafio_inativo_e_recusado(team):
    desafio = ChallengeFactory(
        edition=team.edition, course=leader_course(team), active=False
    )
    with pytest.raises(ChallengeNotEligible):
        ensure_challenge_eligible(team, desafio)


def test_desafio_de_outra_edicao_e_recusado(team):
    desafio = ChallengeFactory(edition=EditionFactory(), course=leader_course(team))
    with pytest.raises(ChallengeNotEligible):
        ensure_challenge_eligible(team, desafio)


# Desafio já escolhido (RF30)


def test_projeto_com_desafio_passa():
    ensure_project_has_challenge(ProjectFactory())


def test_projeto_sem_desafio_e_recusado():
    with pytest.raises(ChallengeNotSelected):
        ensure_project_has_challenge(ProjectFactory(challenge=None))


# Projeto da equipe já existe (RF30)


def test_equipe_com_projeto_passa(team):
    ProjectFactory(team=team)
    ensure_team_has_project(team)


def test_equipe_sem_projeto_e_recusada(team):
    with pytest.raises(ProjectNotFound):
        ensure_team_has_project(team)


# Categoria disponível (RF30, RF49)


def test_categoria_ativa_da_edicao_passa(team):
    ensure_category_available(team, CategoryFactory(edition=team.edition))


def test_categoria_inativa_e_recusada(team):
    categoria = CategoryFactory(edition=team.edition, active=False)
    with pytest.raises(CategoryNotAvailable):
        ensure_category_available(team, categoria)


def test_categoria_de_outra_edicao_e_recusada(team):
    with pytest.raises(CategoryNotAvailable):
        ensure_category_available(team, CategoryFactory())


# Entrega da etapa (UC34, RF31)


def open_stage(edition, **fields):
    now = timezone.now()
    defaults = {
        "starts_at": now - timedelta(days=1),
        "ends_at": now + timedelta(days=1),
    }
    return StageFactory(edition=edition, **{**defaults, **fields})


def closed_stage(edition, **fields):
    now = timezone.now()
    return open_stage(
        edition,
        starts_at=now - timedelta(days=5),
        ends_at=now - timedelta(days=1),
        **fields,
    )


def test_equipe_ativa_passa_na_desclassificacao(team):
    ensure_team_not_disqualified(team)


def test_equipe_desclassificada_e_recusada():
    with pytest.raises(TeamDisqualified):
        ensure_team_not_disqualified(TeamFactory(disqualified=True))


@pytest.mark.parametrize("situation", [None, TeamSituation.COMPLETE])
def test_equipe_completa_ou_sem_situacao_passa(situation):
    ensure_team_not_incomplete(TeamFactory(situation=situation))


@pytest.mark.parametrize(
    "situation", [TeamSituation.INCOMPLETE, TeamSituation.REQUIREMENTS_NOT_MET]
)
def test_equipe_incompleta_e_recusada(situation):
    with pytest.raises(TeamIncomplete):
        ensure_team_not_incomplete(TeamFactory(situation=situation))


def test_etapa_de_entrega_da_edicao_passa():
    project = ProjectFactory()
    ensure_stage_accepts_delivery(project, open_stage(project.edition))


def test_etapa_de_formacao_e_recusada():
    project = ProjectFactory()
    stage = StageFactory(formation=True, edition=project.edition)
    with pytest.raises(StageNotFound):
        ensure_stage_accepts_delivery(project, stage)


def test_etapa_final_e_recusada():
    project = ProjectFactory()
    stage = StageFactory(edition=project.edition, kind=StageKind.FINAL, scored=False)
    with pytest.raises(StageNotFound):
        ensure_stage_accepts_delivery(project, stage)


def test_etapa_de_outra_edicao_e_recusada():
    with pytest.raises(StageNotFound):
        ensure_stage_accepts_delivery(ProjectFactory(), StageFactory())


def test_prazo_de_entrega_aberto_passa():
    project = ProjectFactory()
    ensure_stage_deadline_open(project, open_stage(project.edition))


def test_prazo_encerrado_e_recusado():
    project = ProjectFactory()
    with pytest.raises(StageDeadlineClosed):
        ensure_stage_deadline_open(project, closed_stage(project.edition))


def test_prorrogacao_ativa_libera_o_prazo_encerrado():
    project = ProjectFactory()
    stage = closed_stage(project.edition)
    DeadlineExtensionFactory(
        project=project, stage=stage, ends_at=timezone.now() + timedelta(days=1)
    )
    ensure_stage_deadline_open(project, stage)


def test_prorrogacao_vencida_e_recusada():
    project = ProjectFactory()
    stage = closed_stage(project.edition)
    DeadlineExtensionFactory(
        project=project, stage=stage, ends_at=stage.ends_at + timedelta(hours=1)
    )
    with pytest.raises(StageDeadlineClosed):
        ensure_stage_deadline_open(project, stage)


def test_antes_do_inicio_e_recusado():
    project = ProjectFactory()
    now = timezone.now()
    stage = open_stage(
        project.edition,
        starts_at=now + timedelta(days=1),
        ends_at=now + timedelta(days=5),
    )
    with pytest.raises(StageNotOpen):
        ensure_stage_deadline_open(project, stage)


@pytest.fixture
def stage():
    return StageFactory()


def link_item(field, link="https://github.com/equipe/projeto"):
    return {"field": field, "link": link}


def test_itens_completos_passam(stage):
    field = StageSubmissionFieldFactory(stage=stage)
    ensure_items_match_stage_fields(stage, [link_item(field)])


def test_campo_obrigatorio_sem_resposta_e_recusado(stage):
    answered = StageSubmissionFieldFactory(stage=stage)
    StageSubmissionFieldFactory(stage=stage, required=True)
    with pytest.raises(ValidationError):
        ensure_items_match_stage_fields(stage, [link_item(answered)])


def test_campo_opcional_pode_faltar(stage):
    answered = StageSubmissionFieldFactory(stage=stage)
    StageSubmissionFieldFactory(stage=stage, required=False)
    ensure_items_match_stage_fields(stage, [link_item(answered)])


def test_campo_de_outra_etapa_e_recusado(stage):
    StageSubmissionFieldFactory(stage=stage)
    other = StageSubmissionFieldFactory()
    with pytest.raises(ValidationError):
        ensure_items_match_stage_fields(stage, [link_item(other)])


def test_campo_repetido_e_recusado(stage):
    field = StageSubmissionFieldFactory(stage=stage)
    with pytest.raises(ValidationError):
        ensure_items_match_stage_fields(stage, [link_item(field), link_item(field)])


def file_item(field, name="relatorio.pdf", content=b"%PDF-1.7 conteudo"):
    return {"field": field, "file": SimpleUploadedFile(name, content)}


def test_item_de_arquivo_em_campo_de_arquivo_passa(stage):
    field = StageSubmissionFieldFactory(stage=stage, kind=FieldKind.FILE)
    ensure_items_match_stage_fields(stage, [file_item(field)])


def test_link_e_arquivo_juntos_passam(stage):
    link_field = StageSubmissionFieldFactory(stage=stage)
    file_field = StageSubmissionFieldFactory(stage=stage, kind=FieldKind.FILE)
    items = [link_item(link_field), file_item(file_field)]
    ensure_items_match_stage_fields(stage, items)


def test_campo_de_arquivo_obrigatorio_sem_resposta_e_recusado(stage):
    link_field = StageSubmissionFieldFactory(stage=stage)
    StageSubmissionFieldFactory(stage=stage, kind=FieldKind.FILE, required=True)
    with pytest.raises(ValidationError):
        ensure_items_match_stage_fields(stage, [link_item(link_field)])


def test_campo_de_arquivo_opcional_pode_faltar(stage):
    link_field = StageSubmissionFieldFactory(stage=stage)
    StageSubmissionFieldFactory(stage=stage, kind=FieldKind.FILE, required=False)
    ensure_items_match_stage_fields(stage, [link_item(link_field)])


def test_link_em_campo_de_arquivo_e_recusado(stage):
    field = StageSubmissionFieldFactory(stage=stage, kind=FieldKind.FILE)
    with pytest.raises(ValidationError):
        ensure_items_match_stage_fields(stage, [link_item(field)])


def test_arquivo_em_campo_de_link_e_recusado(stage):
    field = StageSubmissionFieldFactory(stage=stage)
    with pytest.raises(ValidationError):
        ensure_items_match_stage_fields(stage, [file_item(field)])


def test_lista_de_itens_vazia_e_recusada(stage):
    with pytest.raises(ValidationError):
        ensure_items_match_stage_fields(stage, [])


# --- Arquivo da entrega (ensure_file_matches_field) ---

MB = 1024 * 1024


def file_field(**kwargs):
    return StageSubmissionFieldFactory(kind=FieldKind.FILE, **kwargs)


def upload(name="relatorio.pdf", content=b"%PDF-1.7 conteudo"):
    return SimpleUploadedFile(name, content)


@pytest.mark.parametrize("name", ["a.pdf", "a.PDF", "a.Pdf"])
def test_extensao_permitida_passa_sem_diferenciar_caixa(name):
    ensure_file_matches_field(file_field(formats="pdf, docx"), upload(name))


@pytest.mark.parametrize("formats", ["pdf", ".pdf", "PDF", "docx;pdf", "docx .pdf"])
def test_formatos_aceitam_ponto_caixa_e_separadores(formats):
    ensure_file_matches_field(file_field(formats=formats), upload())


def test_extensao_fora_dos_formatos_e_recusada():
    with pytest.raises(FileFormatNotAllowed):
        ensure_file_matches_field(file_field(formats="pdf"), upload("a.txt", b"texto"))


def test_formatos_vazios_aceitam_qualquer_extensao():
    ensure_file_matches_field(file_field(formats=""), upload("a.txt", b"texto"))


@pytest.mark.parametrize("name", ["a.exe", "a.sh", "a.JS", "a.bat"])
def test_extensao_bloqueada_e_recusada_mesmo_sem_formatos(name):
    with pytest.raises(FileFormatNotAllowed):
        ensure_file_matches_field(file_field(formats=""), upload(name, b"x"))


def test_extensao_bloqueada_e_recusada_mesmo_que_o_campo_permita():
    with pytest.raises(FileFormatNotAllowed):
        ensure_file_matches_field(file_field(formats="exe"), upload("a.exe", b"x"))


def test_arquivo_sem_extensao_e_recusado():
    with pytest.raises(FileFormatNotAllowed):
        ensure_file_matches_field(file_field(formats=""), upload("relatorio", b"x"))


def test_arquivo_vazio_e_recusado():
    with pytest.raises(ValidationError):
        ensure_file_matches_field(file_field(), upload("a.pdf", b""))


def test_arquivo_acima_do_limite_do_campo_e_recusado():
    big = upload("a.pdf", b"%PDF" + b"0" * (MB + 1))
    with pytest.raises(FileTooLarge):
        ensure_file_matches_field(file_field(max_size_mb=1), big)


def test_arquivo_no_limite_exato_passa():
    exact = upload("a.pdf", b"%PDF" + b"0" * (MB - 4))
    ensure_file_matches_field(file_field(max_size_mb=1), exact)


def test_campo_sem_limite_usa_o_teto_global(settings):
    settings.DELIVERY_MAX_FILE_MB = 1
    big = upload("a.pdf", b"%PDF" + b"0" * (MB + 1))
    with pytest.raises(FileTooLarge):
        ensure_file_matches_field(file_field(max_size_mb=None), big)


def test_campo_acima_do_teto_vale_o_teto(settings):
    settings.DELIVERY_MAX_FILE_MB = 1
    big = upload("a.pdf", b"%PDF" + b"0" * (MB + 1))
    with pytest.raises(FileTooLarge):
        ensure_file_matches_field(file_field(max_size_mb=20), big)


def test_conteudo_que_nao_bate_com_a_extensao_e_recusado():
    with pytest.raises(FileFormatNotAllowed):
        ensure_file_matches_field(file_field(), upload("a.pdf", b"isto e texto"))


def test_assinatura_do_zip_vale_para_docx():
    ensure_file_matches_field(file_field(), upload("a.docx", b"PK\x03\x04resto"))


def test_validar_o_arquivo_nao_consome_o_conteudo():
    uploaded = upload()
    ensure_file_matches_field(file_field(), uploaded)
    assert uploaded.read() == b"%PDF-1.7 conteudo"


# Canvas e SWOT: formato fixo do conteúdo (RF31)


def content_item(field, content):
    return {"field": field, "content": content}


@pytest.fixture
def canvas_field(stage):
    return StageSubmissionFieldFactory(stage=stage, kind=FieldKind.CANVAS)


@pytest.fixture
def swot_field(stage):
    return StageSubmissionFieldFactory(stage=stage, kind=FieldKind.SWOT)


def test_canvas_e_swot_completos_sao_aceitos(stage, canvas_field, swot_field):
    ensure_items_match_stage_fields(
        stage,
        [
            content_item(canvas_field, valid_canvas()),
            content_item(swot_field, valid_swot()),
        ],
    )


def with_block(**changes):
    return {**valid_canvas(), **changes}


@pytest.mark.parametrize(
    "content",
    [
        {k: v for k, v in valid_canvas().items() if k != "channels"},
        with_block(extra="x"),
        with_block(channels="   "),
        with_block(channels=["lista"]),
        with_block(channels="x" * (CONTENT_TEXT_MAX_LENGTH + 1)),
        ["não é objeto"],
    ],
    ids=[
        "bloco-faltando",
        "chave-desconhecida",
        "bloco-vazio",
        "bloco-lista",
        "bloco-longo",
        "lista",
    ],
)
def test_canvas_incompleto_ou_fora_do_formato_e_recusado(stage, canvas_field, content):
    with pytest.raises(ValidationError):
        ensure_items_match_stage_fields(stage, [content_item(canvas_field, content)])


@pytest.mark.parametrize(
    "content",
    [
        {k: v for k, v in valid_swot().items() if k != "threats"},
        {**valid_swot(), "extra": ["x"]},
        {**valid_swot(), "threats": []},
        {**valid_swot(), "threats": ["ok", " "]},
        {**valid_swot(), "threats": "texto solto"},
        {**valid_swot(), "threats": ["x"] * (SWOT_QUADRANT_MAX_ITEMS + 1)},
        {**valid_swot(), "threats": ["x" * (CONTENT_TEXT_MAX_LENGTH + 1)]},
    ],
    ids=[
        "quadrante-faltando",
        "chave-desconhecida",
        "lista-vazia",
        "texto-vazio",
        "texto",
        "itens-demais",
        "texto-longo",
    ],
)
def test_swot_incompleto_ou_fora_do_formato_e_recusado(stage, swot_field, content):
    with pytest.raises(ValidationError):
        ensure_items_match_stage_fields(stage, [content_item(swot_field, content)])


def test_conteudo_em_campo_link_e_link_em_campo_canvas_sao_recusados(
    stage, canvas_field
):
    link_field = StageSubmissionFieldFactory(stage=stage, kind=FieldKind.LINK)
    with pytest.raises(ValidationError):
        ensure_items_match_stage_fields(
            stage, [content_item(link_field, valid_canvas())]
        )
    with pytest.raises(ValidationError):
        ensure_items_match_stage_fields(stage, [link_item(canvas_field)])


def test_canvas_obrigatorio_nao_respondido_e_recusado(stage, canvas_field):
    answered = StageSubmissionFieldFactory(stage=stage)
    with pytest.raises(ValidationError):
        ensure_items_match_stage_fields(stage, [link_item(answered)])


def test_canvas_e_swot_no_limite_de_tamanho_sao_aceitos(
    stage, canvas_field, swot_field
):
    canvas = with_block(channels="x" * CONTENT_TEXT_MAX_LENGTH)
    swot = {
        **valid_swot(),
        "threats": ["x" * CONTENT_TEXT_MAX_LENGTH] * SWOT_QUADRANT_MAX_ITEMS,
    }

    ensure_items_match_stage_fields(
        stage, [content_item(canvas_field, canvas), content_item(swot_field, swot)]
    )


def test_canvas_opcional_pode_ficar_sem_item(stage):
    answered = StageSubmissionFieldFactory(stage=stage)
    StageSubmissionFieldFactory(stage=stage, kind=FieldKind.CANVAS, required=False)

    ensure_items_match_stage_fields(stage, [link_item(answered)])
