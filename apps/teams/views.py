from django.db.models import Count, F, Q
from rest_framework import status
from rest_framework.exceptions import NotFound
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
from apps.teams.enums import (
    MemberRole,
    TeamStatus,
)
from apps.teams.exceptions import MemberNoteError
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
    AdminTeamDetailSerializer,
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
from apps.teams.use_cases.create_team import create_team
from apps.teams.use_cases.disqualify_team import disqualify_team
from apps.teams.use_cases.get_student_dashboard import get_student_dashboard
from apps.teams.use_cases.invite_member import invite_member
from apps.teams.use_cases.leave_team import (
    LeaveTeamRejected,
    leave_team,
)
from apps.teams.use_cases.rename_team import rename_team
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
from config.pagination import DefaultPagination


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

    def patch(self, request, team_id):
        serializer = TeamUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        team = rename_team(
            actor=request.user, team_id=team_id, **serializer.validated_data
        )
        # Resposta no schema Team do contrato.
        return Response(AdminTeamDetailSerializer(team).data)


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
            AdminTeamDetailSerializer(team).data,
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
