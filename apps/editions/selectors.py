from apps.editions.models import Edition


def list_editions():
    """Todas as edições, na ordem do model (ano e semestre, da mais recente)."""
    return Edition.objects.all()
