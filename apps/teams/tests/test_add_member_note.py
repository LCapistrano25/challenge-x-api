import pytest
from django.core.exceptions import ValidationError

from apps.accounts.enums import UserRole
from apps.accounts.factories import StudentFactory, UserFactory
from apps.core.exceptions import BusinessRuleViolation
from apps.projects.exceptions import NotTeamLeader
from apps.teams.enums import MemberRole, TeamStatus
from apps.teams.exceptions import (
    MemberNoteNotFound,
    MemberNotePermissionDenied,
)
from apps.teams.factories import TeamFactory, TeamMemberFactory
from apps.teams.models import MemberNote
from apps.teams.use_cases.add_member_note import add_member_note


@pytest.mark.django_db
def test_add_member_note_creates_note():
    team = TeamFactory(status=TeamStatus.ACTIVE)
    leader = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    ).student
    member = StudentFactory()

    membership = TeamMemberFactory(
        team=team,
        student=member,
        role=MemberRole.MEMBER,
    )

    note = add_member_note(
        actor=leader.user,
        team_id=team.id,
        member_id=membership.id,
        text="Participação muito boa.",
    )

    assert isinstance(note, MemberNote)
    assert note.member == membership
    assert note.author == leader
    assert note.text == "Participação muito boa."


@pytest.mark.django_db
def test_add_member_note_rejects_non_student():
    non_student_role = next(role for role in UserRole if role != UserRole.STUDENT)
    actor = UserFactory(role=non_student_role)

    with pytest.raises(MemberNotePermissionDenied):
        add_member_note(
            actor=actor,
            team_id=999999,
            member_id=1,
            text="Observação.",
        )


@pytest.mark.django_db
def test_add_member_note_rejects_missing_student_profile():
    actor = UserFactory(role=UserRole.STUDENT)

    with pytest.raises(MemberNoteNotFound):
        add_member_note(
            actor=actor,
            team_id=999999,
            member_id=1,
            text="Observação.",
        )


@pytest.mark.django_db
def test_add_member_note_rejects_non_leader():
    team = TeamFactory(status=TeamStatus.ACTIVE)
    student = StudentFactory()
    member = StudentFactory()

    TeamMemberFactory(
        team=team,
        student=student,
        role=MemberRole.MEMBER,
    )
    membership = TeamMemberFactory(
        team=team,
        student=member,
        role=MemberRole.MEMBER,
    )

    with pytest.raises(NotTeamLeader):
        add_member_note(
            actor=student.user,
            team_id=team.id,
            member_id=membership.id,
            text="Observação.",
        )


@pytest.mark.django_db
def test_add_member_note_rejects_inactive_team():
    team = TeamFactory(status=TeamStatus.DISBANDED)
    leader = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    ).student
    member = StudentFactory()

    membership = TeamMemberFactory(
        team=team,
        student=member,
        role=MemberRole.MEMBER,
    )

    with pytest.raises(BusinessRuleViolation):
        add_member_note(
            actor=leader.user,
            team_id=team.id,
            member_id=membership.id,
            text="Observação.",
        )


@pytest.mark.django_db
def test_add_member_note_rejects_nonexistent_team():
    team = TeamFactory(status=TeamStatus.ACTIVE)
    leader = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    ).student
    member = StudentFactory()
    membership = TeamMemberFactory(team=team, student=member)

    with pytest.raises(MemberNoteNotFound):
        add_member_note(
            actor=leader.user,
            team_id=999999,
            member_id=membership.id,
            text="Observação.",
        )


@pytest.mark.django_db
def test_add_member_note_rejects_member_from_another_team():
    team = TeamFactory(status=TeamStatus.ACTIVE)
    leader = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    ).student

    other_team = TeamFactory(status=TeamStatus.ACTIVE)
    outsider = TeamMemberFactory(team=other_team)

    with pytest.raises(MemberNoteNotFound):
        add_member_note(
            actor=leader.user,
            team_id=team.id,
            member_id=outsider.id,
            text="Observação.",
        )


@pytest.mark.django_db
def test_add_member_note_rejects_inactive_member():
    team = TeamFactory(status=TeamStatus.ACTIVE)
    leader = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    ).student
    member = StudentFactory()
    membership = TeamMemberFactory(team=team, student=member)

    membership.active = False
    membership.left_at = membership.joined_at
    membership.save(update_fields=["active", "left_at"])

    with pytest.raises(MemberNoteNotFound):
        add_member_note(
            actor=leader.user,
            team_id=team.id,
            member_id=membership.id,
            text="Observação.",
        )


@pytest.mark.django_db
def test_add_member_note_rejects_nonexistent_member():
    team = TeamFactory(status=TeamStatus.ACTIVE)
    leader = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    ).student

    with pytest.raises(MemberNoteNotFound):
        add_member_note(
            actor=leader.user,
            team_id=team.id,
            member_id=999999,
            text="Observação.",
        )


@pytest.mark.django_db
def test_add_member_note_rejects_leader_observing_themselves():
    team = TeamFactory(status=TeamStatus.ACTIVE)
    leader_membership = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    )
    leader = leader_membership.student

    with pytest.raises(ValidationError):
        add_member_note(
            actor=leader.user,
            team_id=team.id,
            member_id=leader_membership.id,
            text="Observação.",
        )


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
@pytest.mark.django_db
def test_add_member_note_rejects_empty_text(text):
    team = TeamFactory(status=TeamStatus.ACTIVE)
    leader = team.members.get(
        role=MemberRole.LEADER,
        active=True,
    ).student
    member = StudentFactory()

    membership = TeamMemberFactory(
        team=team,
        student=member,
        role=MemberRole.MEMBER,
    )

    with pytest.raises(ValidationError):
        add_member_note(
            actor=leader.user,
            team_id=team.id,
            member_id=membership.id,
            text=text,
        )
