import pytest


@pytest.fixture(autouse=True)
def delivery_storage_root(settings, tmp_path):
    """Os testes gravam as entregas em tmp_path, nunca no disco real do projeto."""
    root = tmp_path / "deliveries-storage"
    storages = dict(settings.STORAGES)
    storages["deliveries"] = {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": str(root)},
    }
    settings.STORAGES = storages
    return root


def stored_keys(root):
    """Chaves (caminhos relativos) de todos os arquivos gravados no storage."""
    if not root.exists():
        return []
    return sorted(
        p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
    )
