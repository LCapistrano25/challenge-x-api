"""UC09 — Publicar o edital e tornar a edição visível (RF09, INT-01, INT-02)."""

import logging
from uuid import uuid4

from django.core.files.uploadedfile import UploadedFile
from django.db import DEFAULT_DB_ALIAS, Error, connections, transaction
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.enums import EditionStatus
from apps.editions.exceptions import RegulationStorageUnavailable
from apps.editions.models import Edition
from apps.editions.regulation_files import delete_regulation, save_regulation
from apps.editions.rules import ensure_edition_ready_for_publication

logger = logging.getLogger(__name__)
REGULATION_REFERENCE_LOCK_TIMEOUT = "2s"


def publish_regulation(
    *, actor: User, edition: Edition, notice_file: UploadedFile, public_origin: str
) -> Edition:
    """Publica o edital e torna a edição visível (UC09, RF09)."""
    ensure_actor_is_admin(actor)
    stored_key = None
    saved = False
    committed = False
    try:
        # O commit precisa ocorrer aqui para que a limpeza observe falhas.
        # O bloco durável recusa chamadas dentro de outra transação.
        with transaction.atomic(durable=True):
            edition = Edition.objects.select_for_update().get(pk=edition.pk)
            ensure_edition_ready_for_publication(edition)

            token = uuid4()
            key = f"{edition.pk}/{token.hex}.pdf"
            path = reverse(
                "edition-regulation",
                kwargs={"edition_id": edition.pk, "token": token},
            )
            stored_key = save_regulation(key=key, file=notice_file)
            if stored_key != key:
                raise RegulationStorageUnavailable()
            edition.regulation_url = f"{public_origin}{path}"
            edition.status = EditionStatus.PUBLISHED
            edition.published_at = timezone.now()
            edition.save(
                update_fields=["regulation_url", "status", "published_at", "updated_at"]
            )
            saved = True
        committed = True
    finally:
        if not committed and stored_key is not None:
            if not saved or _can_delete_after_commit_failure(edition.pk, path):
                delete_regulation(stored_key)
    return edition


def _can_delete_after_commit_failure(edition_id: int, path: str) -> bool:
    """Preserva o PDF se a confirmação do commit tiver se perdido."""
    connection = connections[DEFAULT_DB_ALIAS]
    if connection.in_atomic_block:
        return False
    try:
        connection.close()
        try:
            with transaction.atomic(using=connection.alias):
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SET LOCAL lock_timeout = %s",
                        [REGULATION_REFERENCE_LOCK_TIMEOUT],
                    )
                editions = Edition.objects.using(connection.alias)
                # Aguarda a transação anterior liberar a edição antes de ler a URL.
                editions.select_for_update().filter(pk=edition_id).exists()
                return not editions.filter(regulation_url__endswith=path).exists()
        finally:
            connection.close()
    except Error:
        logger.warning("Não foi possível verificar a referência do edital.")
        return False
