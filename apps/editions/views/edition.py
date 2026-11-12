from rest_framework import generics

from apps.accounts.permissions import IsAdmin
from apps.editions.models import Edition
from apps.editions.selectors import list_editions
from apps.editions.serializers import EditionSerializer


class EditionListView(generics.ListAPIView):
    """GET /api/admin/editions: lista curta, array simples (RF47)."""

    permission_classes = [IsAdmin]
    serializer_class = EditionSerializer
    pagination_class = None

    def get_queryset(self):
        return list_editions()


class EditionDetailView(generics.RetrieveAPIView):
    """GET /api/admin/editions/{edition_id}: consulta uma edição (RF47)."""

    permission_classes = [IsAdmin]
    serializer_class = EditionSerializer
    queryset = Edition.objects.all()
    lookup_url_kwarg = "edition_id"
