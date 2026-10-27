import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.accounts.enums import UserRole
from apps.accounts.factories import StudentFactory, UserFactory
from apps.editions.factories import EditionFactory
from apps.teams.enums import MemberRole, TeamSituation, TeamStatus
from apps.teams.models import (
    Invitation,
    JoinRequest,
    LeadershipRequest,
    MemberNote,
    Team,
    TeamMember,
)


class TeamMemberFactory(DjangoModelFactory):
    class Meta:
        model = TeamMember

    team = factory.SubFactory("apps.teams.factories.TeamFactory", leader=False)
    edition = factory.SelfAttribute("team.edition")
    student = factory.SubFactory(StudentFactory)
    role = MemberRole.MEMBER


class TeamFactory(DjangoModelFactory):
    """Equipe já com líder ativo; use leader=False para criá-la sem."""

    class Meta:
        model = Team
        skip_postgeneration_save = True

    edition = factory.SubFactory(EditionFactory)
    name = factory.Sequence(lambda n: f"Equipe {n}")
    code = factory.Sequence(lambda n: f"EQ{n:04d}")

    class Params:
        incomplete = factory.Trait(situation=TeamSituation.INCOMPLETE)
        disqualified = factory.Trait(
            status=TeamStatus.DISQUALIFIED,
            disqualification_reason="Desclassificada no teste.",
            disqualified_at=factory.LazyFunction(timezone.now),
            disqualified_by=factory.SubFactory(UserFactory, role=UserRole.ADMIN),
        )

    @factory.post_generation
    def leader(self, create, extracted, **kwargs):
        if create and extracted is not False:
            TeamMemberFactory(team=self, role=MemberRole.LEADER)


class InvitationFactory(DjangoModelFactory):
    class Meta:
        model = Invitation

    team = factory.SubFactory(TeamFactory)
    student = factory.SubFactory(StudentFactory)


class JoinRequestFactory(DjangoModelFactory):
    class Meta:
        model = JoinRequest

    team = factory.SubFactory(TeamFactory)
    student = factory.SubFactory(StudentFactory)


class LeadershipRequestFactory(DjangoModelFactory):
    class Meta:
        model = LeadershipRequest

    team = factory.SubFactory(TeamFactory)
    requester = factory.SubFactory(StudentFactory)
    justification = "O líder saiu da equipe."


class MemberNoteFactory(DjangoModelFactory):
    class Meta:
        model = MemberNote

    member = factory.SubFactory(TeamMemberFactory)
    author = factory.SubFactory(StudentFactory)
    text = "Integrante não participou das reuniões."
