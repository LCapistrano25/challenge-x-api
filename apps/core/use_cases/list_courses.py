from typing import List, Dict, Any
from apps.core.models import Course

def list_courses(*, actor) -> List[Dict[str, Any]]:
    """
    Lista todos os cursos cadastrados.
    Regra: Apenas administradores podem ver esta lista (já garantido pela View, mas mantemos o actor para auditoria futura).
    """
    if not actor.is_staff and not actor.is_superuser:
        raise PermissionError("Apenas administradores podem listar cursos.")
        
    # Retorna os dados puros (sem acoplamento com objetos complexos do Django)
    return list(Course.objects.all().values("id", "name", "term_count"))