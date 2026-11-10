from rest_framework import serializers

from apps.teams.models import Team, TeamMember


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
    