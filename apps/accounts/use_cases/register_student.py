"""UC21 — Realizar autocadastro. RF19. Regras: RN02 do Administrador (domínios)."""

from django.db import IntegrityError, transaction

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import (
    NotStudentActor,
    RegistrationNumberTaken,
    RegistrationRejected,
    StudentProfileExists,
)
from apps.accounts.models import Student, User
from apps.accounts.rules import ensure_institutional_domain
from apps.core.models import Course


@transaction.atomic
def register_student(
    *, actor: User, registration_number: str, course_id: int, term: int
) -> Student:
    """Conclui o autocadastro do aluno autenticado (UC21, RF19).

    Levanta NotStudentActor, InvalidEmailDomain, DomainRoleMismatch,
    RegistrationRejected (curso ou período inválido), StudentProfileExists
    ou RegistrationNumberTaken.
    """
    if actor.role != UserRole.STUDENT:
        raise NotStudentActor()
    ensure_institutional_domain(actor.email, UserRole.STUDENT)
    if Student.objects.filter(user=actor).exists():
        raise StudentProfileExists()

    course = Course.objects.filter(pk=course_id, active=True).first()
    if course is None:
        raise RegistrationRejected("Curso inválido.")
    if not 1 <= term <= course.term_count:
        raise RegistrationRejected(
            f"O período deve estar entre 1 e {course.term_count}."
        )

    if Student.objects.filter(registration_number=registration_number).exists():
        raise RegistrationNumberTaken()
    try:
        return Student.objects.create(
            user=actor,
            registration_number=registration_number,
            course=course,
            term=term,
        )
    except IntegrityError:
        # Dois cadastros simultâneos passam pela checagem acima; o banco desempata.
        raise RegistrationNumberTaken() from None
