from decimal import Decimal

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.accounts.factories import ExternalReviewerFactory, TeacherFactory
from apps.editions.factories import StageCriterionFactory, StageFactory
from apps.editions.models import EditionReviewer
from apps.evaluations.enums import (
    EvaluationStatus,
    FinalEvaluationStatus,
    QuestionKind,
    ScoreStatus,
)
from apps.evaluations.models import (
    Evaluation,
    EvaluationItem,
    FinalAnswer,
    FinalEvaluation,
    FinalForm,
    FinalQuestion,
    StageScore,
)
from apps.projects.factories import ProjectFactory


class EvaluationFactory(DjangoModelFactory):
    class Meta:
        model = Evaluation

    project = factory.SubFactory(ProjectFactory)
    # Etapa sempre da edição do projeto.
    stage = factory.SubFactory(
        StageFactory, edition=factory.SelfAttribute("..project.edition")
    )
    teacher = factory.SubFactory(TeacherFactory)

    class Params:
        finalized = factory.Trait(
            status=EvaluationStatus.FINALIZED,
            finalized_at=factory.LazyFunction(timezone.now),
        )


class EvaluationItemFactory(DjangoModelFactory):
    class Meta:
        model = EvaluationItem

    evaluation = factory.SubFactory(EvaluationFactory)
    # Critério da mesma etapa avaliada.
    stage_criterion = factory.SubFactory(
        StageCriterionFactory, stage=factory.SelfAttribute("..evaluation.stage")
    )
    points = Decimal("0.50")


class StageScoreFactory(DjangoModelFactory):
    class Meta:
        model = StageScore

    project = factory.SubFactory(ProjectFactory)
    stage = factory.SubFactory(
        StageFactory, edition=factory.SelfAttribute("..project.edition")
    )

    class Params:
        definitive = factory.Trait(
            status=ScoreStatus.DEFINITIVE, value=Decimal("2.50"), evaluation_count=2
        )


class FinalFormFactory(DjangoModelFactory):
    class Meta:
        model = FinalForm

    edition = factory.SubFactory("apps.editions.factories.EditionFactory")
    title = "Avaliação da Apresentação Final"


class FinalQuestionFactory(DjangoModelFactory):
    class Meta:
        model = FinalQuestion

    form = factory.SubFactory(FinalFormFactory)
    order = factory.Sequence(lambda n: n + 1)
    prompt = "Clareza e qualidade do pitch"
    kind = QuestionKind.SCORE
    max_score = Decimal("10.00")

    class Params:
        text = factory.Trait(kind=QuestionKind.TEXT, max_score=None)


class FinalEvaluationFactory(DjangoModelFactory):
    class Meta:
        model = FinalEvaluation

    project = factory.SubFactory(ProjectFactory)
    reviewer = factory.SubFactory(ExternalReviewerFactory)
    form = factory.SubFactory(
        FinalFormFactory, edition=factory.SelfAttribute("..project.edition")
    )

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # Só avalia quem foi convidado para a edição do projeto.
        EditionReviewer.objects.get_or_create(
            edition=kwargs["project"].edition, reviewer=kwargs["reviewer"]
        )
        return super()._create(model_class, *args, **kwargs)

    class Params:
        evaluated = factory.Trait(
            status=FinalEvaluationStatus.EVALUATED,
            finalized_at=factory.LazyFunction(timezone.now),
        )


class FinalAnswerFactory(DjangoModelFactory):
    class Meta:
        model = FinalAnswer

    evaluation = factory.SubFactory(FinalEvaluationFactory)
    question = factory.SubFactory(
        FinalQuestionFactory, form=factory.SelfAttribute("..evaluation.form")
    )
    value = Decimal("8.00")
