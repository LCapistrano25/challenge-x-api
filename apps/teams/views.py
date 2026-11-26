from django.db.models import Count, F, Q
from rest_framework import status
from rest_framework.exceptions import NotFound
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
from apps.projects.rules import ensure_actor_is_team_leader
from apps.teams.enums import MemberRole, TeamStatus
from apps.teams.exceptions import MemberNoteError, TeamNotFound
from apps.teams.models import (
    Invitation,
    JoinRequest,
    LeadershipRequest,
    MemberNote,
    Team,
    TeamMember,
)
from apps.teams.selectors import list_invitable_students
from apps.teams.serializers import (
    AdminTeamListItemSerializer,
    AdminTeamListQuerySerializer,
    DisqualifyTeamSerializer,
    InvitableStudentQuerySerializer,
    InvitableStudentSerializer,
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
    MemberNoteCreateSerializer,
    MemberNoteSerializer,
    TeamAvailabilitySerializer,
    TeamCreateSerializer,
    TeamLeaveSerializer,
    TeamMemberSerializer,
    TeamSerializer,
    TeamUpdateSerializer,
)
from apps.teams.use_cases.add_member_note import add_member_note
from apps.teams.use_cases.create_team import NoCurrentEdition, create_team
from apps.teams.use_cases.disqualify_team import disqualify_team
from apps.teams.use_cases.get_student_dashboard import get_student_dashboard
from apps.teams.use_cases.invite_member import invite_member
from apps.teams.use_cases.leave_team import leave_team
from apps.teams.use_cases.rename_team import rename_team
from apps.teams.use_cases.request_leadership import request_leadership
from apps.teams.use_cases.request_to_join import request_to_join
from apps.teams.use_cases.respond_invitation import respond_invitation
from apps.teams.use_cases.respond_join_request import respond_join_request
from apps.teams.use_cases.review_leadership_request import review_leadership_request
from apps.teams.use_cases.transfer_leadership import transfer_leadership
from config.authentication import SessionAuthenticationWith401
from config.pagination import DefaultPagination


class StudentDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def get(self, request):
        dashboard = get_student_dashboard(actor=request.user)

        return Response(
            dashboard,
            status=status.HTTP_200_OK,
        )


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

    def patch(self, request, team_id):
        serializer = TeamUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        team = rename_team(
            actor=request.user, team_id=team_id, **serializer.validated_data
        )
        return Response(TeamSerializer(team).data)


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
            raise NotFound("Solicitações da equipe não encontradas.")

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


class TeamMemberNotesView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            permission_classes = [IsAuthenticated, IsStudent]
        elif self.request.method == "GET":
            permission_classes = [IsAuthenticated, IsTeacher | IsAdmin]
        else:
            permission_classes = [IsAuthenticated]

        return [permission() for permission in permission_classes]

    def post(self, request, team_id):

        serializer = MemberNoteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            note = add_member_note(
                actor=request.user,
                team_id=team_id,
                **serializer.validated_data,
            )
        except MemberNoteError as error:
            return Response(
                {
                    "error": {
                        "code": error.code,
                        "message": str(error),
                        "details": None,
                    }
                },
                status=error.http_status,
            )

        return Response(
            {
                "id": note.pk,
                "created_at": note.created_at,
            },
            status=status.HTTP_201_CREATED,
        )

    def get(self, request, team_id):
        team = Team.objects.filter(pk=team_id).first()

        if team is None:
            return Response(
                {
                    "error": {
                        "code": "not_found",
                        "message": "Equipe não encontrada.",
                        "details": None,
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if request.user.role == UserRole.TEACHER:
            has_course_access = Project.objects.filter(
                team=team,
                challenge__course__teacher_links__teacher__user=request.user,
                challenge__course__teacher_links__active=True,
            ).exists()

            if not has_course_access:
                return Response(
                    {
                        "error": {
                            "code": "permission_denied",
                            "message": (
                                "Você não possui vínculo ativo com o curso "
                                "do desafio desta equipe."
                            ),
                            "details": None,
                        }
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        notes = (
            MemberNote.objects.filter(member__team=team)
            .select_related(
                "member__student__user",
                "author__user",
            )
            .order_by("created_at", "pk")
        )

        return Response(
            MemberNoteSerializer(notes, many=True).data,
            status=status.HTTP_200_OK,
        )


class AdminTeamListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        query_serializer = AdminTeamListQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        filters = query_serializer.validated_data

        teams = (
            Team.objects.all()
            .select_related("edition", "project")
            .annotate(
                member_count=Count(
                    "members",
                    filter=Q(members__active=True),
                    distinct=True,
                )
            )
            .order_by("name")
        )

        edition_id = filters.get("edition_id")
        if edition_id is not None:
            teams = teams.filter(edition_id=edition_id)

        team_status = filters.get("status")
        if team_status:
            teams = teams.filter(status=team_status)

        search = filters.get("search")
        if search:
            teams = teams.filter(
                Q(name__icontains=search)
                | Q(code__icontains=search)
                | Q(project__title__icontains=search)
            )

        paginator = DefaultPagination()
        page = paginator.paginate_queryset(teams, request, view=self)

        serializer = AdminTeamListItemSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)


class AdminTeamDisqualifyView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, team_id):
        serializer = DisqualifyTeamSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        team = disqualify_team(
            actor=request.user,
            team_id=team_id,
            reason=serializer.validated_data["reason"],
        )

        team = (
            Team.objects.filter(pk=team.pk)
            .select_related("edition", "disqualified_by")
            .prefetch_related(
                "members__student__user",
                "members__student__course",
            )
            .get()
        )

        return Response(
            TeamSerializer(team).data,
            status=status.HTTP_200_OK,
        )


class InvitableStudentsView(APIView):
    """Alunos que o líder pode convidar, para o popup de convite (#232)."""

    permission_classes = [IsAuthenticated, IsStudent]

    def get(self, request, team_id):
        team = Team.objects.select_related("edition").filter(pk=team_id).first()
        if team is None:
            raise NotFound("Equipe não encontrada.")
        ensure_actor_is_team_leader(team, request.user)
        query = InvitableStudentQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        students = list_invitable_students(
            team=team, search=query.validated_data["search"]
        )
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(students, request, view=self)
        return paginator.get_paginated_response(
            InvitableStudentSerializer(page, many=True).data
        )
