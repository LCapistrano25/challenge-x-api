from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdmin, IsStudent, IsTeacher
from apps.projects.models import Project
from apps.projects.rules import (
    ensure_actor_can_view_project,
    ensure_actor_is_team_member,
)
from apps.projects.selectors import get_active_categories, get_eligible_challenges
from apps.projects.serializers import (
    ChallengeSelectionSerializer,
    ProjectDetailsSerializer,
    ProjectOptionsSerializer,
    ProjectSerializer,
)
from apps.projects.use_cases.save_project_details import save_project_details
from apps.projects.use_cases.select_challenge import select_challenge
from apps.teams.models import Team


def get_team(team_id):
    # NotFound do DRF, não Http404: config/exception.py não trata o Http404 puro.
    try:
        return Team.objects.select_related("edition").get(pk=team_id)
    except Team.DoesNotExist:
        raise NotFound("Equipe não encontrada.") from None


class ProjectOptionsView(APIView):
    permission_classes = [IsStudent]

    def get(self, request, team_id):
        team = get_team(team_id)
        ensure_actor_is_team_member(team, request.user)
        options = {
            "challenges": get_eligible_challenges(team),
            "categories": get_active_categories(team.edition),
        }
        return Response(ProjectOptionsSerializer(options).data)


class TeamProjectView(APIView):
    permission_classes = [IsStudent | IsTeacher | IsAdmin]

    def get(self, request, team_id):
        team = get_team(team_id)
        ensure_actor_can_view_project(team, request.user)
        project = (
            Project.objects.select_related(
                "team", "challenge__course", "challenge__sdg", "category"
            )
            .filter(team=team)
            .first()
        )
        if project is None:
            raise NotFound("A equipe ainda não tem projeto.")
        return Response(ProjectSerializer(project).data)


class ProjectChallengeView(APIView):
    permission_classes = [IsStudent]

    def put(self, request, team_id):
        team = get_team(team_id)
        serializer = ChallengeSelectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        project = select_challenge(
            actor=request.user,
            team=team,
            challenge=serializer.validated_data["challenge"],
        )
        return Response(ProjectSerializer(project).data)


class ProjectDetailsView(APIView):
    permission_classes = [IsStudent]

    def put(self, request, team_id):
        team = get_team(team_id)
        serializer = ProjectDetailsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        project = save_project_details(
            actor=request.user, team=team, **serializer.validated_data
        )
        return Response(ProjectSerializer(project).data)
