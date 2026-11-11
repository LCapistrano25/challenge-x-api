from django.core.exceptions import ValidationError
from django.db import transaction
from apps.core.models import Course

@transaction.atomic
def update_course(*, actor, course_id: int, name: str = None, term_count: int = None) -> Course:
    """
    Atualiza os dados de um curso existente.
    Regras de negócio:
    - Apenas administradores podem atualizar.
    - Nome deve continuar único.
    - 8 ou 10 períodos (se for alterado).
    """
    # 1. Verifica se o utilizador tem permissão
    if not actor.is_staff and not actor.is_superuser:
        raise PermissionError("Apenas administradores podem atualizar cursos.")

    # 2. Busca o curso (se não existir, o Django lança Course.DoesNotExist)
    course = Course.objects.get(id=course_id)

    # 3. Valida e atualiza o nome (se foi enviado um nome novo)
    if name is not None and name != course.name:
        if Course.objects.filter(name=name).exists():
            raise ValidationError("Já existe outro curso com este nome.")
        course.name = name

    # 4. Valida e atualiza a quantidade de períodos (se foi enviada)
    if term_count is not None and term_count != course.term_count:
        if term_count not in [8, 10]:
            raise ValidationError("O curso deve ter exatamente 8 ou 10 períodos.")
        course.term_count = term_count

    # 5. Guarda as alterações no banco de dados
    course.save()
    
    return course