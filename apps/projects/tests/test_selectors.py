from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.factories import StudentFactory
from apps.core.factories import CourseFactory
from apps.editions.factories import (
    CategoryFactory,
    ChallengeFactory,
    EditionFactory,
    StageFactory,
    StageSubmissionFieldFactory,
)
from apps.projects.enums import DeliveryStatus, PhaseStatus
from apps.projects.factories import (
    DeadlineExtensionFactory,
    ProjectFactory,
    SubmissionFactory,
    SubmissionReceiptFactory,
    SubmissionVersionFactory,
)
from apps.projects.selectors import (
    get_active_categories,
    get_delivery_status,
    get_eligible_challenges,
    get_official_version,
    get_phase_status,
    get_project_deliverables,
    get_receipt_by_version,
    get_team_courses,
    get_valid_version,
)
from apps.teams.enums import MemberRole
from apps.teams.factories import TeamFactory, TeamMemberFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def submission():
    return SubmissionFactory()


def at(submission, delta):
    return submission.stage.ends_at + delta


# Critérios de pronto da issue BM5


def test_envio_no_prazo_vale(submission):
    version = SubmissionVersionFactory(
        submission=submission,
        number=1,
        submitted_at=at(submission, -timedelta(hours=1)),
    )
    assert get_valid_version(submission) == version


def test_envio_fora_do_prazo_nao_vale(submission):
    SubmissionVersionFactory(
        submission=submission,
        number=1,
        submitted_at=at(submission, timedelta(minutes=1)),
    )
    assert get_valid_version(submission) is None


def test_sem_nenhuma_versao(submission):
    assert get_valid_version(submission) is None


# Casos de borda


def test_vale_a_de_maior_numero_dentro_do_prazo(submission):
    SubmissionVersionFactory(
        submission=submission, number=1, submitted_at=at(submission, -timedelta(days=2))
    )
    ultima_no_prazo = SubmissionVersionFactory(
        submission=submission, number=2, submitted_at=at(submission, -timedelta(days=1))
    )
    SubmissionVersionFactory(
        submission=submission, number=3, submitted_at=at(submission, timedelta(hours=1))
    )
    assert get_valid_version(submission) == ultima_no_prazo


def test_envio_exatamente_no_fim_do_prazo_vale(submission):
    version = SubmissionVersionFactory(
        submission=submission, number=1, submitted_at=submission.stage.ends_at
    )
    assert get_valid_version(submission) == version


# Prorrogação por equipe (RF14, P-21)


def test_prorrogacao_faz_valer_envio_depois_do_prazo_da_etapa(submission):
    extensao = DeadlineExtensionFactory(
        project=submission.project, stage=submission.stage
    )
    version = SubmissionVersionFactory(
        submission=submission,
        number=1,
        submitted_at=at(submission, timedelta(days=1)),
    )
    assert extensao.ends_at > version.submitted_at
    assert get_valid_version(submission) == version


def test_prorrogacao_de_outra_equipe_nao_vale(submission):
    DeadlineExtensionFactory(stage=submission.stage)
    SubmissionVersionFactory(
        submission=submission,
        number=1,
        submitted_at=at(submission, timedelta(days=1)),
    )
    assert get_valid_version(submission) is None


# Opções de desafio e categoria da equipe (RF29, RF50)


@pytest.fixture
def team():
    return TeamFactory()


def leader_course(team):
    return team.members.get(role=MemberRole.LEADER).student.course


def test_cursos_da_equipe_sao_os_dos_integrantes_ativos(team):
    outro = CourseFactory()
    TeamMemberFactory(team=team, student=StudentFactory(course=outro))
    TeamMemberFactory(team=team, student=StudentFactory(course=outro))
    inativo = TeamMemberFactory(team=team, student=StudentFactory())
    inativo.active = False
    inativo.left_at = timezone.now()
    inativo.save()

    assert set(get_team_courses(team)) == {leader_course(team), outro}


def test_desafio_de_curso_de_integrante_ativo_e_elegivel(team):
    desafio = ChallengeFactory(edition=team.edition, course=leader_course(team))
    assert list(get_eligible_challenges(team)) == [desafio]


def test_desafio_de_curso_sem_integrante_nao_e_elegivel(team):
    ChallengeFactory(edition=team.edition)
    assert not get_eligible_challenges(team).exists()


def test_desafio_inativo_nao_e_elegivel(team):
    ChallengeFactory(edition=team.edition, course=leader_course(team), active=False)
    assert not get_eligible_challenges(team).exists()


def test_desafio_de_outra_edicao_nao_e_elegivel(team):
    ChallengeFactory(edition=EditionFactory(), course=leader_course(team))
    assert not get_eligible_challenges(team).exists()


def test_curso_de_ex_integrante_nao_conta(team):
    curso = CourseFactory()
    ex = TeamMemberFactory(team=team, student=StudentFactory(course=curso))
    ex.active = False
    ex.left_at = timezone.now()
    ex.save()
    ChallengeFactory(edition=team.edition, course=curso)

    assert not get_eligible_challenges(team).exists()


def test_desafio_aparece_uma_vez_com_varios_integrantes_do_curso(team):
    curso = leader_course(team)
    TeamMemberFactory(team=team, student=StudentFactory(course=curso))
    desafio = ChallengeFactory(edition=team.edition, course=curso)

    assert list(get_eligible_challenges(team)) == [desafio]


def test_categorias_so_ativas_da_edicao(team):
    ativa = CategoryFactory(edition=team.edition)
    CategoryFactory(edition=team.edition, active=False)
    CategoryFactory(edition=EditionFactory())

    assert list(get_active_categories(team.edition)) == [ativa]


# Status da entrega e consulta por etapa (RF31, P-27)


def stage_between(project, start, end, **fields):
    now = timezone.now()
    return StageFactory(
        edition=project.edition,
        starts_at=now + start,
        ends_at=now + end,
        **fields,
    )


def test_status_nao_enviada_com_prazo_aberto():
    project = ProjectFactory()
    stage = stage_between(project, -timedelta(days=1), timedelta(days=1))
    assert get_delivery_status(project, stage) == DeliveryStatus.NOT_SUBMITTED


def test_status_enviada_com_versao_no_prazo():
    submission = SubmissionFactory()
    SubmissionVersionFactory(
        submission=submission,
        number=1,
        submitted_at=at(submission, -timedelta(hours=1)),
    )
    status = get_delivery_status(submission.project, submission.stage)
    assert status == DeliveryStatus.SUBMITTED


def test_status_nao_entregue_com_prazo_encerrado_sem_versao():
    project = ProjectFactory()
    stage = stage_between(project, -timedelta(days=5), -timedelta(days=1))
    assert get_delivery_status(project, stage) == DeliveryStatus.NOT_DELIVERED


def test_prorrogacao_muda_nao_entregue_para_nao_enviada():
    project = ProjectFactory()
    stage = stage_between(project, -timedelta(days=5), -timedelta(days=1))
    DeadlineExtensionFactory(
        project=project, stage=stage, ends_at=timezone.now() + timedelta(days=1)
    )
    assert get_delivery_status(project, stage) == DeliveryStatus.NOT_SUBMITTED


def test_versao_oficial_nula_com_prazo_aberto():
    submission = SubmissionFactory()
    SubmissionVersionFactory(
        submission=submission,
        number=1,
        submitted_at=at(submission, -timedelta(hours=1)),
    )
    assert get_official_version(submission.project, submission.stage) is None


def test_versao_oficial_depois_do_prazo_e_a_de_maior_numero_no_prazo():
    project = ProjectFactory()
    stage = stage_between(project, -timedelta(days=5), -timedelta(days=1))
    submission = SubmissionFactory(project=project, stage=stage)
    SubmissionVersionFactory(
        submission=submission, number=1, submitted_at=at(submission, -timedelta(days=3))
    )
    last = SubmissionVersionFactory(
        submission=submission, number=2, submitted_at=at(submission, -timedelta(days=2))
    )
    assert get_official_version(project, stage) == last


def test_versao_oficial_nula_sem_envio():
    project = ProjectFactory()
    stage = stage_between(project, -timedelta(days=5), -timedelta(days=1))
    assert get_official_version(project, stage) is None


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (timedelta(days=1), timedelta(days=2), PhaseStatus.UPCOMING),
        (-timedelta(days=1), timedelta(days=1), PhaseStatus.OPEN),
        (-timedelta(days=2), -timedelta(days=1), PhaseStatus.FINISHED),
    ],
)
def test_fase_da_etapa(start, end, expected):
    stage = stage_between(ProjectFactory(), start, end)
    assert get_phase_status(stage) == expected


def test_entregas_listam_so_etapas_de_entrega_com_campos_em_ordem():
    project = ProjectFactory()
    second = StageFactory(edition=project.edition, order=2)
    first = StageFactory(edition=project.edition, order=1)
    no_fields = StageFactory(edition=project.edition, order=3)
    formation = StageFactory(formation=True, edition=project.edition, order=4)
    for stage in (second, first, formation):
        StageSubmissionFieldFactory(stage=stage)
    assert no_fields.submission_fields.count() == 0

    assert list(get_project_deliverables(project)) == [first, second]


def test_comprovante_da_versao_vem_com_equipe_projeto_e_etapa(
    django_assert_num_queries,
):
    receipt = SubmissionReceiptFactory()

    found = get_receipt_by_version(receipt.version_id)

    with django_assert_num_queries(0):
        assert found == receipt
        assert found.version.submission.project.team.code
        assert found.version.submission.stage.name


def test_comprovante_nulo_para_versao_inexistente():
    assert get_receipt_by_version(999999) is None


def test_comprovante_nulo_para_versao_sem_comprovante():
    version = SubmissionVersionFactory()
    assert get_receipt_by_version(version.pk) is None
