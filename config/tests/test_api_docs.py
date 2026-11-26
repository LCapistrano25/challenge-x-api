import pytest


@pytest.fixture
def docs_on(settings):
    settings.ENABLE_API_DOCS = True


@pytest.mark.django_db
@pytest.mark.parametrize("url", ["/api/docs/", "/api/docs/openapi.yaml"])
def test_docs_desligada_responde_404(client, settings, url):
    settings.ENABLE_API_DOCS = False

    response = client.get(url)

    assert response.status_code == 404


@pytest.mark.django_db
def test_swagger_abre_sem_login(client, docs_on):
    response = client.get("/api/docs/")

    assert response.status_code == 200
    assert b"SwaggerUIBundle" in response.content
    assert b"X-CSRFToken" in response.content


@pytest.mark.django_db
def test_serve_o_contrato_sem_login(client, docs_on):
    response = client.get("/api/docs/openapi.yaml")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/yaml"
    assert b"sessionAuth" in b"".join(response.streaming_content)
