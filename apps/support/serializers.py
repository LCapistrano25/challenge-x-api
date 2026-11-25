from rest_framework import serializers

from apps.accounts.models import User
from apps.support.enums import SupportTicketPriority, SupportTicketStatus
from apps.support.models import SupportTicket


class SupportTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = [
            "id",
            "title",
            "description",
            "status",
            "priority",
            "support_response",
            "created_at",
            "updated_at",
            "resolved_at",
        ]
        read_only_fields = fields


class SupportTicketRequesterSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="id", read_only=True)

    class Meta:
        model = User
        fields = ["user_id", "name", "email", "role"]
        read_only_fields = fields


class SupportTicketAssigneeSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="id", read_only=True)

    class Meta:
        model = User
        fields = ["user_id", "name"]
        read_only_fields = fields


class SupportTicketAdminSerializer(SupportTicketSerializer):
    requester = SupportTicketRequesterSerializer(read_only=True)
    assigned_to = SupportTicketAssigneeSerializer(read_only=True, allow_null=True)

    class Meta(SupportTicketSerializer.Meta):
        fields = [*SupportTicketSerializer.Meta.fields, "requester", "assigned_to"]
        read_only_fields = fields


class SupportTicketCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=150, min_length=1)
    description = serializers.CharField(min_length=1)

    def validate(self, attrs):
        extra = set(self.initial_data.keys()) - set(self.fields.keys())
        if extra:
            raise serializers.ValidationError(
                {field: "Campo não permitido." for field in sorted(extra)}
            )
        return attrs


class SupportTicketAdminUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=SupportTicketStatus.choices, required=False
    )
    priority = serializers.ChoiceField(
        choices=SupportTicketPriority.choices, required=False
    )
    support_response = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    assigned_to = serializers.IntegerField(min_value=1, required=False, allow_null=True)

    def validate(self, attrs):
        extra = set(self.initial_data.keys()) - set(self.fields.keys())
        if extra:
            raise serializers.ValidationError(
                {field: "Campo não permitido." for field in sorted(extra)}
            )
        if not attrs:
            raise serializers.ValidationError(
                "Informe ao menos um campo para atualizar."
            )
        return attrs
