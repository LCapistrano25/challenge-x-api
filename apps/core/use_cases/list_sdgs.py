from apps.core.models import Sdg


def list_sdgs(*, actor):
    """
    Lista todas as ODS.
    Regra: Apenas administradores.
    """
    if not actor.is_staff and not actor.is_superuser:
        raise PermissionError("Apenas administradores podem listar ODS.")

    return Sdg.objects.all().order_by("number")
