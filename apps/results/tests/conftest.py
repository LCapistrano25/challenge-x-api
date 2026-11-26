from decimal import Decimal

import pytest

from apps.accounts.enums import UserRole
from apps.accounts.factories import UserFactory
from apps.core.factories import CourseFactory
from apps.editions.factories import (
    ChallengeFactory,
    CriterionFactory,
    EditionFactory,
    StageCriterionFactory,
    StageFactory,
)
from apps.evaluations.factories import StageScoreFactory
from apps.projects.factories import ProjectFactory
from apps.teams.factories import TeamFactory


@pytest.fixture
def admin(db):
    return UserFactory(role=UserRole.ADMIN)


@pytest.fixture
def edition(db):
    return EditionFactory()


@pytest.fixture
def stages(edition):
    """Duas etapas pontuadas, de 3 pontos cada."""
    return [StageFactory(edition=edition), StageFactory(edition=edition)]


@pytest.fixture
def criteria(edition, stages):
    """Dois critérios de desempate, ligados às duas etapas: [stage][ordem]."""
    items = [CriterionFactory(edition=edition, tiebreak_order=n) for n in (1, 2)]
    return {
        stage.pk: [
            StageCriterionFactory(stage=stage, criterion=criterion)
            for criterion in items
        ]
        for stage in stages
    }


@pytest.fixture
def make_project(edition, stages):
    default_course = CourseFactory()

    def make(*values, course=None, team=None, **kwargs):
        """values: uma nota definitiva por etapa; None deixa a etapa sem nota."""
        project = ProjectFactory(
            team=team or TeamFactory(edition=edition),
            challenge=ChallengeFactory(
                edition=edition, course=course or default_course
            ),
            **kwargs,
        )
        for stage, value in zip(stages, values, strict=False):
            if value is not None:
                StageScoreFactory(
                    project=project,
                    stage=stage,
                    definitive=True,
                    value=Decimal(value),
                )
        return project

    return make
