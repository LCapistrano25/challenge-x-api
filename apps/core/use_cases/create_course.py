from django.db import transaction
from django.core.exceptions import ValidationError
from apps.core.models import Course

@transaction.atomic
def create_course(*, actor, name: str, term_count: int) -> Course:
    """
    Cadastra um novo curso.
    Regras de negócio (RF03):
    - Apenas administradores podem criar.
    - Nome único.
    - 8 ou 10 períodos.
    """
    # 1. Verifica se o utilizador tem permissão de admin
    if not actor.is_staff and not actor.is_superuser:
        raise PermissionError("Apenas administradores podem cadastrar cursos.")

    # 2. Valida a quantidade de períodos antes de bater no banco
    if term_count not in [8, 10]:
        raise ValidationError("O curso deve ter exatamente 8 ou 10 períodos.")

    # 3. Valida se já existe um curso com esse nome
    if Course.objects.filter(name__iexact=name).exists():
        raise ValidationError("Já existe um curso cadastrado com este nome.")

    # 4. Salva o curso na base de dados
    course = Course.objects.create(
        name=name,
        term_count=term_count
    )

    return course