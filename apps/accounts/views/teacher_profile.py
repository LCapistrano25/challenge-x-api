from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsTeacherAccount
from apps.accounts.serializers import TeacherProfileSerializer
from apps.accounts.use_cases.register_teacher import register_teacher


class TeacherProfileView(APIView):
    permission_classes = [IsTeacherAccount]

    def post(self, request):
        serializer = TeacherProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        teacher = register_teacher(actor=request.user, **serializer.validated_data)

        return Response(
            {"teacher": {"user_id": teacher.user_id}}, status=status.HTTP_201_CREATED
        )
