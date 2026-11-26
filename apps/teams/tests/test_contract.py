from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import StudentFactory
from apps.core.tests.contract import mismatches, schema
from apps.editions.enums import EditionStatus
from apps.editions.factories import EditionFactory, StageFactory
from apps.teams.enums import MemberRole
from apps.teams.factories import (
    InvitationFactory,
    JoinRequestFactory,
    TeamFactory,
)
from apps.teams.models import TeamMember

pytestmark = pytest.mark.django_db


def test_listagem_de_equipes_segue_o_contrato():
    student = StudentFactory()
    team = TeamFactory()

    team.edition.status = EditionStatus.PUBLISHED
    team.edition.max_members = 5
    team.edition.save()

    client = APIClient()
    client.force_authenticate(user=student.user)

    response = client.get("/api/teams", {"search": team.name})

    assert response.status_code == 200
    assert mismatches(response.data, schema("PaginatedTeamListing")) == []


def test_detalhe_da_equipe_segue_o_contrato():
    from apps.teams.factories import TeamMemberFactory

    student = StudentFactory()
    team = TeamFactory(leader=False)
    TeamMemberFactory(team=team, student=student)

    client = APIClient()
    client.force_authenticate(user=student.user)

    response = client.get(f"/api/teams/{team.id}")

    assert response.status_code == 200
    assert mismatches(response.data, schema("Team")) == []


def test_criacao_de_equipe_segue_o_contrato():
    student = StudentFactory()
    invited_students = StudentFactory.create_batch(2)

    edition = EditionFactory(status=EditionStatus.PUBLISHED)
    now = timezone.now()

    StageFactory(
        edition=edition,
        formation=True,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=7),
    )

    client = APIClient()
    client.force_authenticate(user=student.user)

    response = client.post(
        "/api/teams",
        {
            "name": "Equipe Contrato",
            "invitations": [
                {"student_id": invited_students[0].pk},
                {"student_id": invited_students[1].pk},
            ],
        },
        format="json",
    )

    assert response.status_code == 201, response.data
    assert mismatches(response.data, schema("Team")) == []


def test_listagem_de_convites_segue_o_contrato():
    student = StudentFactory()
    InvitationFactory(student=student)

    client = APIClient()
    client.force_authenticate(user=student.user)

    response = client.get("/api/me/invitations")

    assert response.status_code == 200
    assert (
        mismatches(
            response.data,
            {
                "type": "array",
                "items": schema("Invitation"),
            },
        )
        == []
    )


def test_resposta_de_convite_segue_o_contrato():
    from apps.teams.tests.test_api import create_open_formation

    team = TeamFactory()
    create_open_formation(team.edition)
    student = StudentFactory()
    invitation = InvitationFactory(team=team, student=student)

    client = APIClient()
    client.force_authenticate(user=student.user)

    response = client.post(
        f"/api/invitations/{invitation.id}/respond",
        {"status": "ACCEPTED"},
        format="json",
    )

    assert response.status_code == 200, response.data
    assert mismatches(response.data, schema("Invitation")) == []


def test_listagem_de_solicitacoes_segue_o_contrato():
    student = StudentFactory()
    JoinRequestFactory(student=student)

    client = APIClient()
    client.force_authenticate(user=student.user)

    response = client.get("/api/me/join-requests")

    assert response.status_code == 200
    assert (
        mismatches(
            response.data,
            {
                "type": "array",
                "items": schema("JoinRequest"),
            },
        )
        == []
    )


def test_aprovacao_de_solicitacao_segue_o_contrato():
    from apps.teams.tests.test_api import create_open_formation

    team = TeamFactory()
    create_open_formation(team.edition)
    join_request = JoinRequestFactory(team=team)

    leader = TeamMember.objects.get(
        team=team,
        role=MemberRole.LEADER,
        active=True,
    )

    client = APIClient()
    client.force_authenticate(user=leader.student.user)

    response = client.post(
        f"/api/join-requests/{join_request.id}/respond",
        {"status": "APPROVED"},
        format="json",
    )

    assert response.status_code == 200, response.data
    assert mismatches(response.data, schema("JoinRequest")) == []
