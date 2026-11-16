from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdmin
from apps.accounts.serializers import ExternalReviewSerializer
from apps.accounts.use_cases.register_external_reviewer import (
    register_external_reviewer,
)


class ExternalReviewProfileView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request):
        serializer = ExternalReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        external_review = register_external_reviewer(
            actor=request.user, **serializer.validated_data
        )

        return Response(
            {
                "external_evaluator": {
                    "user_id": external_review.user_id,
                    "email": external_review.user.email,
                }
            },
            status=status.HTTP_201_CREATED,
        )
