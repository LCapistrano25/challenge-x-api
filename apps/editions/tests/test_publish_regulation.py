from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from itertools import chain
from threading import Barrier, Event
from uuid import UUID

import pytest
from django.apps import apps
from django.core import serializers as django_serializers
from django.core.files.storage import storages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import (
    DatabaseError,
    OperationalError,
    connection,
    connections,
    transaction,
)
from django.db.models.signals import post_migrate
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import NotAdminActor
from apps.accounts.factories import UserFactory
from apps.core.models import Course, Sdg
from apps.core.tests.contract import mismatches, schema
from apps.editions.enums import EditionStatus
from apps.editions.exceptions import EditionNotInSetup
from apps.editions.factories import (
    CategoryFactory,
    ChallengeFactory,
    EditionFactory,
    StageCriterionFactory,
    StageFactory,
)
from apps.editions.models import Edition
from apps.editions.regulation_files import delete_regulation
from apps.editions.use_cases.publish_regulation import publish_regulation

pytestmark = pytest.mark.django_db
PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"


@pytest.fixture
def edition():
    edition = EditionFactory()
    ChallengeFactory(edition=edition)
    CategoryFactory(edition=edition)
    stage = StageFactory(edition=edition, max_score=Decimal("10"))
    StageCriterionFactory(stage=stage, max_score=Decimal("10"))
    return edition


@pytest.fixture
def admin_client():
    client = APIClient()
    client.force_authenticate(UserFactory(role=UserRole.ADMIN))
    return client


@pytest.fixture(autouse=True)
def regulation_storage(settings, tmp_path):
    settings.STORAGES = {
        **settings.STORAGES,
        "regulations": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": tmp_path},
        },
    }
    return tmp_path


@pytest.fixture
def restore_catalogs_after_flush():
    """Restaura os catálogos carregados pelas migrations, incluindo suas PKs."""
    courses = Course.objects.order_by("pk")
    sdgs = Sdg.objects.order_by("pk")

    def snapshot():
        return django_serializers.serialize("python", chain(courses.all(), sdgs.all()))

    initial = snapshot()
    core = apps.get_app_config("core")

    def restore(sender, using, **kwargs):
        if using != connection.alias:
            return
        post_migrate.disconnect(restore, sender=core)
        for row in django_serializers.deserialize("python", initial):
            row.save(using=using)
        assert snapshot() == initial

    # O flush do teste transacional emite o sinal depois do teardown das fixtures.
    post_migrate.connect(restore, sender=core, weak=False)


def publish(client, edition_id, content=PDF, **headers):
    file = SimpleUploadedFile("edital.pdf", content, "application/pdf")
    return client.post(
        f"/api/admin/editions/{edition_id}/publish",
        {"notice_file": file},
        format="multipart",
        **headers,
    )


def test_publica_e_disponibiliza_pdf_para_consulta(admin_client, edition):
    response = publish(admin_client, edition.pk)
    assert response.status_code == 200
    assert mismatches(response.json(), schema("Edition")) == []
    edition.refresh_from_db()
    assert edition.status == EditionStatus.PUBLISHED
    assert edition.published_at is not None
    assert response.json()["regulation_url"] == edition.regulation_url

    download = APIClient().get(edition.regulation_url)
    assert download.status_code == 200
    assert download["Content-Type"] == "application/pdf"
    assert b"".join(download.streaming_content) == PDF


def test_incompleta_informa_pendencias_sem_gravar_pdf(admin_client, regulation_storage):
    Course.objects.update(active=False)
    edition = EditionFactory()
    response = publish(admin_client, edition.pk)
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "publication_requirements_not_met"
    assert {"courses", "sdgs", "challenges", "categories", "criteria", "stages"} <= set(
        error["details"]
    )
    edition.refresh_from_db()
    assert edition.status == EditionStatus.SETUP
    assert not list(regulation_storage.rglob("*.pdf"))


def test_pdf_invalido_nao_publica(admin_client, edition):
    response = publish(admin_client, edition.pk, b"arquivo renomeado")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    edition.refresh_from_db()
    assert edition.status == EditionStatus.SETUP


@pytest.mark.parametrize("status", [EditionStatus.PUBLISHED, EditionStatus.CLOSED])
def test_rejeita_edicao_fora_de_configuracao(admin_client, edition, status):
    edition.status = status
    edition.save(update_fields=["status"])
    response = publish(admin_client, edition.pk)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "edition_not_in_setup"


def test_anonimo_recebe_401(edition):
    assert publish(APIClient(), edition.pk).status_code == 401


def test_papel_incorreto_recebe_403(edition):
    client = APIClient()
    client.force_authenticate(UserFactory(role=UserRole.STUDENT))
    assert publish(client, edition.pk).status_code == 403


def test_edicao_inexistente_recebe_404(admin_client):
    response = publish(admin_client, 999999)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.parametrize(
    ("stage_score", "criterion_score", "missing"),
    [(9, 9, "stages"), (10, 9, "stage_criteria"), (10, None, "stage_criteria")],
)
def test_conferencia_das_somas(
    admin_client, edition, stage_score, criterion_score, missing
):
    stage = edition.stages.get()
    edition.stages.update(max_score=stage_score)
    if criterion_score is None:
        stage.criterion_links.all().delete()
    else:
        stage.criterion_links.update(max_score=criterion_score)

    response = publish(admin_client, edition.pk)
    assert response.status_code == 409
    assert missing in response.json()["error"]["details"]


def test_segunda_publicacao_preserva_pdf_original(admin_client, edition):
    first = publish(admin_client, edition.pk)
    assert first.status_code == 200
    assert (
        publish(admin_client, edition.pk, PDF.replace(b"Catalog", b"Page")).status_code
        == 409
    )
    edition.refresh_from_db()
    assert edition.regulation_url == first.json()["regulation_url"]
    download = APIClient().get(edition.regulation_url)
    assert download.status_code == 200
    assert b"".join(download.streaming_content) == PDF


def test_falha_no_storage_nao_publica(admin_client, edition, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("Falha simulada no armazenamento")

    monkeypatch.setattr(storages["regulations"], "save", fail)
    response = publish(admin_client, edition.pk)
    assert response.status_code == 500
    assert response.json()["error"]["details"] is None
    assert "Falha simulada" not in response.content.decode()
    edition.refresh_from_db()
    assert edition.status == EditionStatus.SETUP
    assert edition.regulation_url == ""
    assert edition.published_at is None


def test_falha_no_banco_remove_pdf(
    admin_client, edition, regulation_storage, monkeypatch
):
    def fail(*args, **kwargs):
        raise DatabaseError("Falha simulada no banco")

    monkeypatch.setattr(Edition, "save", fail)
    with pytest.raises(DatabaseError, match="Falha simulada"):
        publish(admin_client, edition.pk)
    edition.refresh_from_db()
    assert edition.status == EditionStatus.SETUP
    assert not list(regulation_storage.rglob("*.pdf"))


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("restore_catalogs_after_flush")
@pytest.mark.parametrize("lock_during_check", [False, True], ids=["livre", "timeout"])
def test_falha_ao_confirmar_transacao_remove_pdf(
    admin_client, edition, regulation_storage, monkeypatch, caplog, lock_during_check
):
    commit = connection.commit
    start = Event()
    locked = Event()
    release = Event()
    sqlstates = []

    def hold_lock():
        try:
            if start.wait(timeout=10):
                with transaction.atomic():
                    Edition.objects.select_for_update().get(pk=edition.pk)
                    locked.set()
                    release.wait(timeout=8)
        finally:
            connections.close_all()

    def fail():
        patch.setattr(connection, "commit", commit)
        assert len(list(regulation_storage.rglob("*.pdf"))) == 1
        if lock_during_check:
            connection.rollback()
            start.set()
            assert locked.wait(timeout=10)
        raise DatabaseError("Falha simulada no commit")

    def record_query(execute, sql, params, many, context):
        try:
            return execute(sql, params, many, context)
        except OperationalError as error:
            sqlstates.append(error.__cause__.sqlstate)
            raise

    with (
        ThreadPoolExecutor(max_workers=1) as pool,
        monkeypatch.context() as patch,
        connection.execute_wrapper(record_query),
    ):
        future = pool.submit(hold_lock) if lock_during_check else None
        patch.setattr(connection, "commit", fail)
        try:
            with pytest.raises(DatabaseError, match="Falha simulada no commit"):
                publish(admin_client, edition.pk)
        finally:
            release.set()
            start.set()
        assert connection.connection is None
        if future is not None:
            future.result(timeout=10)

    edition.refresh_from_db()
    assert edition.status == EditionStatus.SETUP
    assert edition.regulation_url == ""
    assert edition.published_at is None
    if lock_during_check:
        assert sqlstates == ["55P03"]
        (file,) = regulation_storage.rglob("*.pdf")
        assert file.read_bytes() == PDF
        assert "Não foi possível verificar a referência do edital." in caplog.text
        assert file.stem not in caplog.text
        assert str(UUID(hex=file.stem)) not in caplog.text
    else:
        assert not list(regulation_storage.rglob("*.pdf"))


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("restore_catalogs_after_flush")
def test_confirmacao_perdida_depois_do_commit_preserva_pdf(
    admin_client, edition, monkeypatch
):
    commit = connection.commit
    sessions = []

    def commit_then_disconnect():
        patch.setattr(connection, "commit", commit)
        commit()
        connection.close()
        raise OperationalError("Confirmação do commit perdida")

    def track_connection(execute, sql, params, many, context):
        if "FOR UPDATE" in sql:
            sessions.append(connection.connection)
        return execute(sql, params, many, context)

    with monkeypatch.context() as patch, connection.execute_wrapper(track_connection):
        patch.setattr(connection, "commit", commit_then_disconnect)
        with pytest.raises(OperationalError, match="Confirmação do commit perdida"):
            publish(admin_client, edition.pk)
        assert connection.connection is None
        original, recovered = sessions
        assert recovered is not original

    edition.refresh_from_db()
    assert edition.status == EditionStatus.PUBLISHED
    download = APIClient().get(edition.regulation_url)
    assert download.status_code == 200
    assert b"".join(download.streaming_content) == PDF


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("restore_catalogs_after_flush")
def test_banco_indisponivel_durante_conferencia_preserva_pdf(
    admin_client, edition, regulation_storage, monkeypatch, caplog
):
    def unavailable():
        raise OperationalError("Banco indisponível")

    def fail_commit():
        patch.setattr(connection, "connect", unavailable)
        raise OperationalError("Confirmação do commit perdida")

    with monkeypatch.context() as patch:
        patch.setattr(connection, "commit", fail_commit)
        with pytest.raises(OperationalError, match="Confirmação do commit perdida"):
            publish(admin_client, edition.pk)

    (file,) = regulation_storage.rglob("*.pdf")
    assert file.read_bytes() == PDF
    records = caplog.get_records("call")
    messages = [
        record.getMessage()
        for record in records
        if record.name == "apps.editions.use_cases.publish_regulation"
    ]
    assert messages == ["Não foi possível verificar a referência do edital."]
    assert file.stem not in caplog.text


def test_falha_na_limpeza_nao_expoe_chave(monkeypatch, caplog):
    key = "identificador-do-arquivo.pdf"

    def fail(*args, **kwargs):
        raise OSError(f"Falha ao remover {key}")

    monkeypatch.setattr(storages["regulations"], "delete", fail)
    delete_regulation(key)
    assert "Não foi possível remover o edital" in caplog.text
    assert key not in caplog.text


def test_exige_multipart_e_pdf_obrigatorio(admin_client, edition):
    url = f"/api/admin/editions/{edition.pk}/publish"
    assert (
        admin_client.post(url, {"notice_file": "texto"}, format="json").status_code
        == 415
    )
    response = admin_client.post(url, {}, format="multipart")
    assert response.status_code == 400
    assert "notice_file" in response.json()["error"]["details"]


def test_caso_de_uso_verifica_o_ator(edition, regulation_storage):
    with pytest.raises(NotAdminActor):
        publish_regulation(
            actor=UserFactory(role=UserRole.STUDENT),
            edition=edition,
            notice_file=SimpleUploadedFile("edital.pdf", PDF),
            public_origin="http://testserver",
        )
    assert not list(regulation_storage.rglob("*.pdf"))


def test_caso_de_uso_recusa_transacao_externa_sem_gravar_pdf(
    edition, regulation_storage
):
    actor = UserFactory(role=UserRole.ADMIN)
    with transaction.atomic():
        with pytest.raises(RuntimeError, match="durable atomic block"):
            publish_regulation(
                actor=actor,
                edition=edition,
                notice_file=SimpleUploadedFile("edital.pdf", PDF),
                public_origin="http://testserver",
            )

    edition.refresh_from_db()
    assert edition.status == EditionStatus.SETUP
    assert edition.regulation_url == ""
    assert not list(regulation_storage.rglob("*.pdf"))


def test_caso_de_uso_consulta_o_status_atual(edition, regulation_storage):
    Edition.objects.filter(pk=edition.pk).update(status=EditionStatus.PUBLISHED)
    with pytest.raises(EditionNotInSetup):
        publish_regulation(
            actor=UserFactory(role=UserRole.ADMIN),
            edition=edition,
            notice_file=SimpleUploadedFile("edital.pdf", PDF),
            public_origin="http://testserver",
        )
    assert not list(regulation_storage.rglob("*.pdf"))


@pytest.mark.parametrize(
    ("alteration", "expected"),
    [
        ("courses", {"courses", "challenges"}),
        ("sdgs", {"sdgs", "challenges"}),
        ("challenges", {"challenges"}),
        ("categories", {"categories"}),
        ("criteria", {"criteria", "stage_criteria"}),
    ],
)
def test_cada_pre_condicao_bloqueia_publicacao(
    admin_client, edition, regulation_storage, alteration, expected
):
    if alteration == "courses":
        Course.objects.update(active=False)
    elif alteration == "sdgs":
        sdg = edition.sdg_links.get().sdg
        sdg.active = False
        sdg.save(update_fields=["active"])
    elif alteration == "challenges":
        edition.challenges.update(active=False)
    elif alteration == "categories":
        edition.categories.all().delete()
    elif alteration == "criteria":
        edition.stages.get().criterion_links.all().delete()
        edition.criteria.all().delete()

    response = publish(admin_client, edition.pk)
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "publication_requirements_not_met"
    assert set(error["details"]) == expected
    edition.refresh_from_db()
    assert edition.status == EditionStatus.SETUP
    assert edition.published_at is None
    assert edition.regulation_url == ""
    assert not list(regulation_storage.rglob("*.pdf"))


@pytest.mark.parametrize("include_token", [True, False])
def test_publicacao_com_sessao_real(edition, include_token):
    password = "Senha-para-teste-UC09"
    admin = UserFactory(role=UserRole.ADMIN)
    admin.set_password(password)
    admin.save(update_fields=["password"])
    client = APIClient(enforce_csrf_checks=True)
    csrf = client.get("/api/auth/csrf").json()["csrfToken"]
    login = client.post(
        "/api/auth/sessions/password",
        {"email": admin.email, "password": password},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert login.status_code == 200
    csrf = client.get("/api/auth/csrf").json()["csrfToken"]
    headers = {"HTTP_X_CSRFTOKEN": csrf} if include_token else {}

    response = publish(client, edition.pk, **headers)
    edition.refresh_from_db()
    if include_token:
        assert response.status_code == 200
        assert edition.status == EditionStatus.PUBLISHED
    else:
        assert response.status_code == 403
        assert edition.status == EditionStatus.SETUP


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("restore_catalogs_after_flush")
def test_publicacoes_concorrentes_gravam_apenas_um_edital(edition, regulation_storage):
    admin = UserFactory(role=UserRole.ADMIN)
    start = Barrier(2, timeout=10)

    def attempt():
        client = APIClient()
        client.force_authenticate(admin)
        try:
            start.wait()
            with CaptureQueriesContext(connection) as queries:
                response = publish(client, edition.pk)
            locked_edition = any(
                'FROM "editions_edition"' in query["sql"]
                and "FOR UPDATE" in query["sql"]
                for query in queries
            )
            return response.status_code, response.json(), locked_edition
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt) for _ in range(2)]
        results = [future.result(timeout=20) for future in futures]

    assert sorted(status for status, _, _ in results) == [200, 409]
    assert all(locked for _, _, locked in results)
    responses = {status: body for status, body, _ in results}
    assert responses[409]["error"]["code"] == "edition_not_in_setup"
    edition.refresh_from_db()
    assert edition.status == EditionStatus.PUBLISHED
    assert edition.regulation_url == responses[200]["regulation_url"]
    assert len(list(regulation_storage.rglob("*.pdf"))) == 1
