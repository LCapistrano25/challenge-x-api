from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.exceptions import NotAdminActor
from apps.accounts.factories import StudentFactory
from apps.editions.enums import EditionStatus
from apps.editions.exceptions import EditionClosed
from apps.evaluations.factories import FinalEvaluationFactory
from apps.evaluations.models import StageScore
from apps.projects.enums import ProjectStatus
from apps.projects.models import Project
from apps.results.exceptions import (
    FinalistAlreadyEvaluated,
    NoFinalists,
    NoScoredStages,
    ResultsAlreadyApproved,
    ResultsNotCalculated,
    ResultsOutdated,
)
from apps.results.factories import ProjectResultFactory
from apps.results.models import ProjectResult, StudentScore
from apps.results.use_cases.approve_finalists import approve_finalists
from apps.results.use_cases.calculate_results import calculate_results
from apps.results.use_cases.compute_student_points import compute_student_points
from apps.results.use_cases.select_finalists import select_finalists
from apps.teams.enums import MemberRole, TeamStatus
from apps.teams.factories import TeamMemberFactory
from apps.teams.models import Team

pytestmark = pytest.mark.django_db


def close(edition):
    edition.status = EditionStatus.CLOSED
    edition.save()


def add_member(project, term, **kwargs):
    return TeamMemberFactory(
        team=project.team, student=StudentFactory(term=term), **kwargs
    )


def leader_of(project, term=1):
    member = project.team.members.get(role=MemberRole.LEADER)
    member.student.term = term
    member.student.save()
    return member


def points_of(project):
    return {
        s.student_id: (s.term, s.points)
        for s in StudentScore.objects.filter(project=project)
    }


# compute_student_points (RF19, RN49)


@pytest.fixture
def scored(make_project):
    """Projeto com nota final 7,50, líder no 1º período e um integrante no 4º."""
    project = make_project()
    leader = leader_of(project, term=1)
    member = add_member(project, term=4)
    result = ProjectResultFactory(project=project, final_score=Decimal("7.50"))
    return project, leader, member, result


def test_grava_um_registro_por_integrante_ativo(admin, scored):
    project, leader, member, _ = scored

    scores = compute_student_points(actor=admin, project=project)

    assert len(scores) == 2
    assert all(s.calculated_at for s in scores)
    assert points_of(project) == {
        leader.student_id: (1, Decimal("0.75")),
        member.student_id: (4, Decimal("1.50")),
    }


def test_integrante_inativo_nao_pontua(admin, scored):
    project, *_ = scored
    gone = add_member(project, term=2, active=False, left_at=timezone.now())

    compute_student_points(actor=admin, project=project)

    assert gone.student_id not in points_of(project)


def test_quem_saiu_perde_a_pontuacao_no_recalculo(admin, scored):
    project, leader, member, _ = scored
    compute_student_points(actor=admin, project=project)
    member.active = False
    member.left_at = timezone.now()
    member.save()

    compute_student_points(actor=admin, project=project)

    assert list(points_of(project)) == [leader.student_id]


def test_recalculo_mantem_o_periodo_e_atualiza_os_pontos(admin, scored):
    project, _, member, result = scored
    compute_student_points(actor=admin, project=project)
    member.student.term = 1
    member.student.save()
    result.final_score = Decimal("10.00")
    result.save()

    compute_student_points(actor=admin, project=project)

    assert points_of(project)[member.student_id] == (4, Decimal("2.00"))


def test_resultado_sem_nota_apaga_os_pontos(admin, scored):
    project, *_, result = scored
    compute_student_points(actor=admin, project=project)
    result.final_score = None
    result.save()

    assert compute_student_points(actor=admin, project=project) == []
    assert points_of(project) == {}


def test_pontos_exigem_resultado(admin, make_project):
    with pytest.raises(ResultsNotCalculated):
        compute_student_points(actor=admin, project=make_project())


def test_pontos_exigem_admin(scored):
    project, leader, *_ = scored

    with pytest.raises(NotAdminActor):
        compute_student_points(actor=leader.student.user, project=project)
    assert points_of(project) == {}


def test_pontos_barram_edicao_encerrada(admin, edition, scored):
    project = scored[0]
    close(edition)
    project.refresh_from_db()

    with pytest.raises(EditionClosed):
        compute_student_points(actor=admin, project=project)
    assert points_of(project) == {}


def test_pontos_barram_resultado_homologado(admin, scored):
    project, *_, result = scored
    result.approved_at = timezone.now()
    result.save()

    with pytest.raises(ResultsAlreadyApproved):
        compute_student_points(actor=admin, project=project)
    assert points_of(project) == {}


# calculate_results (RF15)


def result_of(project):
    return ProjectResult.objects.get(project=project)


def test_calculo_grava_nota_posicao_e_pontos(admin, edition, make_project):
    first = make_project("3.00", "3.00")
    second = make_project("1.00", "1.50")
    leader = leader_of(first, term=3)

    calculate_results(actor=admin, edition=edition)

    assert result_of(first).final_score == Decimal("6.00")
    assert result_of(first).course_rank == 1
    assert result_of(second).final_score == Decimal("2.50")
    assert result_of(second).course_rank == 2
    assert points_of(first) == {leader.student_id: (3, Decimal("1.20"))}


def test_pendente_e_desclassificada_nao_ganham_resultado(admin, edition, make_project):
    pending = make_project("3.00")
    disqualified = make_project("3.00", "3.00", status=ProjectStatus.DISQUALIFIED)

    calculate_results(actor=admin, edition=edition)

    ids = [pending.pk, disqualified.pk]
    assert not ProjectResult.objects.filter(project_id__in=ids).exists()
    assert not StudentScore.objects.filter(project_id__in=ids).exists()


def test_recalculo_preserva_finalista_classificado(admin, edition, make_project):
    project = make_project("3.00", "3.00")
    calculate_results(actor=admin, edition=edition)
    ProjectResult.objects.filter(project=project).update(finalist=True)

    calculate_results(actor=admin, edition=edition)

    assert result_of(project).finalist


@pytest.mark.parametrize("status", [TeamStatus.DISQUALIFIED, TeamStatus.DISBANDED])
def test_quem_sai_do_ranking_perde_nota_posicao_marca_e_pontos(
    admin, edition, make_project, status
):
    project = make_project("3.00", "3.00")
    calculate_results(actor=admin, edition=edition)
    ProjectResult.objects.filter(project=project).update(finalist=True)
    changes = {"status": status}
    if status == TeamStatus.DISQUALIFIED:
        changes |= {
            "disqualification_reason": "Plágio.",
            "disqualified_at": timezone.now(),
            "disqualified_by": admin,
        }
    Team.objects.filter(pk=project.team_id).update(**changes)

    calculate_results(actor=admin, edition=edition)

    result = result_of(project)
    assert (result.final_score, result.course_rank, result.finalist) == (
        None,
        None,
        False,
    )
    assert points_of(project) == {}


def test_calculo_exige_etapa_pontuada(admin, edition):
    with pytest.raises(NoScoredStages):
        calculate_results(actor=admin, edition=edition)


def test_calculo_exige_admin(edition, make_project):
    project = make_project("3.00", "3.00")

    with pytest.raises(NotAdminActor):
        calculate_results(actor=leader_of(project).student.user, edition=edition)
    assert not ProjectResult.objects.exists()


def test_calculo_barra_edicao_encerrada(admin, edition, make_project):
    make_project("3.00", "3.00")
    close(edition)

    with pytest.raises(EditionClosed):
        calculate_results(actor=admin, edition=edition)
    assert not ProjectResult.objects.exists()


def test_calculo_barra_resultado_homologado(admin, edition, make_project):
    project = make_project("3.00", "3.00")
    calculate_results(actor=admin, edition=edition)
    ProjectResult.objects.update(approved_at=timezone.now())
    StageScore.objects.filter(project=project).update(value=Decimal("1.00"))

    with pytest.raises(ResultsAlreadyApproved):
        calculate_results(actor=admin, edition=edition)
    assert result_of(project).final_score == Decimal("6.00")


def test_calculo_e_atomico(admin, edition, make_project):
    project = make_project("3.00", "3.00")
    add_member(project, term=11)  # fora do CHECK de StudentScore (1 a 10)

    with pytest.raises(ValidationError):
        calculate_results(actor=admin, edition=edition)
    assert not ProjectResult.objects.exists()
    assert not StudentScore.objects.exists()


# select_finalists e approve_finalists (RF15, UC15)


@pytest.fixture
def calculated(admin, edition, make_project):
    """Dois classificados (o primeiro com a maior nota) e um pendente."""
    first = make_project("3.00", "3.00")
    second = make_project("1.00", "1.00")
    pending = make_project("3.00")
    calculate_results(actor=admin, edition=edition)
    return first, second, pending


def finalists(edition):
    return set(
        ProjectResult.objects.filter(
            project__edition=edition, finalist=True
        ).values_list("project_id", flat=True)
    )


def test_finalistas_marca_exatamente_a_lista(admin, edition, calculated):
    _, second, _ = calculated

    select_finalists(actor=admin, edition=edition, project_ids=[second.pk])

    assert finalists(edition) == {second.pk}


def test_nova_lista_substitui_a_anterior(admin, edition, calculated):
    first, second, _ = calculated
    select_finalists(actor=admin, edition=edition, project_ids=[first.pk])

    select_finalists(actor=admin, edition=edition, project_ids=[second.pk])

    assert finalists(edition) == {second.pk}


@pytest.mark.parametrize("case", ["pendente", "outra_edicao"])
def test_finalista_fora_do_ranking_e_barrado_sem_mudar_nada(
    admin, edition, calculated, case
):
    first, second, pending = calculated
    select_finalists(actor=admin, edition=edition, project_ids=[first.pk])
    other = pending.pk if case == "pendente" else ProjectResultFactory().project_id

    with pytest.raises(ValidationError):
        select_finalists(actor=admin, edition=edition, project_ids=[second.pk, other])

    assert finalists(edition) == {first.pk}


def test_retirar_finalista_avaliado_e_barrado(admin, edition, calculated):
    first, second, _ = calculated
    select_finalists(actor=admin, edition=edition, project_ids=[first.pk])
    FinalEvaluationFactory(project=first)

    with pytest.raises(FinalistAlreadyEvaluated):
        select_finalists(actor=admin, edition=edition, project_ids=[second.pk])

    select_finalists(actor=admin, edition=edition, project_ids=[first.pk, second.pk])
    assert finalists(edition) == {first.pk, second.pk}


def test_finalistas_exigem_calculo(admin, edition, make_project):
    project = make_project("3.00", "3.00")

    with pytest.raises(ResultsNotCalculated):
        select_finalists(actor=admin, edition=edition, project_ids=[project.pk])


def test_homologacao_grava_o_mesmo_instante_em_todos_os_classificados(
    admin, edition, calculated
):
    first, second, _ = calculated
    select_finalists(actor=admin, edition=edition, project_ids=[first.pk])

    approve_finalists(actor=admin, edition=edition)

    instants = {result_of(p).approved_at for p in (first, second)}
    assert len(instants) == 1
    assert None not in instants


def test_homologacao_exige_finalista(admin, edition, calculated):
    with pytest.raises(NoFinalists):
        approve_finalists(actor=admin, edition=edition)


def test_homologacao_exige_calculo(admin, edition):
    with pytest.raises(ResultsNotCalculated):
        approve_finalists(actor=admin, edition=edition)


@pytest.mark.parametrize("change", ["nota", "desclassificacao"])
def test_homologacao_barra_resultado_defasado(admin, edition, calculated, change):
    first, second, _ = calculated
    select_finalists(actor=admin, edition=edition, project_ids=[first.pk])
    if change == "nota":
        StageScore.objects.filter(project=second).update(value=Decimal("2.00"))
    else:
        Project.objects.filter(pk=second.pk).update(status=ProjectStatus.DISQUALIFIED)

    with pytest.raises(ResultsOutdated):
        approve_finalists(actor=admin, edition=edition)

    assert not ProjectResult.objects.filter(approved_at__isnull=False).exists()


def run_select(actor, edition, project):
    select_finalists(actor=actor, edition=edition, project_ids=[project.pk])


def run_approve(actor, edition, project):
    approve_finalists(actor=actor, edition=edition)


@pytest.mark.parametrize("run", [run_select, run_approve])
@pytest.mark.parametrize(
    "case, error",
    [
        ("nao_admin", NotAdminActor),
        ("encerrada", EditionClosed),
        ("homologado", ResultsAlreadyApproved),
    ],
)
def test_finalistas_e_homologacao_barram(admin, edition, calculated, run, case, error):
    first, second, _ = calculated
    select_finalists(actor=admin, edition=edition, project_ids=[first.pk])
    actor = admin
    if case == "nao_admin":
        actor = leader_of(first).student.user
    elif case == "encerrada":
        close(edition)
    else:
        approve_finalists(actor=admin, edition=edition)
    before = list(ProjectResult.objects.values_list("finalist", "approved_at"))

    with pytest.raises(error):
        run(actor, edition, second)

    assert list(ProjectResult.objects.values_list("finalist", "approved_at")) == before


def test_nada_muda_depois_de_homologar(admin, edition, calculated):
    first, *_ = calculated
    select_finalists(actor=admin, edition=edition, project_ids=[first.pk])
    approve_finalists(actor=admin, edition=edition)

    with pytest.raises(ResultsAlreadyApproved):
        calculate_results(actor=admin, edition=edition)
