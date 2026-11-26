from django.db.models import Count, F, Q
from rest_framework import status
from rest_framework.generics import GenericAPIView
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
from apps.teams.exceptions import TeamNotFound
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
from apps.teams.use_cases.create_team import NoCurrentEdition, create_team
from apps.teams.use_cases.invite_member import invite_member
from apps.teams.use_cases.leave_team import leave_team
from apps.teams.use_cases.request_leadership import (
    request_leadership,
)
from apps.teams.use_cases.request_to_join import (
    request_to_join,
)
from apps.teams.use_cases.respond_invitation import (
    respond_invitation,
)
from apps.teams.use_cases.respond_join_request import respond_join_request
from apps.teams.use_cases.review_leadership_request import (
    review_leadership_request,
)
from apps.teams.use_cases.transfer_leadership import transfer_leadership
from config.authentication import SessionAuthenticationWith401


class TeamCreateView(GenericAPIView):
    serializer_class = TeamAvailabilitySerializer
    authentication_classes = [SessionAuthenticationWith401]
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request):
        serializer = TeamCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        edition = Edition.objects.filter(status=EditionStatus.PUBLISHED).first()

        if edition is None:
            raise NoCurrentEdition("Não há edição vigente.")

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

        search = request.query_params.get("search")

        if search:
            teams = teams.filter(Q(name__icontains=search) | Q(code__icontains=search))

        page = self.paginate_queryset(teams)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(teams, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TeamDetailView(APIView):
    authentication_classes = [SessionAuthenticationWith401]
    permission_classes = [IsAdmin | IsStudent | IsTeacher]

    def get(self, request, team_id):
        team = Team.objects.filter(pk=team_id).first()

        if team is None:
            raise TeamNotFound()

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
            raise TeamNotFound()

        return Response(
            TeamSerializer(team).data,
            status=status.HTTP_200_OK,
        )


class TeamInvitationView(APIView):
    authentication_classes = [SessionAuthenticationWith401]
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
            raise TeamNotFound()

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
    authentication_classes = [SessionAuthenticationWith401]
    permission_classes = [IsAuthenticated, IsStudent]

    def get(self, request, team_id):
        leader = TeamMember.objects.filter(
            team_id=team_id,
            student__user=request.user,
            role=MemberRole.LEADER,
            active=True,
        ).exists()

        if not leader:
            raise TeamNotFound()

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
        join_request = request_to_join(
            actor=request.user,
            team_id=team_id,
        )

        return Response(
            JoinRequestSerializer(join_request).data,
            status=status.HTTP_201_CREATED,
        )


class MyInvitationsView(APIView):
    authentication_classes = [SessionAuthenticationWith401]
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
    authentication_classes = [SessionAuthenticationWith401]
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request, invitation_id):
        serializer = InvitationResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        invitation = respond_invitation(
            actor=request.user,
            invitation_id=invitation_id,
            **serializer.validated_data,
        )

        return Response(
            InvitationSerializer(invitation).data,
            status=status.HTTP_200_OK,
        )


class MyJoinRequestsView(APIView):
    authentication_classes = [SessionAuthenticationWith401]
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


class JoinRequestResponseView(APIView):
    authentication_classes = [SessionAuthenticationWith401]
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request, join_request_id):
        serializer = JoinRequestResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        join_request = respond_join_request(
            actor=request.user,
            join_request_id=join_request_id,
            **serializer.validated_data,
        )

        return Response(
            JoinRequestSerializer(join_request).data,
            status=status.HTTP_200_OK,
        )


class TeamLeaveView(APIView):
    authentication_classes = [SessionAuthenticationWith401]
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request, team_id):
        serializer = TeamLeaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        leave_team(
            actor=request.user,
            team_id=team_id,
            **serializer.validated_data,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


class LeadershipTransferView(APIView):
    authentication_classes = [SessionAuthenticationWith401]
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request, team_id):
        serializer = LeadershipTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_leader = transfer_leadership(
            actor=request.user,
            team_id=team_id,
            **serializer.validated_data,
        )

        return Response(
            TeamMemberSerializer(new_leader).data,
            status=status.HTTP_200_OK,
        )


class LeadershipRequestCreateView(APIView):
    authentication_classes = [SessionAuthenticationWith401]
    permission_classes = [IsAuthenticated, IsStudent]

    def get(self, request, team_id):
        student = getattr(request.user, "student", None)

        if student is None:
            raise TeamNotFound()

        is_active_member = TeamMember.objects.filter(
            team_id=team_id,
            student=student,
            active=True,
        ).exists()

        if not is_active_member:
            raise TeamNotFound()

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

        leadership_request = request_leadership(
            actor=request.user,
            team_id=team_id,
            **serializer.validated_data,
        )

        return Response(
            LeadershipRequestSerializer(leadership_request).data,
            status=status.HTTP_201_CREATED,
        )


class TeacherLeadershipRequestsView(APIView):
    authentication_classes = [SessionAuthenticationWith401]
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
    authentication_classes = [SessionAuthenticationWith401]
    permission_classes = [IsAuthenticated, IsTeacher]

    def post(self, request, leadership_request_id):
        serializer = LeadershipRequestDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        leadership_request = review_leadership_request(
            actor=request.user,
            leadership_request_id=leadership_request_id,
            **serializer.validated_data,
        )

        return Response(
            LeadershipRequestSerializer(leadership_request).data,
            status=status.HTTP_200_OK,
        )
