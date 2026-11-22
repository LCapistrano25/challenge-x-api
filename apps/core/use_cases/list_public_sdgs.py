from apps.core.models import Sdg


def list_public_sdgs():
    """
    Lista apenas as ODS ativas para o público geral.
    """
    return Sdg.objects.filter(active=True).order_by("number")
