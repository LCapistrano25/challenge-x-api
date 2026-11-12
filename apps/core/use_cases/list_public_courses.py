from typing import List, Dict, Any
from apps.core.models import Course

def list_public_courses() -> List[Dict[str, Any]]:
    """
    Lista os cursos para o público geral.
    Regra: Retorna APENAS os cursos marcados como ativos.
    """
    # Filtra por active=True e devolve os dados puros
    return list(Course.objects.filter(active=True).values("id", "name", "term_count"))