import pytest
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.factories import StudentFactory, UserFactory
from apps.teams.enums import MemberRole, TeamStatus
from apps.teams.exceptions import (
    MemberNoteNotFound,
    MemberNotePermissionDenied,
    MemberNoteRejected,
)
from apps.teams.factories import TeamFactory, TeamMemberFactory
from apps.teams.models import MemberNote
from apps.teams.use_cases.add_member_note import add_member_note

pytestmark = pytest.mark.django_db


def test_add_member_note_successfully():
    team = TeamFactory()
    leader = team.members.get(role=MemberRole.LEADER, active=True)
    target = StudentFactory(course=leader.student.course)
    membership = TeamMemberFactory(team=team, student=target)

    result = add_member_note(
        actor=leader.student.user,
        team_id=team.id,
        member_id=membership.pk,
        text="Participou ativamente das atividades.",
    )

    assert isinstance(result, MemberNote)
    assert result.member.student_id == target.pk
    assert result.author_id == leader.student.pk
    assert result.text == "Participou ativamente das atividades."
    assert MemberNote.objects.filter(pk=result.pk).exists()


def test_add_member_note_rejects_non_student():
    team = TeamFactory()
    leader = team.members.get(role=MemberRole.LEADER, active=True)
    target = StudentFactory(course=leader.student.course)
    membership = TeamMemberFactory(team=team, student=target)
    admin = UserFactory(role=UserRole.ADMIN)

    with pytest.raises(
        MemberNotePermissionDenied,
        match="Somente acadêmicos podem registrar observações.",
    ):
        add_member_note(
            actor=admin,
            team_id=team.id,
            member_id=membership.pk,
            text="Observação.",
        )


def test_add_member_note_rejects_student_without_profile():
    team = TeamFactory()
    target = StudentFactory()
    membership = TeamMemberFactory(team=team, student=target)
    student_user = UserFactory(role=UserRole.STUDENT)

    with pytest.raises(
        MemberNoteRejected,
        match="O perfil de acadêmico não foi encontrado.",
    ):
        add_member_note(
            actor=student_user,
            team_id=team.id,
            member_id=membership.pk,
            text="Observação.",
        )


def test_add_member_note_rejects_nonexistent_team():
    student = StudentFactory()

    with pytest.raises(MemberNoteNotFound, match="Equipe não encontrada."):
        add_member_note(
            actor=student.user,
            team_id=999999,
            member_id=999999,
            text="Observação.",
        )


def test_add_member_note_rejects_inactive_team():
    team = TeamFactory()
    leader = team.members.get(role=MemberRole.LEADER, active=True)
    target = StudentFactory(course=leader.student.course)
    membership = TeamMemberFactory(team=team, student=target)

    team.status = TeamStatus.DISQUALIFIED
    team.disqualification_reason = "Motivo do teste."
    team.disqualified_at = timezone.now()
    team.disqualified_by = UserFactory(role=UserRole.ADMIN)
    team.save()

    with pytest.raises(
        MemberNoteRejected,
        match="Não é possível registrar observações em uma equipe inativa.",
    ):
        add_member_note(
            actor=leader.student.user,
            team_id=team.id,
            member_id=membership.pk,
            text="Observação.",
        )


def test_add_member_note_rejects_non_leader():
    team = TeamFactory()
    leader = team.members.get(role=MemberRole.LEADER, active=True)
    target = StudentFactory(course=leader.student.course)
    TeamMemberFactory(team=team, student=target)

    with pytest.raises(
        MemberNotePermissionDenied,
        match="Somente o líder ativo da equipe pode registrar observações.",
    ):
        add_member_note(
            actor=target.user,
            team_id=team.id,
            member_id=leader.pk,
            text="Observação.",
        )


def test_add_member_note_rejects_student_outside_team():
    team = TeamFactory()
    leader = team.members.get(role=MemberRole.LEADER, active=True)
    outsider = StudentFactory(course=leader.student.course)
    membership = TeamMemberFactory(student=outsider)

    with pytest.raises(
        MemberNoteNotFound,
        match="O vínculo informado não é de um integrante ativo desta equipe.",
    ):
        add_member_note(
            actor=leader.student.user,
            team_id=team.id,
            member_id=membership.pk,
            text="Observação.",
        )


def test_add_member_note_rejects_inactive_member():
    team = TeamFactory()
    leader = team.members.get(role=MemberRole.LEADER, active=True)
    target = StudentFactory(course=leader.student.course)
    membership = TeamMemberFactory(team=team, student=target)

    membership.active = False
    membership.left_at = membership.joined_at
    membership.save(update_fields=["active", "left_at", "updated_at"])

    with pytest.raises(
        MemberNoteNotFound,
        match="O vínculo informado não é de um integrante ativo desta equipe.",
    ):
        add_member_note(
            actor=leader.student.user,
            team_id=team.id,
            member_id=membership.pk,
            text="Observação.",
        )


def test_add_member_note_rejects_leader_observing_themselves():
    team = TeamFactory()
    leader = team.members.get(role=MemberRole.LEADER, active=True)

    with pytest.raises(
        MemberNoteRejected,
        match="O líder não pode registrar observações sobre si mesmo.",
    ):
        add_member_note(
            actor=leader.student.user,
            team_id=team.id,
            member_id=leader.pk,
            text="Observação.",
        )


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_add_member_note_rejects_empty_text(text):
    team = TeamFactory()
    leader = team.members.get(role=MemberRole.LEADER, active=True)
    target = StudentFactory(course=leader.student.course)
    membership = TeamMemberFactory(team=team, student=target)

    with pytest.raises(
        MemberNoteRejected,
        match="O texto da observação é obrigatório.",
    ):
        add_member_note(
            actor=leader.student.user,
            team_id=team.id,
            member_id=membership.pk,
            text=text,
        )
