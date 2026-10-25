import pytest


@pytest.fixture(autouse=True)
def fast_password_hasher(settings):
    # O hash padrão (PBKDF2) é lento de propósito; nos testes só atrasa a suíte.
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
