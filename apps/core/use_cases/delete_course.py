from django.core.exceptions import ValidationError
from django.db import transaction
from apps.core.models import Course

@transaction.atomic
def delete_course(*, actor, course_id: int) -> None:
    """
    Exclui um curso existente.
    Regra: Não exclui curso com professores ou projetos vinculados.
    """
    if not actor.is_staff and not actor.is_superuser:
        raise PermissionError("Apenas administradores podem excluir cursos.")

    course = Course.objects.get(id=course_id)

    # Verifica os vínculos de forma segura (usando o padrão _set do Django)
    has_professors = hasattr(course, 'professor_set') and course.professor_set.exists()
    has_projects = hasattr(course, 'project_set') and course.project_set.exists()

    if has_professors or has_projects:
        raise ValidationError("Não é possível excluir este curso pois possui professores ou projetos vinculados.")

    course.delete()