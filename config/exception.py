from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
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

    if isinstance(exc, AppError):
        return Response(body(exc.code, str(exc)), status=exc.http_status)

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
