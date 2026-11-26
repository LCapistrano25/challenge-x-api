"""Atualizar cadastro de aluno pelo administrador (RFXX). RN10."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.accounts.exceptions import RegistrationNumberTaken, UserNotFound
from apps.accounts.models import Student, User
from apps.accounts.rules import ensure_actor_is_admin, ensure_term_within_course
from apps.core.models import Course


@transaction.atomic
def update_student(
    *,
    actor: User,
    user_id: int,
    name: str | None = None,
    registration_number: str | None = None,
    course_id: int | None = None,
    term: int | None = None,
) -> Student:
    """Atualiza só os campos informados; e-mail e vínculos ficam como estão."""
    ensure_actor_is_admin(actor)
    student = Student.objects.select_related("user", "course").filter(pk=user_id)
    student = student.select_for_update().first()
    if student is None:
        raise UserNotFound()

    if course_id is not None:
        course = Course.objects.filter(pk=course_id, active=True).first()
        if course is None:
            raise ValidationError({"course_id": "Curso inválido."})
        student.course = course
    if term is not None:
        student.term = term
    if course_id is not None or term is not None:
        ensure_term_within_course(student.course, student.term)
    if registration_number is not None:
        taken = Student.objects.filter(registration_number=registration_number)
        if taken.exclude(pk=student.pk).exists():
            raise RegistrationNumberTaken()
        student.registration_number = registration_number

    if name is not None:
        student.user.name = name
        student.user.save(update_fields=["name", "updated_at"])
    try:
        student.save()
    except IntegrityError:
        raise RegistrationNumberTaken() from None
    return student
