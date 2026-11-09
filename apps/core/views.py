from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.core.use_cases.create_course import create_course

class CourseCreateSerializer(serializers.Serializer):
    """Filtra e valida os dados que chegam da internet."""
    name = serializers.CharField(max_length=150)
    term_count = serializers.IntegerField()

class CourseCreateView(APIView):
    """Endpoint para cadastrar um novo curso (Admin)."""
    
    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = CourseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            # 2. Chama o seu Caso de Uso (Cérebro)
            course = create_course(
                actor=request.user,
                name=serializer.validated_data["name"],
                term_count=serializer.validated_data["term_count"]
            )
        except DjangoValidationError as e:
            # 3. Traduz o erro interno para um erro HTTP 400 Bad Request
            raise DRFValidationError(e.messages)

        # 4. Devolve a resposta de sucesso (201 Created)
        return Response(
            {
                "id": course.id, 
                "name": course.name, 
                "term_count": course.term_count
            },
            status=status.HTTP_201_CREATED
        )