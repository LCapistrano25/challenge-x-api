from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdmin
from apps.editions.models import Edition, EditionReviewer
from apps.editions.selectors import list_edition_reviewers
from apps.editions.serializers import (
    EditionReviewerCreateSerializer,
    EditionReviewerSerializer,
    EditionReviewerUpdateSerializer,
)
from apps.editions.use_cases.link_reviewer_to_edition import link_reviewer_to_edition
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
