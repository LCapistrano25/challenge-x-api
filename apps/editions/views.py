from urllib.parse import urlsplit

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdmin
from apps.editions.enums import EditionStatus
from apps.editions.models import Edition, EditionReviewer
from apps.editions.regulation_files import open_regulation
from apps.editions.selectors import list_edition_reviewers, list_editions
from apps.editions.serializers import (
    EditionCreateSerializer,
    EditionPublishSerializer,
    EditionReviewerCreateSerializer,
    EditionReviewerSerializer,
    EditionReviewerUpdateSerializer,
    EditionSerializer,
    EditionUpdateSerializer,
)
from apps.editions.use_cases.create_edition import create_edition
from apps.editions.use_cases.link_reviewer_to_edition import link_reviewer_to_edition
from apps.editions.use_cases.publish_regulation import publish_regulation
from apps.editions.use_cases.update_edition import update_edition
from apps.editions.use_cases.update_reviewer_scope import update_reviewer_scope


class EditionReviewView(APIView):
    """Avaliadores externos da edição: listar e vincular (RF11)."""

    permission_classes = [IsAdmin]

    def get(self, request, edition_id):
        get_object_or_404(Edition, pk=edition_id)
        reviewers = list_edition_reviewers(edition_id)
        return Response(EditionReviewerSerializer(reviewers, many=True).data)

    def post(self, request, edition_id):
        edition = get_object_or_404(Edition, pk=edition_id)
        serializer = EditionReviewerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        link = link_reviewer_to_edition(
            actor=request.user, edition=edition, **serializer.validated_data
        )
        return Response(
            EditionReviewerSerializer(link).data, status=status.HTTP_201_CREATED
        )


class EditionReviewDetailView(APIView):
    """Abrangência de um avaliador na edição (RF11)."""

    permission_classes = [IsAdmin]

    def patch(self, request, edition_id, evaluator_id):
        link = get_object_or_404(
            EditionReviewer, edition_id=edition_id, reviewer_id=evaluator_id
        )
        serializer = EditionReviewerUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        link = update_reviewer_scope(
            actor=request.user, link=link, **serializer.validated_data
        )
        return Response(EditionReviewerSerializer(link).data)


class EditionListView(generics.ListAPIView):
    """GET lista as edições (array simples); POST cadastra uma edição (RF47)."""

    permission_classes = [IsAdmin]
    # O contrato só declara application/json nas entradas.
    parser_classes = [JSONParser]
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
    """GET consulta e PATCH atualiza nome e limites de uma edição (RF47, RF48)."""

    permission_classes = [IsAdmin]
    # O contrato só declara application/json nas entradas.
    parser_classes = [JSONParser]
    serializer_class = EditionSerializer
    queryset = Edition.objects.all()
    lookup_url_kwarg = "edition_id"

    def patch(self, request, *args, **kwargs):
        edition = self.get_object()
        serializer = EditionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        edition = update_edition(
            actor=request.user, edition=edition, **serializer.validated_data
        )
        return Response(EditionSerializer(edition).data)


class EditionPublishView(APIView):
    permission_classes = [IsAdmin]
    parser_classes = [MultiPartParser]

    def post(self, request, edition_id):
        edition = get_object_or_404(Edition, pk=edition_id)
        serializer = EditionPublishSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        edition = publish_regulation(
            actor=request.user,
            edition=edition,
            public_origin=request.build_absolute_uri("/").rstrip("/"),
            **serializer.validated_data,
        )
        return Response(EditionSerializer(edition).data)


class EditionRegulationView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, edition_id, token):
        edition = get_object_or_404(
            Edition,
            pk=edition_id,
            status__in=[EditionStatus.PUBLISHED, EditionStatus.CLOSED],
        )
        if urlsplit(edition.regulation_url).path != request.path:
            raise Http404
        try:
            file = open_regulation(f"{edition.pk}/{token.hex}.pdf")
        except FileNotFoundError as error:
            raise Http404 from error
        response = FileResponse(
            file,
            as_attachment=True,
            filename="edital.pdf",
            content_type="application/pdf",
        )
        response["X-Content-Type-Options"] = "nosniff"
        return response
