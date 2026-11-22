from django.http import Http404
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

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
    """GET /api/public/editions/{edition_id}/winners : Galeria de vencedores"""

    permission_classes = []

    def get(self, request, edition_id):
        winners = list_edition_winners(edition_id)
        serializer = WinnerSerializer(winners, many=True)
        return Response(serializer.data)


class ProjectPublicSerializer(serializers.Serializer):
    """Serializer para a vitrine de projetos."""

    id = serializers.IntegerField()
    title = serializers.CharField()
    summary = serializers.CharField()
    status = serializers.CharField()


class ProjectDetailPublicSerializer(ProjectPublicSerializer):
    """Serializer para a página de detalhe do projeto."""

    objective = serializers.CharField()
    # Podemos adicionar mais campos futuramente (equipa, links, etc.)


class PublicProjectListView(APIView):
    """GET /api/public/projects : Vitrine e acervo de projetos (público)"""

    permission_classes = []

    def get(self, request):
        projects = list_public_projects()
        serializer = ProjectPublicSerializer(projects, many=True)
        return Response(serializer.data)


class PublicProjectDetailView(APIView):
    """GET /api/public/projects/{project_id} : Detalhe público do projeto (público)"""

    permission_classes = []

    def get(self, request, project_id):
        project = get_public_project(project_id)
        if not project:
            raise Http404("Projeto não encontrado ou não disponível para o público.")
        serializer = ProjectDetailPublicSerializer(project)
        return Response(serializer.data)
