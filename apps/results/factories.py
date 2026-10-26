from decimal import Decimal

import factory
from factory.django import DjangoModelFactory

from apps.accounts.factories import UserFactory
from apps.editions.factories import EditionFactory
from apps.projects.factories import ProjectFactory
from apps.results.enums import CertificateKind
from apps.results.models import (
    Certificate,
    CertificateTemplate,
    ProjectResult,
    StudentScore,
)
from apps.teams.enums import MemberRole


class ProjectResultFactory(DjangoModelFactory):
    class Meta:
        model = ProjectResult

    project = factory.SubFactory(ProjectFactory)
    final_score = Decimal("7.50")

    class Params:
        awarded = factory.Trait(finalist=True, award=1)


class StudentScoreFactory(DjangoModelFactory):
    class Meta:
        model = StudentScore

    project = factory.SubFactory(ProjectFactory)
    # O líder é integrante da equipe do projeto.
    student = factory.LazyAttribute(
        lambda o: o.project.team.members.get(role=MemberRole.LEADER).student
    )
    term = factory.SelfAttribute("student.term")
    points = Decimal("1.50")


class CertificateTemplateFactory(DjangoModelFactory):
    class Meta:
        model = CertificateTemplate

    edition = factory.SubFactory(EditionFactory)
    kind = CertificateKind.PARTICIPATION


class CertificateFactory(DjangoModelFactory):
    class Meta:
        model = Certificate

    template = factory.SubFactory(CertificateTemplateFactory)
    user = factory.SubFactory(UserFactory)
    workload_hours = 20
