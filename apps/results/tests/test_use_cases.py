from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.exceptions import NotAdminActor
from apps.accounts.factories import StudentFactory
from apps.editions.enums import EditionStatus
from apps.editions.exceptions import EditionClosed
from apps.evaluations.models import StageScore
from apps.projects.enums import ProjectStatus
from apps.results.exceptions import (
    NoScoredStages,
    ResultsAlreadyApproved,
    ResultsNotCalculated,
)
from apps.results.factories import ProjectResultFactory
from apps.results.models import ProjectResult, StudentScore
from apps.results.use_cases.calculate_results import calculate_results
from apps.results.use_cases.compute_student_points import compute_student_points
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
