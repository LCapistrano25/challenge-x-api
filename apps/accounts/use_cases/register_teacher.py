"""UC10 — Configurar perfil do professor. RF10, RF36.1. Decisão da P-04 (#68)."""

from django.db import IntegrityError, transaction

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import (
    NotTeacherActor,
    RegistrationRejected,
    TeacherProfileExists,
)
from apps.accounts.models import Teacher, TeacherCourse, User
from apps.accounts.rules import ensure_institutional_domain
from apps.core.models import Course


@transaction.atomic
def register_teacher(*, actor: User, course_ids: list[int]) -> Teacher:
    """Cria o perfil do professor autenticado e os vínculos com os cursos.

    A escolha é única, no primeiro acesso, e os vínculos já nascem ativos;
    depois disso só o administrador altera os cursos (P-04, #68).
    Levanta NotTeacherActor, InvalidEmailDomain, DomainRoleMismatch,
    TeacherProfileExists ou RegistrationRejected (curso inexistente ou inativo).
    """
    if actor.role != UserRole.TEACHER:
        raise NotTeacherActor()
    ensure_institutional_domain(actor.email, UserRole.TEACHER)
    if Teacher.objects.filter(user=actor).exists():
        raise TeacherProfileExists()

    course_ids = set(course_ids)
    courses = list(Course.objects.filter(pk__in=course_ids, active=True))
    if not course_ids or len(courses) != len(course_ids):
        raise RegistrationRejected("Curso inválido.")

    try:
        teacher = Teacher.objects.create(user=actor)
    except IntegrityError:
        # Duas configurações simultâneas passam pela checagem acima; o banco desempata.
        raise TeacherProfileExists() from None
    TeacherCourse.objects.bulk_create(
        TeacherCourse(teacher=teacher, course=course) for course in courses
    )
    return teacher
