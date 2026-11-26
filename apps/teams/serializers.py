from rest_framework import serializers

from apps.teams.enums import InvitationStatus, RequestStatus
from apps.teams.models import (
    Invitation,
    JoinRequest,
    LeadershipRequest,
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


class TeamSerializer(serializers.ModelSerializer):
    edition_id = serializers.IntegerField(read_only=True)
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


class InvitationCreateSerializer(serializers.Serializer):
    student_id = serializers.IntegerField(min_value=1, required=False)
    email = serializers.EmailField(required=False)

    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown_fields = set(data) - set(self.fields)

            if unknown_fields:
                raise serializers.ValidationError(
                    {field: "Campo não permitido." for field in unknown_fields}
                )

        return super().to_internal_value(data)

    def validate(self, attrs):
        has_student_id = "student_id" in attrs
        has_email = "email" in attrs

        if has_student_id == has_email:
            raise serializers.ValidationError(
                "Informe student_id ou email, nunca os dois."
            )

        return attrs


class TeamCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    invitations = InvitationCreateSerializer(many=True, min_length=1)

    def validate(self, attrs):
        unknown_fields = set(self.initial_data) - set(self.fields)

        if unknown_fields:
            raise serializers.ValidationError(
                {field: "Campo não permitido." for field in unknown_fields}
            )

        return attrs


class InvitationSerializer(serializers.ModelSerializer):
    team = serializers.SerializerMethodField()
    student = serializers.SerializerMethodField()
    invited_email = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = [
            "id",
            "team",
            "student",
            "invited_email",
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

    def get_invited_email(self, obj):
        return None


class InvitationStatusFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=InvitationStatus.choices,
        required=False,
    )


class InvitationResponseSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[
            InvitationStatus.ACCEPTED,
            InvitationStatus.DECLINED,
        ],
    )


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
            "course": {
                "id": obj.student.course_id,
                "name": obj.student.course.name,
            },
        }


class JoinRequestStatusFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=RequestStatus.choices,
        required=False,
    )


class JoinRequestResponseSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[
            RequestStatus.APPROVED,
            RequestStatus.REJECTED,
        ],
    )


class TeamAvailabilitySerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(
        source="active_members_count",
        read_only=True,
    )
    available_slots = serializers.SerializerMethodField()
    courses = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = [
            "id",
            "name",
            "code",
            "member_count",
            "available_slots",
            "courses",
        ]

    def get_available_slots(self, obj):
        return obj.edition.max_members - obj.active_members_count

    def get_courses(self, obj):
        courses = (
            obj.members.filter(active=True)
            .values_list("student__course_id", "student__course__name")
            .distinct()
            .order_by("student__course__name")
        )

        return [
            {"id": course_id, "name": course_name} for course_id, course_name in courses
        ]


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
