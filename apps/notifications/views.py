from rest_framework import serializers, status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications.selectors import list_user_notifications
from apps.notifications.use_cases.read_notification import mark_notification_as_read


class NotificationSerializer(serializers.Serializer):
    """Serializer no formato do contrato (docs/api/openapi.yaml)."""

    id = serializers.UUIDField()
    type = serializers.CharField()
    title = serializers.CharField()
    message = serializers.CharField()
    link = serializers.SerializerMethodField()
    read_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()

    def get_link(self, obj):
        return obj.link or None


class NotificationFilterSerializer(serializers.Serializer):
    unread = serializers.BooleanField(required=False, default=False)


class NotificationListView(ListAPIView):
    """GET /api/notifications: listar minhas notificações."""

    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        filters = NotificationFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        return list_user_notifications(
            user=self.request.user, unread_only=filters.validated_data["unread"]
        )


class NotificationReadView(APIView):
    """POST /api/notifications/{notification_id}/read: marcar como lida."""

    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        notification = mark_notification_as_read(
            actor=request.user,
            notification_id=notification_id,
        )
        return Response(
            NotificationSerializer(notification).data,
            status=status.HTTP_200_OK,
        )
