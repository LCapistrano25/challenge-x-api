"""Consultas de leitura de accounts (RF02 e gestão de usuários pelo admin)."""

from django.db.models import Prefetch, Q, QuerySet

from apps.accounts.models import (
    EmailDomain,
    ExternalReviewer,
    Student,
    Teacher,
    TeacherCourse,
)


def list_email_domains(
    *, active: bool | None = None, role: str | None = None
) -> QuerySet[EmailDomain]:
    """Lista os domínios institucionais ordenados por nome."""
    queryset = EmailDomain.objects.order_by("name")
    if active is not None:
        queryset = queryset.filter(active=active)
    if role:
        queryset = queryset.filter(role=role)
    return queryset


def _filter_users(queryset, *, search, active, extra_search=()):
    if active is not None:
        queryset = queryset.filter(user__is_active=active)
    if search:
        condition = Q(user__name__icontains=search) | Q(user__email__icontains=search)
        for field in extra_search:
            condition |= Q(**{f"{field}__icontains": search})
        queryset = queryset.filter(condition)
    return queryset.order_by("user__name", "user_id")


def students_queryset() -> QuerySet[Student]:
    return Student.objects.select_related("user", "course")


def teachers_queryset() -> QuerySet[Teacher]:
    links = TeacherCourse.objects.select_related("course").order_by("course__name")
    return Teacher.objects.select_related("user").prefetch_related(
        Prefetch("course_links", queryset=links)
    )


def external_reviewers_queryset() -> QuerySet[ExternalReviewer]:
    return ExternalReviewer.objects.select_related("user").prefetch_related(
        "edition_links__edition", "edition_links__course"
    )


def list_students(*, search=None, active=None, course_id=None) -> QuerySet[Student]:
    """Alunos para o admin; a busca cobre nome, e-mail e matrícula."""
    queryset = students_queryset()
    if course_id:
        queryset = queryset.filter(course_id=course_id)
    return _filter_users(
        queryset,
        search=search,
        active=active,
        extra_search=["registration_number"],
    )


def list_teachers(*, search=None, active=None, course_id=None) -> QuerySet[Teacher]:
    """Professores para o admin; course_id considera só vínculos ativos."""
    queryset = teachers_queryset()
    if course_id:
        queryset = queryset.filter(
            course_links__course_id=course_id, course_links__active=True
        ).distinct()
    return _filter_users(queryset, search=search, active=active)


def list_external_reviewers(*, search=None, active=None) -> QuerySet[ExternalReviewer]:
    """Avaliadores externos para o admin."""
    return _filter_users(external_reviewers_queryset(), search=search, active=active)
