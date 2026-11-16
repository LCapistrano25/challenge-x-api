import pytest
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from apps.accounts.factories import UserFactory

pytestmark = pytest.mark.django_db


class ViewSemPermissao(APIView):
    """View que esquece de declarar permission_classes."""

    def get(self, request):
        return Response({"ok": True})


def get(user=None):
    request = APIRequestFactory().get("/")
    if user:
        force_authenticate(request, user=user)
    return ViewSemPermissao.as_view()(request)


def test_view_sem_permissao_exige_login():
    resposta = get()

    assert resposta.status_code == 403
    assert resposta.data["error"]["code"] == "not_authenticated"


def test_view_sem_permissao_libera_usuario_logado():
    assert get(UserFactory()).status_code == 200
