"""Gestão de alunos, professores e avaliadores externos pelo admin (RFXX).

As três rotas têm o mesmo formato; cada classe só diz o perfil, a consulta,
o serializer de escrita e o caso de uso.
"""

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import UserNotFound
from apps.accounts.permissions import IsAdmin
from apps.accounts.selectors import (
    external_reviewers_queryset,
    list_external_reviewers,
    list_students,
    list_teachers,
    students_queryset,
    teachers_queryset,
)
from apps.accounts.serializers import (
    AdminUserFilterSerializer,
    ExternalEvaluatorAdminUpdateSerializer,
    StudentAdminUpdateSerializer,
    TeacherAdminUpdateSerializer,
    UserStatusUpdateSerializer,
)
from apps.accounts.use_cases.set_user_active import set_user_active
from apps.accounts.use_cases.update_external_reviewer import update_external_reviewer
from apps.accounts.use_cases.update_student import update_student
from apps.accounts.use_cases.update_teacher import update_teacher
from config.pagination import DefaultPagination


def _course(course) -> dict:
    return {"id": course.id, "name": course.name}


def _user_fields(profile) -> dict:
    user = profile.user
    return {
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "active": user.is_active,
        "created_at": user.date_joined,
        # Nome fica no usuário e o resto no perfil: vale a alteração mais recente.
        "updated_at": max(user.updated_at, profile.updated_at),
    }


def serialize_student(student) -> dict:
    return {
        **_user_fields(student),
        "registration_number": student.registration_number,
        "course": _course(student.course),
        "term": student.term,
    }


def serialize_teacher(teacher) -> dict:
    return {
        **_user_fields(teacher),
        "courses": [
            {"course": _course(link.course), "active": link.active}
            for link in teacher.course_links.all()
        ],
    }


def serialize_external_reviewer(reviewer) -> dict:
    links = sorted(
        reviewer.edition_links.all(),
        key=lambda link: (link.edition.year, link.edition.semester),
    )
    return {
        **_user_fields(reviewer),
        "institution": reviewer.institution or None,
        "editions": [
            {
                "edition": {
                    "id": link.edition.id,
                    "year": link.edition.year,
                    "semester": link.edition.semester,
                    "name": link.edition.name or None,
                    "status": link.edition.status,
                },
                "course": _course(link.course) if link.course else None,
            }
            for link in links
        ],
    }


class AdminUserListView(APIView):
    permission_classes = [IsAdmin]
    selector = None
    serialize = None
    filters = ("search", "active", "course_id")

    def get(self, request):
        query = AdminUserFilterSerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = {k: v for k, v in query.validated_data.items() if k in self.filters}
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(
            type(self).selector(**params), request, view=self
        )
        return paginator.get_paginated_response(
            [type(self).serialize(profile) for profile in page]
        )


class AdminUserDetailView(APIView):
    permission_classes = [IsAdmin]
    queryset = None
    update_serializer = None
    update = None
    serialize = None

    def _get(self, user_id):
        profile = type(self).queryset().filter(pk=user_id).first()
        if profile is None:
            raise UserNotFound()
        return profile

    def get(self, request, user_id: int):
        return Response(type(self).serialize(self._get(user_id)))

    def patch(self, request, user_id: int):
        serializer = self.update_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        type(self).update(
            actor=request.user, user_id=user_id, **serializer.validated_data
        )
        # Relê com os relacionamentos carregados, já com a alteração.
        return Response(type(self).serialize(self._get(user_id)))


class AdminUserStatusView(APIView):
    permission_classes = [IsAdmin]
    role = None

    def patch(self, request, user_id: int):
        serializer = UserStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = set_user_active(
            actor=request.user,
            user_id=user_id,
            role=self.role,
            **serializer.validated_data,
        )
        return Response({"user_id": user.id, "active": user.is_active})


class StudentListView(AdminUserListView):
    selector = list_students
    serialize = serialize_student


class StudentDetailView(AdminUserDetailView):
    queryset = students_queryset
    update_serializer = StudentAdminUpdateSerializer
    update = update_student
    serialize = serialize_student


class StudentStatusView(AdminUserStatusView):
    role = UserRole.STUDENT


class TeacherListView(AdminUserListView):
    selector = list_teachers
    serialize = serialize_teacher


class TeacherDetailView(AdminUserDetailView):
    queryset = teachers_queryset
    update_serializer = TeacherAdminUpdateSerializer
    update = update_teacher
    serialize = serialize_teacher


class TeacherStatusView(AdminUserStatusView):
    role = UserRole.TEACHER


class ExternalReviewerListView(AdminUserListView):
    selector = list_external_reviewers
    serialize = serialize_external_reviewer
    filters = ("search", "active")


class ExternalReviewerDetailView(AdminUserDetailView):
    queryset = external_reviewers_queryset
    update_serializer = ExternalEvaluatorAdminUpdateSerializer
    update = update_external_reviewer
    serialize = serialize_external_reviewer


class ExternalReviewerStatusView(AdminUserStatusView):
    role = UserRole.EXTERNAL_REVIEWER
