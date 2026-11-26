"""Acesso ao armazenamento dos PDFs de edital."""

import logging

from django.core.files.storage import storages

from apps.editions.exceptions import RegulationStorageUnavailable

logger = logging.getLogger(__name__)


def delete_regulation(key: str) -> None:
    try:
        storages["regulations"].delete(key)
    except OSError:
        logger.error("Não foi possível remover o edital após falha.")


def save_regulation(*, key: str, file) -> str:
    try:
        return storages["regulations"].save(key, file)
    except OSError:
        logger.error("Não foi possível gravar o edital.")
        delete_regulation(key)
        raise RegulationStorageUnavailable() from None


def open_regulation(key: str):
    try:
        return storages["regulations"].open(key, "rb")
    except FileNotFoundError:
        raise
    except OSError:
        logger.error("Não foi possível ler o edital.")
        raise RegulationStorageUnavailable() from None
