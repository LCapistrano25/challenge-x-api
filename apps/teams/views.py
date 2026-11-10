from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.enums import UserRole
from apps.accounts.models import TeacherCourse
from apps.accounts.permissions import IsAdmin, IsStudent, IsTeacher
from apps.editions.enums import EditionStatus
from apps.editions.models import Edition
from apps.teams.enums import MemberRole
from apps.teams.models import Invitation, TeamMember
from apps.teams.models.team import Team
from apps.teams.serializers import (
    InvitationCreateSerializer,
    InvitationResponseSerializer,
    InvitationSerializer,
    InvitationStatusFilterSerializer,
    TeamCreateSerializer,
    TeamSerializer,
)
from apps.teams.use_cases.create_team import create_team
from apps.teams.use_cases.invite_member import invite_member
from apps.teams.use_cases.respond_invitation import (
    InvitationResponseRejected,
    respond_invitation,
)


class TeamCreateView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request):
        serializer = TeamCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        edition = Edition.objects.filter(status=EditionStatus.PUBLISHED).first()

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


class TeamInvitationView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request, team_id):
        serializer = InvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        invitation = invite_member(
            actor=request.user,
            team_id=team_id,
            **serializer.validated_data,
        )

        return Response(
            InvitationSerializer(invitation).data,
            status=status.HTTP_201_CREATED,
        )

    def get(self, request, team_id):
        leader = TeamMember.objects.filter(
            team_id=team_id,
            student__user=request.user,
            role=MemberRole.LEADER,
            active=True,
        ).exists()

        if not leader:
            return Response(
                {"detail": "Equipe não encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )

        filter_serializer = InvitationStatusFilterSerializer(
            data=request.query_params,
        )
        filter_serializer.is_valid(raise_exception=True)

        invitations = Invitation.objects.filter(
            team_id=team_id,
        ).select_related("team", "student__user")

        invitation_status = filter_serializer.validated_data.get("status")

        if invitation_status:
            invitations = invitations.filter(status=invitation_status)

        return Response(
            InvitationSerializer(invitations, many=True).data,
            status=status.HTTP_200_OK,
        )


class MyInvitationsView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def get(self, request):
        filter_serializer = InvitationStatusFilterSerializer(
            data=request.query_params,
        )
        filter_serializer.is_valid(raise_exception=True)

        student = request.user.student

        invitations = Invitation.objects.filter(
            student=student,
        ).select_related("team", "student__user")

        invitation_status = filter_serializer.validated_data.get("status")

        if invitation_status:
            invitations = invitations.filter(status=invitation_status)

        return Response(
            InvitationSerializer(invitations, many=True).data,
            status=status.HTTP_200_OK,
        )


class InvitationResponseView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request, invitation_id):
        serializer = InvitationResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            invitation = respond_invitation(
                actor=request.user,
                invitation_id=invitation_id,
                **serializer.validated_data,
            )

        except InvitationResponseRejected as error:
            message = str(error)

            if message in (
                "Convite não encontrado.",
                "Este convite não pertence ao estudante autenticado.",
            ):
                code = "not_found"
                http_status = status.HTTP_404_NOT_FOUND

            else:
                error_codes = dict(
    [
        (
            "Não existe prazo de formação aberto para esta equipe.",
            "formation_closed",
        ),
        (
            "A equipe já atingiu o limite máximo de integrantes.",
            "team_full",
        ),
        (
            "O estudante já participa de uma equipe ativa nesta edição.",
            "student_already_in_team",
        ),
        (
            "Este convite não está mais pendente.",
            "invitation_not_pending",
        ),
    ]
)
                code = error_codes.get(
                    message,
                    "invitation_response_rejected",
                )
                http_status = status.HTTP_409_CONFLICT

            return Response(
                {
                    "error": {
                        "code": code,
                        "message": message,
                        "details": None,
                    }
                },
                status=http_status,
            )

        return Response(
            InvitationSerializer(invitation).data,
            status=status.HTTP_200_OK,
        )
