"""Formato padrão de erro (P-37): cada caminho do custom_exception_handler."""

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import exceptions, serializers
from rest_framework.permissions import AllowAny
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from apps.accounts.exceptions import NotAdminActor
from apps.core.exceptions import ExternalServiceError
from apps.editions.exceptions import (
    EditionAlreadyExists,
    TeamLimitsLocked,
)


class StorageUnavailable(ExternalServiceError):
    code = "storage_unavailable"
    default_message = "Armazenamento indisponível."


class Payload(serializers.Serializer):
    email = serializers.EmailField()
    name = serializers.CharField()


def raise_validation_from_serializer():
    Payload(data={"email": "x"}).is_valid(raise_exception=True)


def respond(error):
    """Chama uma view que lança `error` (exceção ou função que lança)."""

    class Boom(APIView):
        authentication_classes = []
        permission_classes = [AllowAny]

        def get(self, request):
            if callable(error) and not isinstance(error, Exception):
                error()
            raise error

    return Boom.as_view()(APIRequestFactory().get("/"))


def assert_error(resposta, status, code):
    assert resposta.status_code == status
    assert set(resposta.data) == {"error"}
    assert set(resposta.data["error"]) == {"code", "message", "details"}
    assert resposta.data["error"]["code"] == code


# Validação


def test_validacao_do_serializer_detalha_por_campo():
    resposta = respond(raise_validation_from_serializer)

    assert_error(resposta, 400, "validation_error")
    assert set(resposta.data["error"]["details"]) == {"email", "name"}


def test_validacao_sem_campo_vai_para_non_field_errors():
    resposta = respond(exceptions.ValidationError("Erro solto."))

    assert_error(resposta, 400, "validation_error")
    assert resposta.data["error"]["details"] == {"non_field_errors": ["Erro solto."]}


def test_validation_error_do_django_com_campo():
    resposta = respond(DjangoValidationError({"password": ["Senha fraca."]}))

    assert_error(resposta, 400, "validation_error")
    assert resposta.data["error"]["details"] == {"password": ["Senha fraca."]}


def test_validation_error_do_django_sem_campo():
    # É o que validate_password lança.
    resposta = respond(DjangoValidationError(["A senha é muito curta."]))

    assert_error(resposta, 400, "validation_error")
    assert resposta.data["error"]["details"] == {
        "non_field_errors": ["A senha é muito curta."]
    }


# Exceções da aplicação


def test_regra_de_negocio_vira_409_com_code_da_classe():
    resposta = respond(TeamLimitsLocked())

    assert_error(resposta, 409, "team_limits_locked")
    assert resposta.data["error"]["message"] == TeamLimitsLocked.default_message
    assert resposta.data["error"]["details"] is None


def test_filha_usa_o_proprio_http_status():
    assert_error(respond(NotAdminActor()), 403, "not_admin_actor")


def test_servico_externo_vira_503():
    assert_error(respond(StorageUnavailable()), 503, "storage_unavailable")


def test_mensagem_personalizada_substitui_a_padrao():
    resposta = respond(EditionAlreadyExists("Outra mensagem."))

    assert resposta.data["error"]["message"] == "Outra mensagem."


# Exceções do DRF


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (exceptions.NotFound(), 404, "not_found"),
        (exceptions.PermissionDenied(), 403, "permission_denied"),
        (exceptions.MethodNotAllowed("POST"), 405, "method_not_allowed"),
    ],
)
def test_excecao_do_drf_sai_no_formato_padrao(error, status, code):
    assert_error(respond(error), status, code)


# Erro inesperado


def test_erro_inesperado_nao_e_engolido():
    # O handler devolve None e o DRF relança: vira 500 e aparece no log.
    with pytest.raises(RuntimeError):
        respond(RuntimeError("bug"))
