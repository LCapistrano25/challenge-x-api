from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.core.exceptions import ValidationError as DjangoValidationError
from apps.core.models import Course

from apps.core.use_cases.create_course import create_course
from apps.core.use_cases.list_courses import list_courses
from apps.core.use_cases.update_course import update_course
from apps.core.use_cases.delete_course import delete_course
from apps.core.use_cases.list_public_courses import list_public_courses

class CourseCreateSerializer(serializers.Serializer):
    """Filtra e valida os dados que chegam da internet."""
    name = serializers.CharField(max_length=150)
    term_count = serializers.IntegerField()

class CourseCreateView(APIView):
    """Endpoint para cadastrar um novo curso (Admin)."""
    
    permission_classes = [IsAdminUser]

    def get(self, request):
        courses_data = list_courses(actor=request.user)
        return Response(courses_data, status=status.HTTP_200_OK)

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

class CourseUpdateSerializer(serializers.Serializer):
    """Filtra os dados para atualização (tudo opcional, pois usamos o PATCH)."""
    name = serializers.CharField(max_length=150, required=False)
    term_count = serializers.IntegerField(required=False)

class CourseDetailView(APIView):
    """Endpoint para atualizar (PATCH) e futuramente excluir (DELETE) um curso."""
    
    permission_classes = [IsAdminUser]

    def patch(self, request, course_id):
        serializer = CourseUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            # Chama o Cérebro para atualizar
            course = update_course(
                actor=request.user,
                course_id=course_id,
                name=serializer.validated_data.get("name"),
                term_count=serializer.validated_data.get("term_count")
            )
        except Course.DoesNotExist:
            # Traduz erro de não encontrado para HTTP 404 Not Found
            return Response({"detail": "Curso não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except DjangoValidationError as e:
            # Traduz erro de validação para HTTP 400 Bad Request
            raise DRFValidationError(e.messages)

        return Response(
            {
                "id": course.id,
                "name": course.name,
                "term_count": course.term_count
            },
            status=status.HTTP_200_OK
        )

class CourseDetailView(APIView):
    """Endpoint para atualizar (PATCH) e excluir (DELETE) um curso."""
    
    permission_classes = [IsAdminUser]

    def patch(self, request, course_id):
        serializer = CourseUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            course = update_course(
                actor=request.user,
                course_id=course_id,
                name=serializer.validated_data.get("name"),
                term_count=serializer.validated_data.get("term_count")
            )
        except Course.DoesNotExist:
            return Response({"detail": "Curso não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except DjangoValidationError as e:
            raise DRFValidationError(e.messages)

        return Response(
            {
                "id": course.id,
                "name": course.name,
                "term_count": course.term_count
            },
            status=status.HTTP_200_OK
        )

    def delete(self, request, course_id):
        try:
            delete_course(actor=request.user, course_id=course_id)
        except Course.DoesNotExist:
            return Response({"detail": "Curso não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except DjangoValidationError as e:
            raise DRFValidationError(e.messages)

        return Response(status=status.HTTP_204_NO_CONTENT)

class CoursePublicListView(APIView):
    """Endpoint público para listar apenas cursos ativos."""
    
    # Sem restrição de permissão (qualquer um pode aceder)
    
    def get(self, request):
        courses_data = list_public_courses()
        return Response(courses_data, status=status.HTTP_200_OK)