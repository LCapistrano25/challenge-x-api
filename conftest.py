import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def fast_password_hasher(settings):
    # O hash padrão (PBKDF2) é lento de propósito; nos testes só atrasa a suíte.
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    # O limite de tentativas fica no cache; sem limpar, um teste herda as do outro.
    cache.clear()
