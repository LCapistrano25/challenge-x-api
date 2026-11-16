from rest_framework import serializers

from apps.editions.models import Challenge
from apps.projects.selectors import get_team_courses


class ChallengeSelectionSerializer(serializers.Serializer):
    # Desafio inexistente sai como erro de validação; a elegibilidade é do caso de uso.
    challenge_id = serializers.PrimaryKeyRelatedField(
        queryset=Challenge.objects.all(), source="challenge"
    )


class ProjectDetailsSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    summary = serializers.CharField()
    objective = serializers.CharField(required=False, allow_blank=True, default="")


class CourseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class SdgSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    number = serializers.IntegerField()
    title = serializers.CharField()


class ChallengeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    description = serializers.CharField()
    course = CourseSerializer()
    sdg = SdgSerializer()


class CategoryRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class CategoryOptionSerializer(CategoryRefSerializer):
    description = serializers.CharField(allow_blank=True)


class ProjectOptionsSerializer(serializers.Serializer):
    challenges = ChallengeSerializer(many=True)
    categories = CategoryOptionSerializer(many=True)


class ProjectSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    team_id = serializers.IntegerField()
    edition_id = serializers.IntegerField()
    challenge = ChallengeSerializer(allow_null=True)
    category = CategoryRefSerializer(allow_null=True)
    title = serializers.CharField()
    summary = serializers.CharField()
    objective = serializers.CharField()
    status = serializers.CharField()
    courses = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    def get_courses(self, project):
        return CourseSerializer(get_team_courses(project.team), many=True).data
