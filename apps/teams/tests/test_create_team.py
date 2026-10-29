
import pytest
from django.utils import timezone
from datetime import timedelta

from apps.accounts.factories import StudentFactory
from apps.editions.enums import StageKind
from apps.editions.factories import EditionFactory, StageFactory
from apps.teams.enums import MemberRole
from apps.teams.models import Team, TeamMember
from apps.teams.use_cases.create_team import create_team

pytestmark = pytest.mark.django_db


def test_aluno_cria_equipe_e_se_torna_lider():
    student = StudentFactory()
    edition = EditionFactory()

    now = timezone.now()
    StageFactory(
        edition=edition,
        formation=True,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=7),
    )

    team = create_team(
        actor=student.user,
        edition_id=edition.id,
        name="Equipe Teste",
    )

    assert isinstance(team, Team)
    assert team.name == "Equipe Teste"
    assert team.edition == edition
    assert team.code

    membership = TeamMember.objects.get(
        team=team,
        student=student,
        active=True,
    )
    assert membership.role == MemberRole.LEADER
    assert membership.left_at is None
