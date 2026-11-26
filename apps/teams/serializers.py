from rest_framework import serializers

from apps.teams.enums import InvitationStatus, RequestStatus, TeamStatus
from apps.teams.models import (
    Invitation,
    JoinRequest,
    LeadershipRequest,
    MemberNote,
    Team,
    TeamMember,
)


class TeamLeaveSerializer(serializers.Serializer):
    # Confirma a saída que deixa a equipe abaixo do mínimo de integrantes.
    confirm = serializers.BooleanField(default=False)


class TeamMemberSerializer(serializers.ModelSerializer):
    student = serializers.SerializerMethodField()

    class Meta:
        model = TeamMember
        fields = ["id", "student", "role", "joined_at"]

    def get_student(self, obj):
        return {
            "user_id": obj.student.user_id,
            "name": obj.student.user.name,
            "course": {
                "id": obj.student.course_id,
                "name": obj.student.course.name,
            },
        }


class MemberNoteCreateSerializer(serializers.Serializer):
    member_id = serializers.IntegerField(min_value=1)
    text = serializers.CharField(
        min_length=1,
        allow_blank=False,
        trim_whitespace=True,
    )


class MemberNoteSerializer(serializers.ModelSerializer):
    member = serializers.SerializerMethodField()
    author = serializers.SerializerMethodField()

    class Meta:
        model = MemberNote
        fields = ["id", "member", "author", "text", "created_at"]

    def get_member(self, obj):
        return {
            "user_id": obj.member.student.user_id,
            "name": obj.member.student.user.name,
        }

    def get_author(self, obj):
        return {
            "user_id": obj.author.user_id,
            "name": obj.author.user.name,
        }


class AdminTeamDetailSerializer(serializers.ModelSerializer):
    edition_id = serializers.IntegerField(read_only=True)
    disqualified_by = serializers.IntegerField(
        source="disqualified_by_id",
        read_only=True,
        allow_null=True,
    )
    members = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = [
            "id",
            "edition_id",
            "name",
            "code",
            "status",
            "situation",
            "disqualification_reason",
            "disqualified_at",
            "disqualified_by",
            "formation_extended_until",
            "members",
            "created_at",
            "updated_at",
        ]

    def get_members(self, obj):
        members = obj.members.filter(active=True).select_related(
            "student__user",
            "student__course",
        )
        return TeamMemberSerializer(members, many=True).data


class TeamSerializer(serializers.ModelSerializer):
    edition_id = serializers.IntegerField(read_only=True)
    members = serializers.SerializerMethodField()
    qualification = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = [
            "id",
            "edition_id",
            "name",
            "code",
            "status",
            "qualification",
            "disqualification_reason",
            "formation_extended_until",
            "members",
            "created_at",
            "updated_at",
        ]

    def get_members(self, obj):
        members = obj.members.filter(active=True).select_related(
            "student__user",
            "student__course",
        )
        return TeamMemberSerializer(members, many=True).data

    def get_qualification(self, obj):
        return None


class InvitationCreateSerializer(serializers.Serializer):
    student_id = serializers.IntegerField(required=False)
    email = serializers.EmailField(required=False)

    def validate(self, attrs):
        student_id = attrs.get("student_id")
        email = attrs.get("email")

        if bool(student_id) == bool(email):
            raise serializers.ValidationError(
                "Informe student_id ou email, mas não ambos."
            )

        return attrs


class TeamCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    # A quantidade exigida depende da edição; o caso de uso confere e explica.
    invitations = InvitationCreateSerializer(many=True, required=False)


class InvitationSerializer(serializers.ModelSerializer):
    team = serializers.SerializerMethodField()
    student = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = [
            "id",
            "team",
            "student",
            "status",
            "created_at",
            "responded_at",
        ]

    def get_team(self, obj):
        return {
            "id": obj.team.id,
            "name": obj.team.name,
            "code": obj.team.code,
        }

    def get_student(self, obj):
        return {
            "user_id": obj.student.user_id,
            "name": obj.student.user.name,
        }


class InvitationStatusFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=InvitationStatus.choices,
        required=False,
    )


class InvitationResponseSerializer(serializers.Serializer):
    accept = serializers.BooleanField()


class JoinRequestSerializer(serializers.ModelSerializer):
    team = serializers.SerializerMethodField()
    student = serializers.SerializerMethodField()

    class Meta:
        model = JoinRequest
        fields = [
            "id",
            "team",
            "student",
            "status",
            "created_at",
            "responded_at",
        ]

    def get_team(self, obj):
        return {
            "id": obj.team.id,
            "name": obj.team.name,
            "code": obj.team.code,
        }

    def get_student(self, obj):
        return {
            "user_id": obj.student.user_id,
            "name": obj.student.user.name,
        }


class JoinRequestStatusFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=RequestStatus.choices,
        required=False,
    )


class JoinRequestResponseSerializer(serializers.Serializer):
    approve = serializers.BooleanField()


class TeamAvailabilitySerializer(serializers.ModelSerializer):
    edition_id = serializers.IntegerField(read_only=True)
    members_count = serializers.SerializerMethodField()
    available_vacancies = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = [
            "id",
            "edition_id",
            "name",
            "code",
            "members_count",
            "available_vacancies",
        ]

    def get_members_count(self, obj):
        return obj.active_members_count

    def get_available_vacancies(self, obj):
        return obj.edition.max_members - obj.active_members_count


class LeadershipTransferSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()


class LeadershipRequestCreateSerializer(serializers.Serializer):
    justification = serializers.CharField()


class LeadershipRequestDecisionSerializer(serializers.Serializer):
    approve = serializers.BooleanField()
    justification = serializers.CharField()


class LeadershipRequestSerializer(serializers.ModelSerializer):
    team = serializers.SerializerMethodField()
    requester = serializers.SerializerMethodField()
    teacher = serializers.SerializerMethodField()

    class Meta:
        model = LeadershipRequest
        fields = [
            "id",
            "team",
            "requester",
            "justification",
            "status",
            "teacher",
            "decision_justification",
            "created_at",
            "decided_at",
        ]

    def get_team(self, obj):
        return {
            "id": obj.team.id,
            "name": obj.team.name,
            "code": obj.team.code,
        }

    def get_requester(self, obj):
        return {
            "user_id": obj.requester.user_id,
            "name": obj.requester.user.name,
        }

    def get_teacher(self, obj):
        if obj.teacher is None:
            return None

        return {
            "user_id": obj.teacher.user_id,
            "name": obj.teacher.user.name,
        }


class DisqualifyTeamSerializer(serializers.Serializer):
    reason = serializers.CharField(
        min_length=1,
        allow_blank=False,
        trim_whitespace=True,
    )


class AdminTeamListQuerySerializer(serializers.Serializer):
    edition_id = serializers.IntegerField(required=False, min_value=1)
    status = serializers.ChoiceField(
        choices=TeamStatus.choices,
        required=False,
    )
    search = serializers.CharField(required=False, allow_blank=True)


class ProjectRefSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)


class AdminTeamListItemSerializer(serializers.ModelSerializer):
    edition_id = serializers.IntegerField(read_only=True)
    member_count = serializers.IntegerField(read_only=True)
    project = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = [
            "id",
            "edition_id",
            "name",
            "code",
            "status",
            "situation",
            "member_count",
            "project",
        ]

    def get_project(self, obj):
        project = getattr(obj, "project", None)

        if project is None:
            return None

        return ProjectRefSerializer(project).data


class InvitableStudentQuerySerializer(serializers.Serializer):
    search = serializers.CharField(min_length=3, trim_whitespace=True)


class InvitableStudentSerializer(serializers.Serializer):
    """Aluno para o popup de convite: sem e-mail, matrícula ou período (LGPD)."""

    id = serializers.IntegerField(source="pk")
    name = serializers.CharField(source="user.name")
    course = serializers.SerializerMethodField()

    def get_course(self, obj):
        return {"id": obj.course_id, "name": obj.course.name}
