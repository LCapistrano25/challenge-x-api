from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.factories import StudentFactory
from apps.core.factories import CourseFactory
from apps.editions.factories import CategoryFactory, ChallengeFactory, EditionFactory
from apps.projects.factories import (
    DeadlineExtensionFactory,
    SubmissionFactory,
    SubmissionVersionFactory,
)
from apps.projects.selectors import (
    get_active_categories,
    get_eligible_challenges,
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
