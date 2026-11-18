import json

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
    link = serializers.URLField(max_length=1000, required=False)
    # Posição do arquivo em files[] (multipart, P-43).
    file_index = serializers.IntegerField(min_value=0, required=False)

    def validate(self, attrs):
        if ("link" in attrs) == ("file_index" in attrs):
            raise serializers.ValidationError(
                "Informe o link ou o file_index do item, apenas um dos dois."
            )
        return attrs


class DeliverableSubmissionSerializer(serializers.Serializer):
    """Corpo do envio: JSON só com links, ou multipart com `items` em string JSON.

    Os arquivos vêm do contexto (`context["files"]`, a lista de `files[]`); cada
    `file_index` é trocado pelo arquivo, e o resultado já tem o formato do caso de
    uso: {"field", "link"} ou {"field", "file"}.
    """

    items = DeliverableItemWriteSerializer(many=True, allow_empty=False)
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def to_internal_value(self, data):
        raw_items = data.get("items") if hasattr(data, "get") else None
        if isinstance(raw_items, str):
            try:
                parsed = json.loads(raw_items)
            except ValueError:
                raise serializers.ValidationError(
                    {"items": ["O campo items não é um JSON válido."]}
                ) from None
            # Dicionário comum: o QueryDict do multipart confunde o serializer aninhado.
            data = {"items": parsed}
            if "notes" in self.initial_data:
                data["notes"] = self.initial_data["notes"]
        return super().to_internal_value(data)

    def validate(self, attrs):
        files = self.context.get("files", [])
        used = set()
        items = []
        for raw in attrs["items"]:
            if "file_index" not in raw:
                items.append({"field": raw["field"], "link": raw["link"]})
                continue
            index = raw["file_index"]
            if index >= len(files):
                raise serializers.ValidationError(
                    {"items": f"Não há arquivo na posição {index} de files[]."}
                )
            if index in used:
                raise serializers.ValidationError(
                    {"items": "O mesmo arquivo foi usado em mais de um item."}
                )
            used.add(index)
            items.append({"field": raw["field"], "file": files[index]})
        if len(used) != len(files):
            raise serializers.ValidationError(
                {"files": "Há arquivo enviado sem item correspondente."}
            )
        attrs["items"] = items
        return attrs


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
