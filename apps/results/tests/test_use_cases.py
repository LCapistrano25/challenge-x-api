from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.exceptions import NotAdminActor
from apps.accounts.factories import StudentFactory
from apps.editions.enums import EditionStatus
from apps.editions.exceptions import EditionClosed
from apps.results.exceptions import ResultsAlreadyApproved, ResultsNotCalculated
from apps.results.factories import ProjectResultFactory
from apps.results.models import StudentScore
from apps.results.use_cases.compute_student_points import compute_student_points
from apps.teams.enums import MemberRole
from apps.teams.factories import TeamMemberFactory

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
