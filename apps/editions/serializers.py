from collections.abc import Mapping

from rest_framework import serializers

from apps.core.models import Sdg
from apps.editions.models import Edition, EditionReviewer


class EvaluatorSummarySerializer(serializers.Serializer):
    user_id = serializers.IntegerField(source="user.pk")
    name = serializers.CharField(source="user.name")
    email = serializers.EmailField(source="user.email")
    institution = serializers.CharField()


class CourseSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


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
