from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import (
    RequestDataTooBig,
    TooManyFieldsSent,
    TooManyFilesSent,
)
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404, JsonResponse
from django.views.csrf import csrf_failure as django_csrf_failure
from django.views.defaults import page_not_found
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler

from apps.core.exceptions import AppError


def body(code, message, details=None):
    return {"error": {"code": code, "message": message, "details": details}}


def custom_exception_handler(exc, context):
    """Responde todo erro no formato padrão (P-37)."""
    # ValidationError do Django (validate_password, clean()): o DRF não a trata.
    if isinstance(exc, DjangoValidationError):
        details = (
            exc.message_dict
            if hasattr(exc, "error_dict")
            else {"non_field_errors": exc.messages}
        )
        exc = ValidationError(details)
    # Http404 (get_object_or_404) e PermissionDenied do Django não têm default_code.
    elif isinstance(exc, Http404):
        exc = NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = PermissionDenied()

    # Corpo acima de DATA_UPLOAD_MAX_MEMORY_SIZE ou campos demais: sem isto o
    # Django responde a página HTML de 400.
    if isinstance(exc, (RequestDataTooBig, TooManyFieldsSent, TooManyFilesSent)):
        return Response(
            body("request_too_large", "A requisição excede o tamanho permitido."),
            status=400,
        )

    if isinstance(exc, AppError):
        return Response(
            body(exc.code, str(exc), getattr(exc, "details", None)),
            status=exc.http_status,
        )

    response = exception_handler(exc, context)
    if response is None:
        return None  # erro inesperado: vira 500 do Django e aparece no log

    if isinstance(exc, ValidationError):
        details = (
            exc.detail
            if isinstance(exc.detail, dict)
            else {"non_field_errors": exc.detail}
        )
        response.data = body("validation_error", "Dados inválidos.", details)
    else:
        response.data = body(exc.default_code, str(exc.detail))
    return response


def api_not_found(request, exception=None):
    """Rota inexistente: na API sai no formato padrão; fora dela, a página do Django."""
    if request.path.startswith("/api/"):
        return JsonResponse(body("not_found", "Recurso não encontrado."), status=404)
    return page_not_found(request, exception)


def api_csrf_failure(request, reason=""):
    """Falha de CSRF: na API sai no formato padrão; fora dela, a página do Django."""
    if request.path.startswith("/api/"):
        message = f"CSRF Failed: {reason}" if reason else "CSRF Failed."
        return JsonResponse(body("permission_denied", message), status=403)
    return django_csrf_failure(request, reason=reason)
