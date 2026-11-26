from django.db import transaction
from django.db.models.deletion import ProtectedError

from apps.accounts.rules import ensure_actor_is_admin
from apps.core.exceptions import CourseInUse
from apps.core.models import Course


@transaction.atomic
def delete_course(*, actor, course_id: int) -> None:
    """Exclui fisicamente um curso apenas quando não possui vínculos (RF03)."""
    ensure_actor_is_admin(actor)

    course = Course.objects.get(id=course_id)

    if (
        course.students.exists()
        or course.teachers.exists()
        or course.challenges.exists()
    ):
        raise CourseInUse()

    try:
        course.delete()
    except ProtectedError as exc:
        raise CourseInUse() from exc
