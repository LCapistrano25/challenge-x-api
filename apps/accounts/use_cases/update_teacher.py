"""Atualizar cadastro de professor pelo administrador (RFXX). RF10, RN04."""

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.exceptions import UserNotFound
from apps.accounts.models import Teacher, TeacherCourse, User
from apps.accounts.rules import ensure_actor_is_admin
from apps.core.models import Course


@transaction.atomic
def update_teacher(
    *,
    actor: User,
    user_id: int,
    name: str | None = None,
    courses: list[dict] | None = None,
) -> Teacher:
    """Atualiza o nome e cria ou atualiza vínculos; os não listados não mudam."""
    ensure_actor_is_admin(actor)
    teacher = Teacher.objects.select_related("user").filter(pk=user_id).first()
    if teacher is None:
        raise UserNotFound()

    if courses:
        ids = {link["course_id"] for link in courses}
        found = set(Course.objects.filter(pk__in=ids).values_list("pk", flat=True))
        if missing := sorted(ids - found):
            raise ValidationError({"courses": f"Cursos inexistentes: {missing}."})
        for link in courses:
            # O vínculo inativo some do escopo de avaliação, mas fica no histórico.
            TeacherCourse.objects.update_or_create(
                teacher=teacher,
                course_id=link["course_id"],
                defaults={"active": link["active"]},
            )

    if name is not None:
        teacher.user.name = name
        teacher.user.save(update_fields=["name", "updated_at"])
    teacher.save(update_fields=["updated_at"])
    return teacher
