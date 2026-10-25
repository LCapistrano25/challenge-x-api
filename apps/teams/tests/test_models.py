import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.models import Student, User
from apps.core.models import Course
from apps.editions.models import Edition
from apps.teams.enums import InvitationStatus, MemberRole, RequestStatus, TeamStatus
from apps.teams.models import (
    Invitation,
    JoinRequest,
    LeadershipRequest,
    Team,
    TeamMember,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def edition():
    return Edition.objects.create(year=2026, semester=2)


def student(n):
    user = User.objects.create_user(f"aluno{n}@teste.com", "x", role=UserRole.STUDENT)
    course = Course.objects.get(name="Direito")
    return Student.objects.create(
        user=user, registration_number=str(n), course=course, term=1
    )


def team(edition, name="Equipe A"):
    return Team.objects.create(edition=edition, name=name, code=name.replace(" ", ""))


def member(team, aluno, role=MemberRole.MEMBER, **fields):
    return TeamMember.objects.create(
        team=team, edition=team.edition, student=aluno, role=role, **fields
    )


def leave(vinculo):
    vinculo.active = False
    vinculo.left_at = timezone.now()
    vinculo.save()


# Critérios de pronto da issue BM4


def test_dois_lideres_ativos_na_mesma_equipe_sao_recusados(edition):
    equipe = team(edition)
    member(equipe, student(1), role=MemberRole.LEADER)
    with pytest.raises(IntegrityError):
        member(equipe, student(2), role=MemberRole.LEADER)


def test_mesmo_aluno_em_duas_equipes_da_mesma_edicao_e_recusado(edition):
    aluno = student(1)
    member(team(edition, "Equipe A"), aluno)
    with pytest.raises(IntegrityError):
        member(team(edition, "Equipe B"), aluno)


def test_dois_convites_pendentes_para_o_mesmo_aluno_sao_recusados(edition):
    equipe, aluno = team(edition), student(1)
    Invitation.objects.create(team=equipe, student=aluno)
    with pytest.raises(IntegrityError):
        Invitation.objects.create(team=equipe, student=aluno)


# Histórico preservado: as unicidades valem só para ativos ou pendentes


def test_equipe_pode_ter_varios_membros_e_um_lider(edition):
    equipe = team(edition)
    member(equipe, student(1), role=MemberRole.LEADER)
    member(equipe, student(2))
    member(equipe, student(3))
    assert equipe.members.count() == 3


def test_aluno_que_saiu_pode_entrar_em_outra_equipe_da_edicao(edition):
    aluno = student(1)
    leave(member(team(edition, "Equipe A"), aluno))
    assert member(team(edition, "Equipe B"), aluno).pk


def test_aluno_que_saiu_pode_voltar_para_a_mesma_equipe(edition):
    equipe, aluno = team(edition), student(1)
    leave(member(equipe, aluno))
    assert member(equipe, aluno).pk


def test_novo_lider_depois_que_o_anterior_saiu(edition):
    equipe = team(edition)
    leave(member(equipe, student(1), role=MemberRole.LEADER))
    assert member(equipe, student(2), role=MemberRole.LEADER).pk


def test_convite_recusado_permite_convidar_de_novo(edition):
    equipe, aluno = team(edition), student(1)
    Invitation.objects.create(
        team=equipe, student=aluno, status=InvitationStatus.DECLINED
    )
    assert Invitation.objects.create(team=equipe, student=aluno).pk


def test_uma_solicitacao_de_entrada_pendente_por_aluno(edition):
    equipe, aluno = team(edition), student(1)
    JoinRequest.objects.create(team=equipe, student=aluno)
    with pytest.raises(IntegrityError):
        JoinRequest.objects.create(team=equipe, student=aluno)


def test_solicitacao_de_entrada_recusada_permite_pedir_de_novo(edition):
    equipe, aluno = team(edition), student(1)
    JoinRequest.objects.create(
        team=equipe, student=aluno, status=RequestStatus.REJECTED
    )
    assert JoinRequest.objects.create(team=equipe, student=aluno).pk


def test_uma_solicitacao_de_lideranca_pendente_por_equipe(edition):
    equipe = team(edition)
    LeadershipRequest.objects.create(
        team=equipe, requester=student(1), justification="Líder saiu."
    )
    with pytest.raises(IntegrityError):
        LeadershipRequest.objects.create(
            team=equipe, requester=student(2), justification="Líder saiu."
        )


def test_solicitacao_de_lideranca_decidida_permite_nova(edition):
    equipe = team(edition)
    LeadershipRequest.objects.create(
        team=equipe,
        requester=student(1),
        justification="Líder saiu.",
        status=RequestStatus.REJECTED,
    )
    assert LeadershipRequest.objects.create(
        team=equipe, requester=student(2), justification="Líder saiu."
    ).pk


# Demais regras de integridade


def test_nome_da_equipe_unico_na_edicao(edition):
    team(edition, "Equipe A")
    with pytest.raises(IntegrityError):
        Team.objects.create(edition=edition, name="Equipe A", code="OUTRO")


def test_codigo_da_equipe_unico(edition):
    Team.objects.create(edition=edition, name="Equipe A", code="ABC")
    with pytest.raises(IntegrityError):
        Team.objects.create(edition=edition, name="Equipe B", code="ABC")


def test_desclassificacao_exige_motivo(edition):
    with pytest.raises(IntegrityError):
        Team.objects.create(
            edition=edition, name="Equipe", code="X", status=TeamStatus.DISQUALIFIED
        )


def test_saida_e_vinculo_inativo_andam_juntos(edition):
    with pytest.raises(IntegrityError):
        member(team(edition), student(1), active=False)


def test_convite_exige_aluno_cadastrado(edition):
    with pytest.raises(IntegrityError):
        Invitation.objects.create(team=team(edition))


def test_integrante_tem_a_edicao_da_equipe(edition):
    outra = Edition.objects.create(year=2027, semester=1)
    vinculo = TeamMember(team=team(edition), edition=outra, student=student(1))
    with pytest.raises(ValidationError, match="não é a da equipe"):
        vinculo.full_clean()
