from apps.core.models import Sdg


def list_sdgs(*, actor, active: bool | None = None):
    """
    Lista todas as ODS.
    Regra: Apenas administradores.
    """
    if not actor.is_staff and not actor.is_superuser:
        raise PermissionError("Apenas administradores podem listar ODS.")

    sdgs = Sdg.objects.all()
    if active is not None:
        sdgs = sdgs.filter(active=active)
    return sdgs.order_by("number")
