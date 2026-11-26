from decimal import Decimal

import pytest

from apps.editions.factories import (
    CriterionFactory,
    StageCriterionFactory,
    StageFactory,
)
from apps.evaluations.enums import ScoreStatus
from apps.evaluations.factories import (
    EvaluationFactory,
    EvaluationItemFactory,
    StageScoreFactory,
)
from apps.projects.enums import ProjectStatus
from apps.projects.factories import ProjectFactory
from apps.results.enums import ResultExclusionReason
from apps.results.selectors import list_edition_standings
from apps.teams.enums import TeamStatus
from apps.teams.factories import TeamFactory

pytestmark = pytest.mark.django_db


def by_id(edition):
    return {s.project.pk: s for s in list_edition_standings(edition)}


def assert_excluded(standing, reason):
    assert standing.exclusion == reason
    assert standing.final_score is None
    assert standing.course_rank is None


def test_nota_final_soma_as_etapas_pontuadas(edition, make_project):
    project = make_project("2.50", "3.00")

    standing = by_id(edition)[project.pk]

    assert standing.final_score == Decimal("5.50")
    assert standing.course_rank == 1
    assert standing.exclusion is None


def test_zero_sem_entrega_conta_como_nota(edition, stages, make_project):
    project = make_project("2.50")
    StageScoreFactory(
        project=project,
        stage=stages[1],
        status=ScoreStatus.ZERO_NO_SUBMISSION,
        value=0,
    )

    assert by_id(edition)[project.pk].final_score == Decimal("2.50")


@pytest.mark.parametrize("pending_row", [False, True])
def test_nota_pendente_ou_ausente_fica_fora(edition, stages, make_project, pending_row):
    project = make_project("2.50")
    if pending_row:
        StageScoreFactory(project=project, stage=stages[1])

    assert_excluded(by_id(edition)[project.pk], ResultExclusionReason.PENDING_SCORE)


def test_etapa_nao_pontuada_e_ignorada(edition, make_project):
    project = make_project("1.00", "1.00")
    StageFactory(edition=edition, formation=True)

    assert by_id(edition)[project.pk].exclusion is None


def test_edicao_sem_etapa_pontuada_deixa_todos_pendentes(edition):
    project = ProjectFactory(team=TeamFactory(edition=edition))

    assert_excluded(by_id(edition)[project.pk], ResultExclusionReason.PENDING_SCORE)


def test_desclassificada_pela_equipe_ou_pelo_projeto(edition, make_project):
    by_team = make_project(
        "1.00", "1.00", team=TeamFactory(edition=edition, disqualified=True)
    )
    by_project = make_project("1.00", "1.00", status=ProjectStatus.DISQUALIFIED)

    standings = by_id(edition)

    for project in (by_team, by_project):
        assert_excluded(standings[project.pk], ResultExclusionReason.DISQUALIFIED)


def test_projeto_sem_desafio(edition, make_project):
    project = make_project("1.00", "1.00")
    project.challenge = None
    project.save()

    assert_excluded(by_id(edition)[project.pk], ResultExclusionReason.NO_CHALLENGE)


def test_equipe_desfeita_nao_aparece(edition, make_project):
    team = TeamFactory(edition=edition, status=TeamStatus.DISBANDED)
    project = make_project("1.00", "1.00", team=team)

    assert project.pk not in by_id(edition)


def test_projeto_de_outra_edicao_nao_aparece(edition):
    other = ProjectFactory()

    assert other.pk not in by_id(edition)


def test_desempate_usa_a_media_dos_avaliadores_somada_entre_etapas(
    edition, stages, criteria, make_project
):
    a = make_project("2.00", "2.00")
    b = make_project("2.00", "2.00")
    link = criteria[stages[0].pk][0]

    def rate(project, points, **kwargs):
        evaluation = EvaluationFactory(project=project, stage=stages[0], **kwargs)
        EvaluationItemFactory(
            evaluation=evaluation, stage_criterion=link, points=Decimal(points)
        )

    rate(a, "0.40", finalized=True)
    rate(a, "0.60", finalized=True)
    rate(a, "1.00")  # rascunho não conta
    rate(b, "0.60", finalized=True)

    standings = by_id(edition)

    assert standings[b.pk].course_rank == 1
    assert standings[a.pk].course_rank == 2


def test_desempate_normaliza_o_criterio_pelo_valor_na_etapa(
    edition, stages, make_project
):
    # O mesmo critério vale 2 na primeira etapa e 1 na segunda: 1,6 de 2 (8 em 10)
    # perde para 1,0 de 1 (10 em 10), embora tenha mais pontos brutos.
    criterion = CriterionFactory(edition=edition, tiebreak_order=1)
    worth_two = StageCriterionFactory(
        stage=stages[0], criterion=criterion, max_score=Decimal("2.00")
    )
    worth_one = StageCriterionFactory(
        stage=stages[1], criterion=criterion, max_score=Decimal("1.00")
    )
    a = make_project("2.00", "2.00")
    b = make_project("2.00", "2.00")
    for project, link, points in ((a, worth_two, "1.60"), (b, worth_one, "1.00")):
        evaluation = EvaluationFactory(
            project=project, stage=link.stage, finalized=True
        )
        EvaluationItemFactory(
            evaluation=evaluation, stage_criterion=link, points=Decimal(points)
        )

    standings = by_id(edition)

    assert standings[b.pk].course_rank == 1
    assert standings[a.pk].course_rank == 2
