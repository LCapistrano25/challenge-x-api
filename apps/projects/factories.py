import factory
from factory.django import DjangoModelFactory

from apps.editions.enums import FieldKind
from apps.editions.factories import ChallengeFactory, StageFactory
from apps.projects.models import (
    Project,
    Submission,
    SubmissionItem,
    SubmissionReceipt,
    SubmissionVersion,
)
from apps.teams.enums import MemberRole
from apps.teams.factories import TeamFactory


class ProjectFactory(DjangoModelFactory):
    class Meta:
        model = Project

    team = factory.SubFactory(TeamFactory)
    # Edição e desafio sempre os da equipe: sem isso cada SubFactory criaria a sua.
    edition = factory.SelfAttribute("team.edition")
    challenge = factory.SubFactory(
        ChallengeFactory, edition=factory.SelfAttribute("..team.edition")
    )
    title = factory.Sequence(lambda n: f"Projeto {n}")
    summary = "Resumo da proposta."


class SubmissionFactory(DjangoModelFactory):
    class Meta:
        model = Submission

    project = factory.SubFactory(ProjectFactory)
    stage = factory.SubFactory(
        StageFactory, edition=factory.SelfAttribute("..project.edition")
    )


class SubmissionVersionFactory(DjangoModelFactory):
    class Meta:
        model = SubmissionVersion

    submission = factory.SubFactory(SubmissionFactory)
    number = factory.Sequence(lambda n: n + 1)
    # Quem envia é o líder da equipe do projeto.
    submitted_by = factory.LazyAttribute(
        lambda o: (
            o.submission.project.team.members.get(
                role=MemberRole.LEADER, active=True
            ).student
        )
    )


class SubmissionItemFactory(DjangoModelFactory):
    class Meta:
        model = SubmissionItem

    version = factory.SubFactory(SubmissionVersionFactory)
    kind = FieldKind.LINK
    link = "https://github.com/equipe/projeto"


class SubmissionReceiptFactory(DjangoModelFactory):
    class Meta:
        model = SubmissionReceipt

    version = factory.SubFactory(SubmissionVersionFactory)
