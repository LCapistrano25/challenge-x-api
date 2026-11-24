from collections.abc import Mapping

from rest_framework import serializers

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


class EditionCreateSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    """Entrada do cadastro de edição (EditionCreate): só ano, semestre e nome."""

    # O model guarda o ano em PositiveSmallIntegerField: o teto evita erro do banco.
    year = serializers.IntegerField(min_value=1, max_value=32767)
    semester = serializers.ChoiceField(choices=[1, 2])
    name = serializers.CharField(
        max_length=100, required=False, allow_null=True, allow_blank=True
    )


class EditionUpdateSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    """Entrada da atualização parcial (EditionUpdate): nome e limites da equipe.

    Só entram em validated_data os campos enviados: ausente é diferente de null.
    """

    name = serializers.CharField(
        max_length=100, required=False, allow_null=True, allow_blank=True
    )
    # Os limites são PositiveSmallIntegerField no model: o teto evita erro do banco.
    min_members = serializers.IntegerField(min_value=1, max_value=32767, required=False)
    max_members = serializers.IntegerField(min_value=1, max_value=32767, required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Informe ao menos um campo.")
        return attrs
