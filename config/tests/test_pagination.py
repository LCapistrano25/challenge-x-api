import pytest
from rest_framework import generics, serializers
from rest_framework.permissions import AllowAny
from rest_framework.test import APIRequestFactory

from apps.core.factories import CourseFactory
from apps.core.models import Course

pytestmark = pytest.mark.django_db


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ["id", "name"]


class CourseList(generics.ListAPIView):
    queryset = Course.objects.order_by("id")
    serializer_class = CourseSerializer
    authentication_classes = []
    permission_classes = [AllowAny]


class ShortCourseList(CourseList):
    pagination_class = None


def get(view, **params):
    return view.as_view()(APIRequestFactory().get("/cursos", params))


@pytest.fixture
def total():
    CourseFactory.create_batch(130)
    return Course.objects.count()


def test_listagem_usa_20_por_pagina_por_padrao(total):
    resposta = get(CourseList)

    assert resposta.status_code == 200
    assert set(resposta.data) == {"count", "next", "previous", "results"}
    assert resposta.data["count"] == total
    assert len(resposta.data["results"]) == 20
    assert resposta.data["previous"] is None
    assert "page=2" in resposta.data["next"]


def test_page_size_muda_o_tamanho_da_pagina(total):
    resposta = get(CourseList, page=2, page_size=5)

    assert len(resposta.data["results"]) == 5
    assert resposta.data["previous"] is not None


def test_page_size_acima_de_100_fica_em_100(total):
    resposta = get(CourseList, page_size=500)

    assert len(resposta.data["results"]) == 100


def test_pagina_inexistente_responde_404_no_formato_padrao(total):
    resposta = get(CourseList, page=999)

    assert resposta.status_code == 404
    assert resposta.data["error"]["code"] == "not_found"


def test_listagem_curta_sem_paginacao_devolve_array(total):
    resposta = get(ShortCourseList)

    assert isinstance(resposta.data, list)
    assert len(resposta.data) == total
