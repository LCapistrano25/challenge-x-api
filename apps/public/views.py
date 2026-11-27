from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.editions.models import Edition
from apps.public.selectors import (
    get_current_edition,
    get_public_project,
    list_closed_editions,
    list_edition_winners,
    list_public_projects,
)
from apps.public.serializers import (
    PublicEditionListItemSerializer,
    PublicEditionSerializer,
    PublicProjectSerializer,
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
    """GET /api/public/editions/{edition_id}/winners : Galeria de vencedores (RF47)."""

    permission_classes = []

    def get(self, request, edition_id):
        edition = get_object_or_404(Edition, id=edition_id)
        winners = list_edition_winners(edition)
        return Response(WinnerSerializer(winners, many=True).data)


class PublicProjectFilterSerializer(serializers.Serializer):
    edition_id = serializers.IntegerField(required=False)
    course_id = serializers.IntegerField(required=False)
    sdg_id = serializers.IntegerField(required=False)
    category_id = serializers.IntegerField(required=False)
    search = serializers.CharField(required=False, allow_blank=True)


class PublicProjectListView(ListAPIView):
    """GET /api/public/projects : Vitrine e acervo de projetos (público) - RF34."""

    permission_classes = []
    serializer_class = PublicProjectSerializer

    def get_queryset(self):
        filters = PublicProjectFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        return list_public_projects(**filters.validated_data)


class PublicProjectDetailView(APIView):
    """GET /api/public/projects/{project_id}: Detalhe público do projeto (RF45)."""

    permission_classes = []

    def get(self, request, project_id):
        project = get_public_project(project_id)
        if not project:
            raise Http404("Projeto não encontrado ou não disponível para o público.")
        return Response(PublicProjectSerializer(project).data)
