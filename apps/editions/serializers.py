from collections.abc import Mapping

from rest_framework import serializers

from apps.editions.models import Edition


class EditionSerializer(serializers.ModelSerializer):
    """Edição como o contrato a expõe: texto vazio sai como null (P-37)."""

    notice_url = serializers.URLField(source="regulation_url")

    class Meta:
        model = Edition
        fields = [
            "id",
            "year",
            "semester",
            "name",
            "status",
            "notice_url",
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
        for field in ("name", "notice_url"):
            data[field] = data[field] or None
        return data


class EditionCreateSerializer(serializers.Serializer):
    """Entrada do cadastro de edição (EditionCreate): só ano, semestre e nome.

    O contrato não aceita campos extras (additionalProperties: false).
    """

    # O model guarda o ano em PositiveSmallIntegerField: o teto evita erro do banco.
    year = serializers.IntegerField(min_value=1, max_value=32767)
    semester = serializers.ChoiceField(choices=[1, 2])
    name = serializers.CharField(
        max_length=100, required=False, allow_null=True, allow_blank=True
    )

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError(
                    {field: ["Campo não permitido."] for field in sorted(unknown)}
                )
        return super().to_internal_value(data)
