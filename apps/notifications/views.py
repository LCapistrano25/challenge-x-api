from rest_framework import serializers, status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications.selectors import list_user_notifications
from apps.notifications.use_cases.read_notification import mark_notification_as_read


class NotificationSerializer(serializers.Serializer):
    """Serializer baseado no contrato do OpenAPI."""

    id = serializers.IntegerField()
    notification_type = (
        serializers.CharField()
    )  # Ajuste para o nome real do campo no seu model
    title = serializers.CharField()
    message = serializers.CharField()
    link = serializers.CharField(allow_null=True)
    read = serializers.BooleanField()
    created_at = serializers.DateTimeField()


class NotificationListView(ListAPIView):
    """GET /api/notifications : Listar minhas notificações"""

    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        # O ListAPIView cuida da paginação automaticamente (P-38 da issue #90)
        return list_user_notifications(user=self.request.user)


class NotificationReadView(APIView):
    """POST /api/notifications/{notification_id}/read : Marcar notificação como lida"""

    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        # A view apenas repassa a ação para o caso de uso
        notification = mark_notification_as_read(
            actor=request.user, notification_id=notification_id
        )

        # Como é uma ação, geralmente retornamos os dados atualizados ou
        #  200 OK (verifique o contrato)
        return Response(
            NotificationSerializer(notification).data, status=status.HTTP_200_OK
        )  # Create your views here.
