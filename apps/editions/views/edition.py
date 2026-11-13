from rest_framework import generics, status
from rest_framework.response import Response

from apps.accounts.permissions import IsAdmin
from apps.editions.models import Edition
from apps.editions.selectors import list_editions
from apps.editions.serializers import EditionCreateSerializer, EditionSerializer
from apps.editions.use_cases.create_edition import create_edition


class EditionListView(generics.ListAPIView):
    """GET lista as edições (array simples); POST cadastra uma edição (RF47)."""

    permission_classes = [IsAdmin]
    serializer_class = EditionSerializer
    pagination_class = None

    def get_queryset(self):
        return list_editions()

    def post(self, request):
        serializer = EditionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        edition = create_edition(
            actor=request.user,
            year=data["year"],
            semester=data["semester"],
            name=data.get("name") or "",
        )
        return Response(EditionSerializer(edition).data, status=status.HTTP_201_CREATED)


class EditionDetailView(generics.RetrieveAPIView):
    """GET /api/admin/editions/{edition_id}: consulta uma edição (RF47)."""

    permission_classes = [IsAdmin]
    serializer_class = EditionSerializer
    queryset = Edition.objects.all()
    lookup_url_kwarg = "edition_id"
