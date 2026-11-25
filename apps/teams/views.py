from django.db.models import Count, F, Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.enums import UserRole
from apps.accounts.models import TeacherCourse
from apps.accounts.permissions import IsAdmin, IsStudent, IsTeacher
from apps.editions.enums import EditionStatus
from apps.editions.models import Edition
from apps.projects.models import Project
from apps.teams.enums import (
    MemberRole,
    TeamStatus,
)
from apps.teams.models import (
    Invitation,
    JoinRequest,
    LeadershipRequest,
    TeamMember,
)
from apps.teams.models.team import Team
from apps.teams.serializers import (
    InvitationCreateSerializer,
    InvitationResponseSerializer,
    InvitationSerializer,
    InvitationStatusFilterSerializer,
    JoinRequestResponseSerializer,
    JoinRequestSerializer,
    JoinRequestStatusFilterSerializer,
    LeadershipRequestCreateSerializer,
    LeadershipRequestDecisionSerializer,
    LeadershipRequestSerializer,
    LeadershipTransferSerializer,
    TeamAvailabilitySerializer,
    TeamCreateSerializer,
    TeamLeaveSerializer,
    TeamMemberSerializer,
    TeamSerializer,
)
from apps.teams.use_cases.create_team import create_team
from apps.teams.use_cases.get_student_dashboard import get_student_dashboard
from apps.teams.use_cases.invite_member import invite_member
from apps.teams.use_cases.leave_team import (
    LeaveTeamRejected,
    leave_team,
)
from apps.teams.use_cases.request_leadership import (
    LeadershipRequestRejected,
    request_leadership,
)
from apps.teams.use_cases.request_to_join import (
    JoinRequestRejected,
    request_to_join,
)
from apps.teams.use_cases.respond_invitation import (
    InvitationResponseRejected,
    respond_invitation,
)
from apps.teams.use_cases.respond_join_request import (
    JoinRequestResponseRejected,
    respond_join_request,
)
from apps.teams.use_cases.review_leadership_request import (
    LeadershipRequestReviewRejected,
    review_leadership_request,
)
from apps.teams.use_cases.transfer_leadership import (
    LeadershipTransferRejected,
    transfer_leadership,
)


class StudentDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def get(self, request):
        dashboard = get_student_dashboard(actor=request.user)

        return Response(
            dashboard,
            status=status.HTTP_200_OK,
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

    def get(self, request):
        teams = (
            Team.objects.filter(
                status=TeamStatus.ACTIVE,
                edition__status=EditionStatus.PUBLISHED,
            )
            .select_related("edition")
            .annotate(
                active_members_count=Count(
                    "members",
                    filter=Q(members__active=True),
                )
            )
            .filter(active_members_count__lt=F("edition__max_members"))
            .order_by("name")
        )

        return Response(
            TeamAvailabilitySerializer(teams, many=True).data,
            status=status.HTTP_200_OK,
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


class JoinRequestCreateView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

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

        filter_serializer = JoinRequestStatusFilterSerializer(
            data=request.query_params,
        )
        filter_serializer.is_valid(raise_exception=True)

        join_requests = JoinRequest.objects.filter(
            team_id=team_id,
        ).select_related("team", "student__user")

        request_status = filter_serializer.validated_data.get("status")

        if request_status:
            join_requests = join_requests.filter(status=request_status)

        return Response(
            JoinRequestSerializer(join_requests, many=True).data,
            status=status.HTTP_200_OK,
        )

    def post(self, request, team_id):
        try:
            join_request = request_to_join(
                actor=request.user,
                team_id=team_id,
            )

        except JoinRequestRejected as error:
            message = str(error)

            if message == "Equipe não encontrada.":
                code = "team_not_found"
                http_status = status.HTTP_404_NOT_FOUND
            else:
                error_codes = {
                    "Não existe prazo de formação aberto para esta equipe.": (
                        "formation_closed"
                    ),
                    "A equipe já atingiu o limite máximo de integrantes.": (
                        "team_full"
                    ),
                    "O aluno já participa de uma equipe ativa nesta edição.": (
                        "student_already_in_team"
                    ),
                    "Já existe uma solicitação pendente para esta equipe.": (
                        "request_already_pending"
                    ),
                    (
                        "Não foi possível registrar a solicitação. "
                        "Verifique se já existe uma solicitação pendente."
                    ): "request_already_pending",
                }

                code = error_codes.get(
                    message,
                    "join_request_rejected",
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
            JoinRequestSerializer(join_request).data,
            status=status.HTTP_201_CREATED,
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
                error_codes = {
                    "Não existe prazo de formação aberto para esta equipe.": (
                        "formation_closed"
                    ),
                    "A equipe já atingiu o limite máximo de integrantes.": (
                        "team_full"
                    ),
                    (
                        "O estudante já participa de uma equipe ativa nesta edição."
                    ): "student_already_in_team",
                    "Este convite não está mais pendente.": ("invitation_not_pending"),
                }
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


class MyJoinRequestsView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def get(self, request):
        filter_serializer = JoinRequestStatusFilterSerializer(
            data=request.query_params,
        )
        filter_serializer.is_valid(raise_exception=True)

        student = request.user.student

        join_requests = JoinRequest.objects.filter(
            student=student,
        ).select_related("team", "student__user")

        request_status = filter_serializer.validated_data.get("status")

        if request_status:
            join_requests = join_requests.filter(status=request_status)

        return Response(
            JoinRequestSerializer(join_requests, many=True).data,
            status=status.HTTP_200_OK,
        )


class TeamJoinRequestsView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

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

        filter_serializer = JoinRequestStatusFilterSerializer(
            data=request.query_params,
        )
        filter_serializer.is_valid(raise_exception=True)

        join_requests = JoinRequest.objects.filter(
            team_id=team_id,
        ).select_related("team", "student__user")

        request_status = filter_serializer.validated_data.get("status")

        if request_status:
            join_requests = join_requests.filter(status=request_status)

        return Response(
            JoinRequestSerializer(join_requests, many=True).data,
            status=status.HTTP_200_OK,
        )


class JoinRequestResponseView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request, join_request_id):
        serializer = JoinRequestResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            join_request = respond_join_request(
                actor=request.user,
                join_request_id=join_request_id,
                approve=serializer.validated_data["approve"],
            )

        except JoinRequestResponseRejected as error:
            message = str(error)

            if message == "Solicitação não encontrada.":
                code = "join_request_not_found"
                http_status = status.HTTP_404_NOT_FOUND
            else:
                code = "join_request_response_rejected"
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
            JoinRequestSerializer(join_request).data,
            status=status.HTTP_200_OK,
        )


class TeamLeaveView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request, team_id):
        serializer = TeamLeaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            leave_team(
                actor=request.user,
                team_id=team_id,
                **serializer.validated_data,
            )
        except LeaveTeamRejected as error:
            message = str(error)

            if message in (
                "Equipe não encontrada.",
                "O perfil de aluno não foi encontrado.",
                "O aluno não possui vínculo ativo com esta equipe.",
            ):
                code = "not_found"
                http_status = status.HTTP_404_NOT_FOUND
            else:
                error_codes = {
                    "Não existe prazo de formação aberto para esta equipe.": (
                        "formation_closed"
                    ),
                    "Transfira a liderança antes de sair da equipe.": (
                        "leader_must_transfer"
                    ),
                }

                code = getattr(error, "code", None) or error_codes.get(
                    message,
                    "leave_team_rejected",
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

        return Response(status=status.HTTP_204_NO_CONTENT)


class LeadershipTransferView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request, team_id):
        serializer = LeadershipTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            new_leader = transfer_leadership(
                actor=request.user,
                team_id=team_id,
                **serializer.validated_data,
            )

        except LeadershipTransferRejected as error:
            message = str(error)

            if message in (
                "Equipe não encontrada.",
                "O perfil de aluno não foi encontrado.",
            ):
                code = "not_found"
                http_status = status.HTTP_404_NOT_FOUND
            elif message == (
                "Somente o líder ativo da equipe pode transferir a liderança."
            ):
                code = "permission_denied"
                http_status = status.HTTP_403_FORBIDDEN
            else:
                code = "leadership_transfer_rejected"
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
            TeamMemberSerializer(new_leader).data,
            status=status.HTTP_200_OK,
        )


class LeadershipRequestCreateView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def get(self, request, team_id):
        student = getattr(request.user, "student", None)

        if student is None:
            return Response(
                {"detail": "Equipe não encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )

        is_active_member = TeamMember.objects.filter(
            team_id=team_id,
            student=student,
            active=True,
        ).exists()

        if not is_active_member:
            return Response(
                {"detail": "Equipe não encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )

        filter_serializer = JoinRequestStatusFilterSerializer(
            data=request.query_params,
        )
        filter_serializer.is_valid(raise_exception=True)

        leadership_requests = LeadershipRequest.objects.filter(
            team_id=team_id,
        ).select_related(
            "team",
            "requester__user",
            "teacher__user",
        )

        request_status = filter_serializer.validated_data.get("status")

        if request_status:
            leadership_requests = leadership_requests.filter(
                status=request_status,
            )

        return Response(
            LeadershipRequestSerializer(
                leadership_requests,
                many=True,
            ).data,
            status=status.HTTP_200_OK,
        )

    def post(self, request, team_id):
        serializer = LeadershipRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            leadership_request = request_leadership(
                actor=request.user,
                team_id=team_id,
                **serializer.validated_data,
            )

        except LeadershipRequestRejected as error:
            message = str(error)

            if message in (
                "Equipe não encontrada.",
                "O perfil de aluno não foi encontrado.",
                "Somente integrantes ativos podem solicitar a liderança.",
            ):
                code = "not_found"
                http_status = status.HTTP_404_NOT_FOUND
            else:
                code = "leadership_request_rejected"
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
            LeadershipRequestSerializer(leadership_request).data,
            status=status.HTTP_201_CREATED,
        )


class TeacherLeadershipRequestsView(APIView):
    permission_classes = [IsAuthenticated, IsTeacher]

    def get(self, request):
        filter_serializer = JoinRequestStatusFilterSerializer(
            data=request.query_params,
        )
        filter_serializer.is_valid(raise_exception=True)

        team_ids = Project.objects.filter(
            challenge__course__teacher_links__teacher__user=request.user,
            challenge__course__teacher_links__active=True,
        ).values_list("team_id", flat=True)

        leadership_requests = (
            LeadershipRequest.objects.filter(
                team_id__in=team_ids,
            )
            .select_related(
                "team",
                "requester__user",
                "teacher__user",
            )
            .distinct()
        )

        request_status = filter_serializer.validated_data.get("status")

        if request_status:
            leadership_requests = leadership_requests.filter(
                status=request_status,
            )

        return Response(
            LeadershipRequestSerializer(
                leadership_requests,
                many=True,
            ).data,
            status=status.HTTP_200_OK,
        )


class LeadershipRequestReviewView(APIView):
    permission_classes = [IsAuthenticated, IsTeacher]

    def post(self, request, leadership_request_id):
        serializer = LeadershipRequestDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            leadership_request = review_leadership_request(
                actor=request.user,
                leadership_request_id=leadership_request_id,
                **serializer.validated_data,
            )
        except LeadershipRequestReviewRejected as error:
            message = str(error)

            if message in (
                "Solicitação não encontrada.",
                "Equipe não encontrada.",
            ):
                code = "not_found"
                http_status = status.HTTP_404_NOT_FOUND
            else:
                code = "leadership_request_review_rejected"
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
            LeadershipRequestSerializer(leadership_request).data,
            status=status.HTTP_200_OK,
        )
