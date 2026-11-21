from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.accounts.factories import StudentFactory
from apps.editions.factories import StageFactory
from apps.teams.enums import MemberRole
from apps.teams.factories import InvitationFactory, TeamFactory, TeamMemberFactory
from apps.teams.rules import (
    FORMATION_EXTENSION,
    is_formation_open_for_team,
)
from apps.teams.use_cases.invite_member import InvitationRejected, invite_member
from apps.teams.use_cases.leave_team import LeaveTeamRejected, leave_team
from apps.teams.use_cases.request_to_join import request_to_join
from apps.teams.use_cases.respond_invitation import respond_invitation

pytestmark = pytest.mark.django_db


def formacao(team, termina_em):
    now = timezone.now()
    return StageFactory(
        edition=team.edition,
        formation=True,
        starts_at=now - timedelta(days=10),
        ends_at=now + termina_em,
    )


def equipe_de_3_com_prazo(termina_em):
    """Líder e 2 integrantes (min_members=3 por padrão), prazo terminando em breve."""
    team = TeamFactory()
    stage = formacao(team, termina_em)
    for _ in range(2):
        TeamMemberFactory(team=team, role=MemberRole.MEMBER)
    return team, stage


def equipe_com_prazo_encerrado_e_janela_extra():
    team = TeamFactory()
    formacao(team, timedelta(hours=-2))
    team.formation_extended_until = timezone.now() + timedelta(hours=10)
    team.save()
    return team


# Concessão da janela extra


def test_saida_nas_ultimas_24h_que_derruba_a_equipe_da_48h_para_repor_a_vaga():
    team, stage = equipe_de_3_com_prazo(timedelta(hours=6))
    saindo = team.members.filter(role=MemberRole.MEMBER).first()

    leave_team(actor=saindo.student.user, team_id=team.id, confirm=True)

    team.refresh_from_db()
    assert team.formation_extended_until == stage.ends_at + FORMATION_EXTENSION


def test_saida_com_mais_de_24h_de_prazo_nao_da_janela_extra():
    team, _ = equipe_de_3_com_prazo(timedelta(hours=30))
    saindo = team.members.filter(role=MemberRole.MEMBER).first()

    leave_team(actor=saindo.student.user, team_id=team.id, confirm=True)

    team.refresh_from_db()
    assert team.formation_extended_until is None


def test_saida_que_mantem_o_minimo_nao_da_janela_extra():
    team, _ = equipe_de_3_com_prazo(timedelta(hours=6))
    extra = TeamMemberFactory(team=team, role=MemberRole.MEMBER)  # sobram 3 de 3

    leave_team(actor=extra.student.user, team_id=team.id)

    team.refresh_from_db()
    assert team.formation_extended_until is None


def test_a_janela_extra_e_concedida_uma_so_vez():
    team, _ = equipe_de_3_com_prazo(timedelta(hours=6))
    ja_concedida = timezone.now() + timedelta(hours=40)
    team.formation_extended_until = ja_concedida
    team.save()
    saindo = team.members.filter(role=MemberRole.MEMBER).first()

    leave_team(actor=saindo.student.user, team_id=team.id, confirm=True)

    team.refresh_from_db()
    assert team.formation_extended_until == ja_concedida


def test_aviso_aos_demais_informa_ate_quando_a_equipe_pode_repor_a_vaga():
    team, _ = equipe_de_3_com_prazo(timedelta(hours=6))
    saindo = team.members.filter(role=MemberRole.MEMBER).first()

    with patch("apps.teams.use_cases.leave_team.create_notification") as notify:
        leave_team(actor=saindo.student.user, team_id=team.id, confirm=True)

    assert "para repor a vaga." in notify.call_args.kwargs["message"]


# O que a equipe pode fazer durante a janela extra


def test_regra_considera_a_janela_extra_da_equipe():
    team = TeamFactory()
    formacao(team, timedelta(hours=-2))
    assert is_formation_open_for_team(team) is False

    team.formation_extended_until = timezone.now() + timedelta(hours=1)
    assert is_formation_open_for_team(team) is True

    team.formation_extended_until = timezone.now() - timedelta(minutes=1)
    assert is_formation_open_for_team(team) is False


def test_lider_convida_durante_a_janela_extra():
    team = equipe_com_prazo_encerrado_e_janela_extra()
    lider = team.members.get(role=MemberRole.LEADER)
    novo = StudentFactory()

    invitation = invite_member(
        actor=lider.student.user, team_id=team.id, student_id=novo.pk
    )

    assert invitation.student == novo


def test_aluno_pede_para_entrar_durante_a_janela_extra():
    team = equipe_com_prazo_encerrado_e_janela_extra()

    pedido = request_to_join(actor=StudentFactory().user, team_id=team.id)

    assert pedido.team == team


def test_convidado_aceita_durante_a_janela_extra():
    team = equipe_com_prazo_encerrado_e_janela_extra()
    convite = InvitationFactory(team=team)

    respond_invitation(
        actor=convite.student.user, invitation_id=convite.pk, accept=True
    )

    assert team.members.filter(student=convite.student, active=True).exists()


def test_depois_da_janela_extra_ninguem_convida():
    team = equipe_com_prazo_encerrado_e_janela_extra()
    team.formation_extended_until = timezone.now() - timedelta(minutes=1)
    team.save()
    lider = team.members.get(role=MemberRole.LEADER)

    with pytest.raises(InvitationRejected, match="prazo de formação"):
        invite_member(
            actor=lider.student.user,
            team_id=team.id,
            student_id=StudentFactory().pk,
        )


def test_durante_a_janela_extra_ninguem_sai():
    team = equipe_com_prazo_encerrado_e_janela_extra()
    membro = TeamMemberFactory(team=team, role=MemberRole.MEMBER)

    with pytest.raises(LeaveTeamRejected, match="prazo de formação"):
        leave_team(actor=membro.student.user, team_id=team.id, confirm=True)
