from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdmin, IsStudent, IsTeacher
from apps.editions.models import Stage
from apps.projects.models import Project
from apps.projects.rules import (
    ensure_actor_can_view_project,
    ensure_actor_is_team_member,
)
from apps.projects.selectors import (
    get_active_categories,
    get_eligible_challenges,
    get_project_deliverables,
    get_receipt_by_version,
)
from apps.projects.serializers import (
    CategorySelectionSerializer,
    ChallengeSelectionSerializer,
    DeliverableSubmissionSerializer,
    DeliverableVersionSerializer,
    ProjectDetailsSerializer,
    ProjectOptionsSerializer,
    ProjectSerializer,
    ReceiptDetailSerializer,
    StageDeliverableSerializer,
)
from apps.projects.use_cases.save_project_details import save_project_details
from apps.projects.use_cases.select_category import select_category
from apps.projects.use_cases.select_challenge import select_challenge
from apps.projects.use_cases.submit_stage_delivery import submit_stage_delivery
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


class ProjectCategoryView(APIView):
    permission_classes = [IsStudent]

    def put(self, request, team_id):
        team = get_team(team_id)
        serializer = CategorySelectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        project = select_category(
            actor=request.user,
            team=team,
            category=serializer.validated_data["category"],
        )
        return Response(ProjectSerializer(project).data)


def get_project(project_id):
    try:
        return Project.objects.select_related("team__edition").get(pk=project_id)
    except Project.DoesNotExist:
        raise NotFound("Projeto não encontrado.") from None


def get_stage(stage_id):
    try:
        return Stage.objects.get(pk=stage_id)
    except Stage.DoesNotExist:
        raise NotFound("Etapa não encontrada.") from None


class ProjectDeliverablesView(APIView):
    permission_classes = [IsStudent | IsTeacher | IsAdmin]

    def get(self, request, project_id):
        project = get_project(project_id)
        ensure_actor_can_view_project(project.team, request.user)
        stages = get_project_deliverables(project)
        serializer = StageDeliverableSerializer(
            stages, many=True, context={"project": project}
        )
        return Response(serializer.data)


class ProjectStageVersionsView(APIView):
    permission_classes = [IsStudent]

    def post(self, request, project_id, stage_id):
        project = get_project(project_id)
        stage = get_stage(stage_id)
        serializer = DeliverableSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        version = submit_stage_delivery(
            actor=request.user,
            project=project,
            stage=stage,
            items=serializer.validated_data["items"],
            notes=serializer.validated_data["notes"],
        )
        return Response(DeliverableVersionSerializer(version).data, status=201)


class VersionReceiptView(APIView):
    permission_classes = [IsStudent | IsAdmin]

    def get(self, request, version_id):
        receipt = get_receipt_by_version(version_id)
        if receipt is None:
            raise NotFound("Comprovante não encontrado.")
        ensure_actor_can_view_project(
            receipt.version.submission.project.team, request.user
        )
        return Response(ReceiptDetailSerializer(receipt).data)
