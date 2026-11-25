from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.rules import ensure_actor_is_admin
from apps.core.exceptions import CourseNameTaken
from apps.core.models import Course


@transaction.atomic
def update_course(
    *,
    actor,
    course_id: int,
    name: str | None = None,
    term_count: int | None = None,
    active: bool | None = None,
) -> Course:
    """Atualiza os dados e status de ativação de um curso (RF03)."""
    ensure_actor_is_admin(actor)

    course = Course.objects.get(id=course_id)

    if name is not None:
        clean_name = name.strip()
        if not clean_name:
            raise ValidationError({"name": "Informe o nome do curso."})
        if (
            Course.objects.exclude(pk=course.pk)
            .filter(name__iexact=clean_name)
            .exists()
        ):
            raise CourseNameTaken()
        course.name = clean_name

    if term_count is not None and term_count != course.term_count:
        if term_count not in (8, 10):
            raise ValidationError(
                {"term_count": "O curso deve ter exatamente 8 ou 10 períodos."}
            )
        if course.students.filter(term__gt=term_count).exists():
            raise ValidationError(
                {
                    "term_count": (
                        "Não é possível reduzir os períodos abaixo do período "
                        "de alunos vinculados."
                    )
                }
            )
        course.term_count = term_count

    if active is not None:
        course.active = active

    course.save()
    return course
