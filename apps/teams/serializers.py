from rest_framework import serializers

from apps.teams.enums import InvitationStatus
from apps.teams.models import Invitation, Team, TeamMember


class TeamCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)


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
    accept = serializers.BooleanField()
