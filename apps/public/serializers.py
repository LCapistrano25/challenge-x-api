"""Respostas públicas, no formato do contrato (docs/api/openapi.yaml, tag public)."""

from rest_framework import serializers

from apps.projects.selectors import get_phase_status


class EditionSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    year = serializers.IntegerField()
    semester = serializers.IntegerField()
    name = serializers.SerializerMethodField()
    status = serializers.CharField()

    # Nome vazio no banco vira nulo no contrato.
    def get_name(self, edition):
        return edition.name or None


class PublicEditionListItemSerializer(serializers.Serializer):
    edition = EditionSummarySerializer(source="*")
    closed_at = serializers.DateTimeField(allow_null=True)


class StageScheduleSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    order = serializers.IntegerField()
    name = serializers.CharField()
    kind = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    evaluation_ends_at = serializers.DateTimeField(allow_null=True)
    scored = serializers.BooleanField()
    max_score = serializers.DecimalField(
        max_digits=4, decimal_places=2, allow_null=True
    )
    phase_status = serializers.SerializerMethodField()

    def get_phase_status(self, stage):
        return get_phase_status(stage)


class SdgSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    number = serializers.IntegerField()
    title = serializers.CharField()


class PublicSdgSerializer(SdgSummarySerializer):
    description = serializers.SerializerMethodField()
    icon = serializers.SerializerMethodField()

    def get_description(self, sdg):
        return sdg.description or None

    def get_icon(self, sdg):
        return sdg.icon or None


class CourseSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class PublicChallengeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    description = serializers.CharField()
    course = CourseSummarySerializer()
    sdg = SdgSummarySerializer()


class PublicEditionSerializer(serializers.Serializer):
    edition = EditionSummarySerializer(source="*")
    regulation_url = serializers.SerializerMethodField()
    stages = StageScheduleSerializer(many=True)
    sdgs = serializers.SerializerMethodField()
    challenges = PublicChallengeSerializer(many=True)

    def get_regulation_url(self, edition):
        return edition.regulation_url or None

    def get_sdgs(self, edition):
        sdgs = [link.sdg for link in edition.sdg_links.all()]
        return PublicSdgSerializer(sorted(sdgs, key=lambda s: s.number), many=True).data


class CategoryRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class MemberNameSerializer(serializers.Serializer):
    name = serializers.CharField(source="student.user.name")


class PublicProjectSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    edition = EditionSummarySerializer()
    title = serializers.CharField()
    summary = serializers.CharField()
    course = CourseSummarySerializer(source="challenge.course")
    sdg = SdgSummarySerializer(source="challenge.sdg")
    category = CategoryRefSerializer()
    members = MemberNameSerializer(source="team.active_members", many=True)


class WinnerSerializer(serializers.Serializer):
    award = serializers.IntegerField()
    course = CourseSummarySerializer(source="project.challenge.course")
    category = CategoryRefSerializer(source="project.category")
    project = PublicProjectSerializer()
