"""Troca o authorization code da Microsoft pela identidade do usuário (RF18, RF36)."""

import base64
import json
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

from django.conf import settings

from apps.accounts.exceptions import InvalidCredentials
from apps.core.exceptions import ExternalServiceError

TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
TIMEOUT_SECONDS = 10


def fetch_identity(code: str) -> dict:
    """Devolve microsoft_id, email e name do dono do código.

    O id_token vem direto do endpoint de token, por TLS e com o client secret,
    então dispensa conferir a assinatura (OpenID Connect Core, 3.1.3.7).
    Levanta InvalidCredentials (código inválido ou de outro tenant) ou
    ExternalServiceError (Microsoft fora do ar ou app mal configurado).
    """
    if not settings.MICROSOFT_CLIENT_ID:
        raise ExternalServiceError("Login com a Microsoft não configurado.")

    body = urlencode(
        {
            "client_id": settings.MICROSOFT_CLIENT_ID,
            "client_secret": settings.MICROSOFT_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.MICROSOFT_REDIRECT_URI,
            "scope": "openid profile email",
        }
    ).encode()
    url = TOKEN_URL.format(tenant=settings.MICROSOFT_TENANT_ID)
    try:
        with urlopen(url, data=body, timeout=TIMEOUT_SECONDS) as response:
            tokens = json.load(response)
    except HTTPError as error:
        # invalid_grant: código inválido, expirado ou já usado. O resto é configuração.
        if _error_code(error) == "invalid_grant":
            raise InvalidCredentials() from None
        raise ExternalServiceError() from None
    except OSError:
        raise ExternalServiceError() from None

    claims = _claims(tokens["id_token"])
    # O tenant garante o domínio do e-mail: um tenant de fora poderia usar qualquer um.
    if (
        claims.get("tid") != settings.MICROSOFT_TENANT_ID
        or claims.get("aud") != settings.MICROSOFT_CLIENT_ID
    ):
        raise InvalidCredentials()

    return {
        "microsoft_id": claims["oid"],
        "email": claims["preferred_username"].strip().lower(),
        "name": claims.get("name", ""),
    }


def _error_code(error: HTTPError) -> str:
    try:
        return json.load(error).get("error", "")
    except ValueError:
        return ""


def _claims(id_token: str) -> dict:
    payload = id_token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
