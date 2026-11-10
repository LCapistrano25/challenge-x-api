from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdmin
from apps.editions.models.edition import Edition
from apps.editions.selectors import list_edition_reviewers
from apps.editions.serializers import EditionReviewerSerializer


class EditionReviewView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request, edition_id):
        get_object_or_404(Edition, pk=edition_id)
        reviewers = list_edition_reviewers(edition_id)
        return Response(EditionReviewerSerializer(reviewers, many=True).data)
