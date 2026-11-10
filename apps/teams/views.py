from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.enums import UserRole
from apps.accounts.models import TeacherCourse
from apps.accounts.permissions import IsAdmin, IsStudent, IsTeacher
from apps.editions.enums import EditionStatus
from apps.editions.models import Edition
from apps.teams.models.team import Team
from apps.teams.serializers import TeamCreateSerializer, TeamSerializer
from apps.teams.use_cases.create_team import create_team


class TeamCreateView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request):
        serializer = TeamCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        edition = Edition.objects.filter(
            status=EditionStatus.PUBLISHED
        ).first()

        if edition is None:
            return Response(
                {"detail": "Não existe uma edição publicada no momento."},
                status=status.HTTP_409_CONFLICT,
            )

        team = create_team(
            actor=request.user,
            edition_id=edition.id,
            **serializer.validated_data,
        )

        return Response(
            TeamSerializer(team).data,
            status=status.HTTP_201_CREATED,
        )


class TeamDetailView(APIView):
    permission_classes = [IsAdmin | IsStudent | IsTeacher]

    def get(self, request, team_id):
        team = Team.objects.filter(pk=team_id).first()

        if team is None:
            return Response(
                {"detail": "Equipe não encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )

        allowed = False

        if request.user.role == UserRole.ADMIN:
            allowed = True

        elif request.user.role == UserRole.STUDENT:
            allowed = team.members.filter(
                student__user=request.user,
                active=True,
            ).exists()

        elif request.user.role == UserRole.TEACHER:
            allowed = TeacherCourse.objects.filter(
                teacher__user=request.user,
                active=True,
                course__challenges__projects__team_id=team.id,
            ).exists()

        if not allowed:
            return Response(
                {"detail": "Equipe não encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            TeamSerializer(team).data,
            status=status.HTTP_200_OK,
        )