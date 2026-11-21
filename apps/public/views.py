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


class EditionPublicSerializer(serializers.Serializer):
    """Serializer para expor dados básicos da edição ao público."""

    id = serializers.IntegerField()
    year = serializers.IntegerField()
    semester = serializers.IntegerField()
    name = serializers.CharField()
    regulation_url = serializers.URLField()


class WinnerPublicSerializer(serializers.Serializer):
    """Serializer para expor os resultados dos vencedores."""

    project_id = serializers.IntegerField(source="project.id")
    award = serializers.IntegerField()
    final_score = serializers.DecimalField(max_digits=5, decimal_places=2)


class CurrentEditionView(APIView):
    """GET /api/public/editions/current : Informações gerais da edição vigente"""

    permission_classes = []

    def get(self, request):
        edition = get_current_edition()
        if not edition:
            raise Http404("Nenhuma edição vigente no momento.")
        serializer = EditionPublicSerializer(edition)
        return Response(serializer.data)


class ClosedEditionsListView(APIView):
    """GET /api/public/editions : Listar edições encerradas"""

    permission_classes = []

    def get(self, request):
        editions = list_closed_editions()
        serializer = EditionPublicSerializer(editions, many=True)
        return Response(serializer.data)


class EditionWinnersListView(APIView):
    """GET /api/public/editions/{edition_id}/winners : Galeria de vencedores"""

    permission_classes = []

    def get(self, request, edition_id):
        winners = list_edition_winners(edition_id)
        serializer = WinnerPublicSerializer(winners, many=True)
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
