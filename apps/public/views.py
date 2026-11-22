from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.editions.models import Edition
from apps.public.selectors import (
    get_current_edition,
    list_closed_editions,
    list_edition_winners,
)
from apps.public.serializers import (
    PublicEditionListItemSerializer,
    PublicEditionSerializer,
    WinnerSerializer,
)


class CurrentEditionView(APIView):
    """GET /api/public/editions/current: edição vigente (RF44)."""

    permission_classes = []

    def get(self, request):
        edition = get_current_edition()
        if edition is None:
            raise Http404("Nenhuma edição vigente no momento.")
        return Response(PublicEditionSerializer(edition).data)


class ClosedEditionsListView(APIView):
    """GET /api/public/editions: edições encerradas (RF35, RF46)."""

    permission_classes = []

    def get(self, request):
        editions = list_closed_editions()
        return Response(PublicEditionListItemSerializer(editions, many=True).data)


class EditionWinnersListView(APIView):
    """GET /api/public/editions/{edition_id}/winners: pódio da edição (RF35, RF46)."""

    permission_classes = []

    def get(self, request, edition_id):
        edition = get_object_or_404(Edition, pk=edition_id)
        winners = list_edition_winners(edition)
        return Response(WinnerSerializer(winners, many=True).data)
