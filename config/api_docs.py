"""Swagger UI do contrato (docs/api/openapi.yaml), ligado por ENABLE_API_DOCS.

Serve o YAML do contrato como está: a fonte de verdade continua sendo o gerador.
"""

from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.views.decorators.http import require_GET

SPEC_PATH = Path(__file__).resolve().parent.parent / "docs" / "api" / "openapi.yaml"
SWAGGER_UI = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14"

PAGE = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Desafio X — API</title>
  <link rel="stylesheet" href="{SWAGGER_UI}/swagger-ui.css">
</head>
<body>
<div id="swagger-ui"></div>
<script src="{SWAGGER_UI}/swagger-ui-bundle.js"></script>
<script>
// Autenticação por sessão: o cookie sessionid vai sozinho (mesma origem). Para
// entrar, use POST /api/auth/sessions/password aqui mesmo.
function cookie(name) {{
  const m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
  return m ? decodeURIComponent(m[1]) : null;
}}
SwaggerUIBundle({{
  url: "openapi.yaml",
  dom_id: "#swagger-ui",
  persistAuthorization: true,
  requestInterceptor: async (req) => {{
    // O contrato aponta para localhost:8000; chama o servidor desta página.
    const u = new URL(req.url, location.href);
    if (u.pathname.startsWith("/api/")) {{
      req.url = location.origin + u.pathname + u.search;
    }}
    req.credentials = "same-origin";
    if (!["GET", "HEAD", "OPTIONS"].includes(req.method.toUpperCase())) {{
      if (!cookie("csrftoken")) {{
        await fetch("/api/auth/csrf", {{credentials: "same-origin"}});
      }}
      req.headers["X-CSRFToken"] = cookie("csrftoken");
    }}
    return req;
  }},
}});
</script>
</body>
</html>
"""


def ensure_enabled():
    if not settings.ENABLE_API_DOCS:
        raise Http404


@require_GET
def swagger_ui(request):
    ensure_enabled()
    return HttpResponse(PAGE)


@require_GET
def openapi_spec(request):
    ensure_enabled()
    return FileResponse(SPEC_PATH.open("rb"), content_type="application/yaml")
