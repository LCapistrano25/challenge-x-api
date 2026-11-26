import re
from collections.abc import Mapping
from decimal import Decimal

from rest_framework import serializers

from apps.core.models import Sdg
from apps.editions.enums import FieldKind, StageKind
from apps.editions.models import (
    Category,
    Challenge,
    Criterion,
    Edition,
    EditionReviewer,
    Stage,
    StageSubmissionField,
)


class CriterionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Criterion
        fields = [
            "id",
            "edition_id",
            "name",
            "rubric",
            "tiebreak_order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["rubric"] = data["rubric"] or None
        return data


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            "id",
            "edition_id",
            "name",
            "description",
            "active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["description"] = data["description"] or None
        return data


class EvaluatorSummarySerializer(serializers.Serializer):
    user_id = serializers.IntegerField(source="user.pk")
    name = serializers.CharField(source="user.name")
    email = serializers.EmailField(source="user.email")
    institution = serializers.CharField()


class CourseSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class ChallengeSdgSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    number = serializers.IntegerField()
    title = serializers.CharField()


class ChallengeSerializer(serializers.ModelSerializer):
    course = CourseSummarySerializer()
    sdg = ChallengeSdgSummarySerializer()

    class Meta:
        model = Challenge
        fields = [
            "id",
            "edition_id",
            "course",
            "sdg",
            "description",
            "active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class EditionReviewerSerializer(serializers.ModelSerializer):
    evaluator = EvaluatorSummarySerializer(source="reviewer")
    course = CourseSummarySerializer(allow_null=True)

    class Meta:
        model = EditionReviewer
        fields = ["id", "edition_id", "evaluator", "course", "created_at", "updated_at"]


class EditionReviewerCreateSerializer(serializers.Serializer):
    evaluator_id = serializers.IntegerField(min_value=1)
    # Obrigatório no contrato; nulo = todos os cursos da edição.
    course_id = serializers.IntegerField(min_value=1, allow_null=True)


class EditionReviewerUpdateSerializer(serializers.Serializer):
    course_id = serializers.IntegerField(min_value=1, allow_null=True)


class EditionSerializer(serializers.ModelSerializer):
    """Edição como o contrato a expõe: texto vazio sai como null (P-37)."""

    class Meta:
        model = Edition
        fields = [
            "id",
            "year",
            "semester",
            "name",
            "status",
            "regulation_url",
            "min_members",
            "max_members",
            "published_at",
            "closed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for field in ("name", "regulation_url"):
            data[field] = data[field] or None
        return data


class StrictIntegerField(serializers.IntegerField):
    """Inteiro do JSON Schema: recusa texto e booleano; aceita 5.0, que é inteiro."""

    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, int | float):
            self.fail("invalid")
        if isinstance(data, float) and not data.is_integer():
            self.fail("invalid")
        return super().to_internal_value(data)


class StrictCharField(serializers.CharField):
    """Texto do JSON Schema: recusa número e booleano (o DRF os converte)."""

    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail("invalid")
        return super().to_internal_value(data)


class RejectUnknownFieldsMixin:
    """O contrato não aceita campos extras (additionalProperties: false)."""

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError(
                    {field: ["Campo não permitido."] for field in sorted(unknown)}
                )
        return super().to_internal_value(data)


class StrictBooleanField(serializers.BooleanField):
    def to_internal_value(self, data):
        if not isinstance(data, bool):
            self.fail("invalid", input=data)
        return super().to_internal_value(data)


class CriterionWriteSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    name = StrictCharField(max_length=150)
    rubric = StrictCharField(
        required=False, allow_null=True, allow_blank=True, trim_whitespace=False
    )
    tiebreak_order = StrictIntegerField(
        required=False, allow_null=True, min_value=1, max_value=32767
    )

    def validate(self, attrs):
        if self.partial and not attrs:
            raise serializers.ValidationError("Informe ao menos um campo.")
        return attrs


class CategoryWriteSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    name = StrictCharField(max_length=150)
    description = StrictCharField(
        required=False, allow_null=True, allow_blank=True, trim_whitespace=False
    )
    active = StrictBooleanField(required=False)

    def validate(self, attrs):
        if self.partial and not attrs:
            raise serializers.ValidationError("Informe ao menos um campo.")
        return attrs


class ChallengeWriteSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    course_id = StrictIntegerField()
    sdg_id = StrictIntegerField()
    description = StrictCharField()
    active = StrictBooleanField(required=False)

    def validate(self, attrs):
        if self.partial and not attrs:
            raise serializers.ValidationError("Informe ao menos um campo.")
        return attrs


class ChallengeFiltersSerializer(serializers.Serializer):
    course_id = serializers.IntegerField(required=False)
    sdg_id = serializers.IntegerField(required=False)
    active = serializers.BooleanField(required=False)


class EditionSdgSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sdg
        fields = [
            "id",
            "number",
            "title",
            "description",
            "icon",
            "active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class EditionSdgsUpdateSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    sdg_ids = serializers.ListField(child=StrictIntegerField())

    def validate_sdg_ids(self, ids):
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Informe cada ODS apenas uma vez.")
        return ids


class EditionCreateSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    """Entrada do cadastro de edição (EditionCreate): só ano, semestre e nome."""

    year = StrictIntegerField(min_value=2000, max_value=2100)
    semester = StrictIntegerField(min_value=1, max_value=2)
    name = StrictCharField(
        max_length=100,
        required=False,
        allow_null=True,
        allow_blank=True,
        trim_whitespace=False,
    )


class EditionPublishSerializer(serializers.Serializer):
    notice_file = serializers.FileField()

    def validate_notice_file(self, file):
        header = file.read(5)
        file.seek(max(0, file.size - 1024))
        trailer = file.read().rstrip()
        file.seek(0)
        if header != b"%PDF-" or not trailer.endswith(b"%%EOF"):
            raise serializers.ValidationError("Envie um arquivo PDF.")
        return file


class EditionUpdateSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    """Entrada da atualização parcial (EditionUpdate): nome e limites da equipe.

    Só entram em validated_data os campos enviados: ausente é diferente de null.
    """

    name = StrictCharField(
        max_length=100,
        required=False,
        allow_null=True,
        allow_blank=True,
        trim_whitespace=False,
    )
    min_members = StrictIntegerField(min_value=1, max_value=20, required=False)
    max_members = StrictIntegerField(min_value=1, max_value=20, required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Informe ao menos um campo.")
        return attrs


class StageSubmissionFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = StageSubmissionField
        fields = ["id", "kind", "label", "required", "formats", "max_size_mb"]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["formats"] = data["formats"] or None
        return data


class StageSerializer(serializers.ModelSerializer):
    submission_fields = StageSubmissionFieldSerializer(many=True, read_only=True)

    class Meta:
        model = Stage
        fields = [
            "id",
            "edition_id",
            "order",
            "name",
            "kind",
            "starts_at",
            "ends_at",
            "evaluation_ends_at",
            "scored",
            "max_score",
            "min_evaluations",
            "submission_fields",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class StageDateTimeField(serializers.DateTimeField):
    def to_internal_value(self, data):
        if not isinstance(data, str) or not re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?(?:[Zz]|[+-][0-9]{2}:[0-9]{2})",
            data,
        ):
            self.fail("invalid", format="ISO 8601 com fuso")
        return super().to_internal_value(data.upper())


class StageScoreField(serializers.Field):
    default_error_messages = {
        "invalid": "Informe um decimal em texto, com até duas casas decimais."
    }

    def to_internal_value(self, data):
        if not isinstance(data, str) or not re.fullmatch(
            r"[0-9]{1,3}(?:\.[0-9]{1,2})?", data
        ):
            self.fail("invalid")
        return Decimal(data)


class StageSubmissionFieldWriteSerializer(
    RejectUnknownFieldsMixin, serializers.Serializer
):
    id = StrictIntegerField(required=False)
    kind = serializers.ChoiceField(choices=FieldKind.values)
    label = StrictCharField(
        max_length=150, required=False, allow_blank=True, trim_whitespace=False
    )
    required = StrictBooleanField(required=False)
    formats = StrictCharField(
        max_length=200,
        required=False,
        allow_null=True,
        allow_blank=True,
        trim_whitespace=False,
    )
    max_size_mb = StrictIntegerField(
        min_value=1, max_value=32767, required=False, allow_null=True
    )

    def validate(self, attrs):
        # O partial da etapa não torna kind opcional no objeto aninhado.
        if "kind" not in attrs:
            raise serializers.ValidationError({"kind": "Este campo é obrigatório."})
        return attrs


class StageWriteSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    order = StrictIntegerField(min_value=1, max_value=32767)
    name = StrictCharField(max_length=100)
    kind = serializers.ChoiceField(choices=StageKind.values)
    starts_at = StageDateTimeField()
    ends_at = StageDateTimeField()
    evaluation_ends_at = StageDateTimeField(required=False, allow_null=True)
    scored = StrictBooleanField(required=False)
    max_score = StageScoreField(required=False, allow_null=True)
    min_evaluations = StrictIntegerField(min_value=1, max_value=32767, required=False)
    submission_fields = StageSubmissionFieldWriteSerializer(many=True, required=False)

    def validate(self, attrs):
        if self.partial and not attrs:
            raise serializers.ValidationError("Informe ao menos um campo.")
        return attrs
