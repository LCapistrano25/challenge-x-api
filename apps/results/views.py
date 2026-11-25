from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdmin
from apps.editions.models import Edition
from apps.results.selectors import get_edition_results
from apps.results.serializers import (
    EditionResultsSerializer,
    FinalistsWriteSerializer,
)
from apps.results.use_cases.approve_finalists import approve_finalists
from apps.results.use_cases.calculate_results import calculate_results
from apps.results.use_cases.select_finalists import select_finalists


def get_edition(edition_id):
    edition = Edition.objects.filter(pk=edition_id).first()
    if edition is None:
        raise NotFound("Edição não encontrada.")
    return edition


def results_response(edition):
    return Response(EditionResultsSerializer(get_edition_results(edition)).data)


class ResultsCalculateView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, edition_id):
        edition = get_edition(edition_id)
        calculate_results(actor=request.user, edition=edition)
        return results_response(edition)


class FinalistsView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, edition_id):
        edition = get_edition(edition_id)
        serializer = FinalistsWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        select_finalists(
            actor=request.user, edition=edition, **serializer.validated_data
        )
        return results_response(edition)


class ResultsApproveView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, edition_id):
        edition = get_edition(edition_id)
        approve_finalists(actor=request.user, edition=edition)
        return results_response(edition)
