from rest_framework import serializers

from apps.editions.models import Category, Challenge, StageSubmissionField
from apps.projects.models import SubmissionVersion
from apps.projects.selectors import (
    get_delivery_status,
    get_official_version,
    get_phase_status,
    get_team_courses,
)


class ChallengeSelectionSerializer(serializers.Serializer):
    # Desafio inexistente sai como erro de validação; a elegibilidade é do caso de uso.
    challenge_id = serializers.PrimaryKeyRelatedField(
        queryset=Challenge.objects.all(), source="challenge"
    )


class CategorySelectionSerializer(serializers.Serializer):
    # Categoria inexistente sai como erro de validação; o resto é do caso de uso.
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source="category"
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


class DeliverableItemWriteSerializer(serializers.Serializer):
    # Campo inexistente sai como erro de validação; o resto é da regra do caso de uso.
    field_id = serializers.PrimaryKeyRelatedField(
        queryset=StageSubmissionField.objects.all(), source="field"
    )
    link = serializers.URLField(max_length=1000)


class DeliverableSubmissionSerializer(serializers.Serializer):
    items = DeliverableItemWriteSerializer(many=True, allow_empty=False)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class UserSummarySerializer(serializers.Serializer):
    user_id = serializers.IntegerField(source="pk")
    name = serializers.CharField()


class DeliverableItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    field_id = serializers.IntegerField(allow_null=True)
    type = serializers.CharField(source="kind")
    link = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()
    size_bytes = serializers.IntegerField(allow_null=True)

    # Campo vazio no banco vira nulo no contrato.
    def get_link(self, item):
        return item.link or None

    def get_file_url(self, item):
        return item.file_url or None

    def get_file_name(self, item):
        return item.file_name or None


class ReceiptSerializer(serializers.Serializer):
    verification_code = serializers.CharField()
    file_url = serializers.SerializerMethodField()
    generated_at = serializers.DateTimeField()

    def get_file_url(self, receipt):
        return receipt.file_url or None


class TeamRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    code = serializers.CharField()


class ProjectRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()


class StageRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    position = serializers.IntegerField(source="order")


class ReceiptDetailSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    version_id = serializers.IntegerField()
    version_number = serializers.IntegerField(source="version.number")
    verification_code = serializers.CharField()
    file_url = serializers.SerializerMethodField()
    generated_at = serializers.DateTimeField()
    team = TeamRefSerializer(source="version.submission.project.team")
    project = ProjectRefSerializer(source="version.submission.project")
    stage = StageRefSerializer(source="version.submission.stage")
    submitted_at = serializers.DateTimeField(source="version.submitted_at")

    # Campo vazio no banco vira nulo no contrato; o PDF ainda não é gerado.
    def get_file_url(self, receipt):
        return receipt.file_url or None


class DeliverableVersionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    version_number = serializers.IntegerField(source="number")
    submitted_by = UserSummarySerializer(source="submitted_by.user")
    submitted_at = serializers.DateTimeField()
    notes = serializers.SerializerMethodField()
    items = DeliverableItemSerializer(many=True)
    receipt = ReceiptSerializer(allow_null=True)

    def get_notes(self, version):
        return version.notes or None


class DeliverableFieldSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    type = serializers.CharField(source="kind")
    label = serializers.CharField()
    required = serializers.BooleanField()
    formats = serializers.SerializerMethodField()
    max_size_mb = serializers.IntegerField(allow_null=True)

    def get_formats(self, field):
        return field.formats or None


class StageScheduleSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    position = serializers.IntegerField(source="order")
    name = serializers.CharField()
    type = serializers.CharField(source="kind")
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    scored = serializers.BooleanField()
    points_value = serializers.DecimalField(
        source="max_score", max_digits=4, decimal_places=2, allow_null=True
    )
    phase_status = serializers.SerializerMethodField()

    def get_phase_status(self, stage):
        return get_phase_status(stage)


class StageDeliverableSerializer(serializers.Serializer):
    """Entrega de uma etapa; o contexto traz o projeto (`self.context["project"]`)."""

    stage = StageScheduleSerializer(source="*")
    fields = DeliverableFieldSerializer(source="submission_fields", many=True)
    status = serializers.SerializerMethodField()
    official_version_id = serializers.SerializerMethodField()
    versions = serializers.SerializerMethodField()

    def get_status(self, stage):
        return get_delivery_status(self.context["project"], stage)

    def get_official_version_id(self, stage):
        version = get_official_version(self.context["project"], stage)
        return version.pk if version else None

    def get_versions(self, stage):
        versions = (
            SubmissionVersion.objects.filter(
                submission__project=self.context["project"], submission__stage=stage
            )
            .select_related("submitted_by__user", "receipt")
            .prefetch_related("items")
            .order_by("-number")
        )
        return DeliverableVersionSerializer(versions, many=True).data
