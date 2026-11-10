from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsStudentAccount
from apps.accounts.serializers import StudentProfileSerializer
from apps.accounts.use_cases.register_student import register_student


class StudentProfileView(APIView):
    permission_classes = [IsStudentAccount]

    def post(self, request):
        serializer = StudentProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        student = register_student(actor=request.user, **serializer.validated_data)

        return Response(
            {"student": {"user_id": student.user_id}}, status=status.HTTP_201_CREATED
        )
