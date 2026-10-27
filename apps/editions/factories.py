from datetime import timedelta
from decimal import Decimal

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.accounts.factories import ExternalReviewerFactory
from apps.core.factories import CourseFactory, SdgFactory
from apps.editions.enums import FieldKind, StageKind
from apps.editions.models import (
    Category,
    Challenge,
    Criterion,
    Edition,
    EditionReviewer,
    EditionSdg,
    Stage,
    StageCriterion,
    StageSubmissionField,
)


class EditionFactory(DjangoModelFactory):
    class Meta:
        model = Edition

    # (year, semester) é único: cada edição nova avança um semestre.
    year = factory.Sequence(lambda n: 2026 + n // 2)
    semester = factory.Sequence(lambda n: n % 2 + 1)


class EditionSdgFactory(DjangoModelFactory):
    class Meta:
        model = EditionSdg

    edition = factory.SubFactory(EditionFactory)
    sdg = factory.SubFactory(SdgFactory)


class CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category

    edition = factory.SubFactory(EditionFactory)
    name = factory.Sequence(lambda n: f"Categoria {n}")


class ChallengeFactory(DjangoModelFactory):
    class Meta:
        model = Challenge

    edition = factory.SubFactory(EditionFactory)
    course = factory.SubFactory(CourseFactory)
    sdg = factory.SubFactory(SdgFactory)
    description = factory.Sequence(lambda n: f"Desafio {n}")

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # O desafio só vale com a ODS habilitada na edição (RN09).
        EditionSdg.objects.get_or_create(edition=kwargs["edition"], sdg=kwargs["sdg"])
        return super()._create(model_class, *args, **kwargs)


class StageFactory(DjangoModelFactory):
    class Meta:
        model = Stage

    edition = factory.SubFactory(EditionFactory)
    order = factory.Sequence(lambda n: n + 1)
    name = factory.LazyAttribute(lambda o: f"Etapa {o.order}")
    kind = StageKind.SUBMISSION
    starts_at = factory.LazyFunction(timezone.now)
    ends_at = factory.LazyAttribute(lambda o: o.starts_at + timedelta(days=14))
    evaluation_ends_at = factory.LazyAttribute(lambda o: o.ends_at + timedelta(days=7))
    max_score = Decimal("3.00")

    class Params:
        formation = factory.Trait(
            kind=StageKind.FORMATION,
            scored=False,
            max_score=None,
            evaluation_ends_at=None,
        )


class StageSubmissionFieldFactory(DjangoModelFactory):
    class Meta:
        model = StageSubmissionField

    stage = factory.SubFactory(StageFactory)
    kind = FieldKind.LINK
    label = "Link do repositório"


class CriterionFactory(DjangoModelFactory):
    class Meta:
        model = Criterion

    edition = factory.SubFactory(EditionFactory)
    name = factory.Sequence(lambda n: f"Critério {n}")


class StageCriterionFactory(DjangoModelFactory):
    class Meta:
        model = StageCriterion

    stage = factory.SubFactory(StageFactory)
    # Mesma edição da etapa: sem isso cada SubFactory criaria a sua.
    criterion = factory.SubFactory(
        CriterionFactory, edition=factory.SelfAttribute("..stage.edition")
    )
    max_score = Decimal("1.00")


class EditionReviewerFactory(DjangoModelFactory):
    class Meta:
        model = EditionReviewer

    edition = factory.SubFactory(EditionFactory)
    reviewer = factory.SubFactory(ExternalReviewerFactory)
