import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.accounts.factories import StudentFactory
from apps.editions.factories import EditionFactory
from apps.teams.enums import InvitationStatus, MemberRole, RequestStatus
from apps.teams.factories import (
    InvitationFactory,
    JoinRequestFactory,
    LeadershipRequestFactory,
    TeamFactory,
    TeamMemberFactory,
)
from apps.teams.models import Team, TeamMember

pytestmark = pytest.mark.django_db


def leave(vinculo):
    vinculo.active = False
    vinculo.left_at = timezone.now()
    vinculo.save()


# Critérios de pronto da issue BM4


def test_dois_lideres_ativos_na_mesma_equipe_sao_recusados():
    equipe = TeamFactory()  # já nasce com líder
    with pytest.raises(IntegrityError):
        TeamMemberFactory(team=equipe, role=MemberRole.LEADER)


def test_mesmo_aluno_em_duas_equipes_da_mesma_edicao_e_recusado():
    edicao, aluno = EditionFactory(), StudentFactory()
    TeamMemberFactory(team=TeamFactory(edition=edicao), student=aluno)
    with pytest.raises(IntegrityError):
        TeamMemberFactory(team=TeamFactory(edition=edicao), student=aluno)


def test_dois_convites_pendentes_para_o_mesmo_aluno_sao_recusados():
    convite = InvitationFactory()
    with pytest.raises(IntegrityError):
        InvitationFactory(team=convite.team, student=convite.student)


# Histórico preservado: as unicidades valem só para ativos ou pendentes


def test_equipe_pode_ter_varios_membros_e_um_lider():
    equipe = TeamFactory()
    TeamMemberFactory.create_batch(2, team=equipe)
    assert equipe.members.count() == 3


def test_aluno_que_saiu_pode_entrar_em_outra_equipe_da_edicao():
    vinculo = TeamMemberFactory()
    leave(vinculo)
    outra = TeamFactory(edition=vinculo.edition)
    assert TeamMemberFactory(team=outra, student=vinculo.student).pk


def test_aluno_que_saiu_pode_voltar_para_a_mesma_equipe():
    vinculo = TeamMemberFactory()
    leave(vinculo)
    assert TeamMemberFactory(team=vinculo.team, student=vinculo.student).pk


def test_novo_lider_depois_que_o_anterior_saiu():
    equipe = TeamFactory()
    leave(equipe.members.get(role=MemberRole.LEADER))
    assert TeamMemberFactory(team=equipe, role=MemberRole.LEADER).pk


def test_convite_recusado_permite_convidar_de_novo():
    recusado = InvitationFactory(status=InvitationStatus.DECLINED)
    assert InvitationFactory(team=recusado.team, student=recusado.student).pk


def test_uma_solicitacao_de_entrada_pendente_por_aluno():
    pedido = JoinRequestFactory()
    with pytest.raises(IntegrityError):
        JoinRequestFactory(team=pedido.team, student=pedido.student)


def test_solicitacao_de_entrada_recusada_permite_pedir_de_novo():
    recusado = JoinRequestFactory(status=RequestStatus.REJECTED)
    assert JoinRequestFactory(team=recusado.team, student=recusado.student).pk


def test_uma_solicitacao_de_lideranca_pendente_por_equipe():
    pedido = LeadershipRequestFactory()
    with pytest.raises(IntegrityError):
        LeadershipRequestFactory(team=pedido.team)


def test_solicitacao_de_lideranca_decidida_permite_nova():
    decidido = LeadershipRequestFactory(status=RequestStatus.REJECTED)
    assert LeadershipRequestFactory(team=decidido.team).pk


# Demais regras de integridade


def test_nome_da_equipe_unico_na_edicao():
    equipe = TeamFactory(leader=False)
    with pytest.raises(IntegrityError):
        TeamFactory(edition=equipe.edition, name=equipe.name, leader=False)


def test_codigo_da_equipe_unico():
    equipe = TeamFactory(leader=False)
    with pytest.raises(IntegrityError):
        TeamFactory(code=equipe.code, leader=False)


def test_desclassificacao_exige_motivo():
    with pytest.raises(IntegrityError):
        TeamFactory(disqualified=True, disqualification_reason="", leader=False)


def test_saida_e_vinculo_inativo_andam_juntos():
    with pytest.raises(IntegrityError):
        TeamMemberFactory(active=False)


def test_convite_exige_aluno_cadastrado():
    with pytest.raises(IntegrityError):
        InvitationFactory(student=None)


def test_integrante_tem_a_edicao_da_equipe():
    vinculo = TeamMember(
        team=TeamFactory(leader=False),
        edition=EditionFactory(),
        student=StudentFactory(),
    )
    with pytest.raises(ValidationError, match="não é a da equipe"):
        vinculo.full_clean()


# Factories: o que outros apps vão usar precisa nascer válido


def test_equipe_da_factory_nasce_com_um_lider_ativo():
    equipe = TeamFactory()
    assert equipe.members.filter(role=MemberRole.LEADER, active=True).count() == 1
    assert isinstance(equipe, Team)


def test_traits_da_equipe():
    assert TeamFactory(incomplete=True).situation == "INCOMPLETE"
    assert TeamFactory(disqualified=True).disqualification_reason


@pytest.mark.parametrize(
    "factory",
    [
        TeamFactory,
        TeamMemberFactory,
        InvitationFactory,
        JoinRequestFactory,
        LeadershipRequestFactory,
    ],
)
def test_factory_gera_registro_valido(factory):
    factory().full_clean()
