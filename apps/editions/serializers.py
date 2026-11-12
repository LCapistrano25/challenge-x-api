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
