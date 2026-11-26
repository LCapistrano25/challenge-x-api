from urllib.parse import urlsplit

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdmin
from apps.editions.enums import EditionStatus
from apps.editions.models import (
    Category,
    Challenge,
    Criterion,
    Edition,
    EditionReviewer,
)
from apps.editions.regulation_files import open_regulation
from apps.editions.selectors import (
    list_edition_categories,
    list_edition_challenges,
    list_edition_criteria,
    list_edition_reviewers,
    list_edition_sdgs,
    list_editions,
)
from apps.editions.serializers import (
    CategorySerializer,
    CategoryWriteSerializer,
    ChallengeFiltersSerializer,
    ChallengeSerializer,
    ChallengeWriteSerializer,
    CriterionSerializer,
    CriterionWriteSerializer,
    EditionCreateSerializer,
    EditionPublishSerializer,
    EditionReviewerCreateSerializer,
    EditionReviewerSerializer,
    EditionReviewerUpdateSerializer,
    EditionSdgSerializer,
    EditionSdgsUpdateSerializer,
    EditionSerializer,
    EditionUpdateSerializer,
)
from apps.editions.use_cases.create_category import create_category
from apps.editions.use_cases.create_challenge import create_challenge
from apps.editions.use_cases.create_criterion import create_criterion
from apps.editions.use_cases.create_edition import create_edition
from apps.editions.use_cases.delete_category import delete_category
from apps.editions.use_cases.delete_criterion import delete_criterion
from apps.editions.use_cases.link_reviewer_to_edition import link_reviewer_to_edition
from apps.editions.use_cases.publish_regulation import publish_regulation
from apps.editions.use_cases.set_edition_sdgs import set_edition_sdgs
from apps.editions.use_cases.update_category import update_category
from apps.editions.use_cases.update_challenge import update_challenge
from apps.editions.use_cases.update_criterion import update_criterion
from apps.editions.use_cases.update_edition import update_edition
from apps.editions.use_cases.update_reviewer_scope import update_reviewer_scope


class EditionCriteriaView(APIView):
    """Lista e cadastra critérios de avaliação da edição (RF06)."""

    permission_classes = [IsAdmin]
    parser_classes = [JSONParser]

    def get(self, request, edition_id):
        edition = get_object_or_404(Edition, pk=edition_id)
        criteria = list_edition_criteria(edition.pk)
        return Response(CriterionSerializer(criteria, many=True).data)

    def post(self, request, edition_id):
        edition = get_object_or_404(Edition, pk=edition_id)
        serializer = CriterionWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        criterion = create_criterion(
            actor=request.user, edition=edition, **serializer.validated_data
        )
        return Response(
            CriterionSerializer(criterion).data, status=status.HTTP_201_CREATED
        )


class CriterionDetailView(APIView):
    """Atualiza ou exclui um critério de avaliação da edição (RF06)."""

    permission_classes = [IsAdmin]
    parser_classes = [JSONParser]

    def patch(self, request, criterion_id):
        criterion = get_object_or_404(Criterion, pk=criterion_id)
        serializer = CriterionWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        criterion = update_criterion(
            actor=request.user, criterion=criterion, **serializer.validated_data
        )
        return Response(CriterionSerializer(criterion).data)

    def delete(self, request, criterion_id):
        criterion = get_object_or_404(Criterion, pk=criterion_id)
        delete_criterion(actor=request.user, criterion=criterion)
        return Response(status=status.HTTP_204_NO_CONTENT)


class EditionCategoriesView(APIView):
    """Lista e cadastra categorias da edição para administradores (RF49)."""

    permission_classes = [IsAdmin]
    parser_classes = [JSONParser]

    def get(self, request, edition_id):
        edition = get_object_or_404(Edition, pk=edition_id)
        categories = list_edition_categories(edition.pk)
        return Response(CategorySerializer(categories, many=True).data)

    def post(self, request, edition_id):
        edition = get_object_or_404(Edition, pk=edition_id)
        serializer = CategoryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = create_category(
            actor=request.user, edition=edition, **serializer.validated_data
        )
        return Response(
            CategorySerializer(category).data, status=status.HTTP_201_CREATED
        )


class CategoryDetailView(APIView):
    """Atualiza ou exclui uma categoria da edição (RF49)."""

    permission_classes = [IsAdmin]
    parser_classes = [JSONParser]

    def patch(self, request, category_id):
        category = get_object_or_404(Category, pk=category_id)
        serializer = CategoryWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        category = update_category(
            actor=request.user, category=category, **serializer.validated_data
        )
        return Response(CategorySerializer(category).data)

    def delete(self, request, category_id):
        category = get_object_or_404(Category, pk=category_id)
        delete_category(actor=request.user, category=category)
        return Response(status=status.HTTP_204_NO_CONTENT)


class EditionChallengesView(APIView):
    """Lista e cadastra os desafios de uma edição (RF05)."""

    permission_classes = [IsAdmin]
    parser_classes = [JSONParser]

    def get(self, request, edition_id):
        edition = get_object_or_404(Edition, pk=edition_id)
        filters = ChallengeFiltersSerializer(data=request.query_params.dict())
        filters.is_valid(raise_exception=True)
        challenges = list_edition_challenges(
            edition_id=edition.pk, **filters.validated_data
        )
        return Response(ChallengeSerializer(challenges, many=True).data)

    def post(self, request, edition_id):
        edition = get_object_or_404(Edition, pk=edition_id)
        serializer = ChallengeWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        challenge = create_challenge(
            actor=request.user, edition=edition, **serializer.validated_data
        )
        return Response(
            ChallengeSerializer(challenge).data, status=status.HTTP_201_CREATED
        )


class ChallengeDetailView(APIView):
    """Atualiza um desafio da edição (RF05)."""

    permission_classes = [IsAdmin]
    parser_classes = [JSONParser]

    def patch(self, request, challenge_id):
        challenge = get_object_or_404(Challenge, pk=challenge_id)
        serializer = ChallengeWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        challenge = update_challenge(
            actor=request.user, challenge=challenge, **serializer.validated_data
        )
        return Response(ChallengeSerializer(challenge).data)


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


class EditionSdgsView(APIView):
    """Lista e define as ODS habilitadas na edição (RF04)."""

    permission_classes = [IsAdmin]
    parser_classes = [JSONParser]

    def get(self, request, edition_id):
        edition = get_object_or_404(Edition, pk=edition_id)
        return Response(
            EditionSdgSerializer(list_edition_sdgs(edition.pk), many=True).data
        )

    def put(self, request, edition_id):
        edition = get_object_or_404(Edition, pk=edition_id)
        serializer = EditionSdgsUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sdgs = set_edition_sdgs(
            actor=request.user, edition=edition, **serializer.validated_data
        )
        return Response(EditionSdgSerializer(sdgs, many=True).data)


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
    renderer_classes = [JSONRenderer]

    def perform_content_negotiation(self, request, force=False):
        # FileResponse entrega o PDF; o renderer formata só os erros em JSON.
        renderer = self.get_renderers()[0]
        return renderer, renderer.media_type

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
