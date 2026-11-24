"""Armazenamento dos arquivos da entrega (RF31).

Só funções sobre o storage privado `deliveries`: nenhuma regra de negócio. O
storage não gera URL; o arquivo só sai pela API, depois de checada a permissão.
"""

import logging
import os
import uuid

from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import storages
from django.utils.text import get_valid_filename

from apps.projects.exceptions import StorageUnavailable

logger = logging.getLogger(__name__)

STORAGE_ALIAS = "deliveries"

# Nunca entram, nem que o campo da etapa deixe os formatos em branco.
BLOCKED_EXTENSIONS = frozenset(
    {"exe", "bat", "cmd", "com", "msi", "sh", "js", "vbs", "ps1", "jar", "scr", "dll"}
)

# Começo do arquivo por extensão. Extensão fora da tabela vale só pelo nome.
_ZIP = (b"PK\x03\x04",)
SIGNATURES = {
    "pdf": (b"%PDF",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "zip": _ZIP,
    "docx": _ZIP,
    "xlsx": _ZIP,
    "pptx": _ZIP,
}
SIGNATURE_SIZE = max(len(s) for prefixes in SIGNATURES.values() for s in prefixes)

MAX_FILE_NAME_LENGTH = 255


def get_extension(name: str) -> str:
    """Extensão em minúscula e sem ponto; vazia se o nome não tem."""
    return os.path.splitext(name or "")[1].lstrip(".").lower()


def clean_file_name(name: str) -> str:
    """Nome para exibir e baixar: sem caminho, sem caracteres perigosos, até 255."""
    base = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    try:
        cleaned = get_valid_filename(base)
    except SuspiciousFileOperation:
        cleaned = "arquivo"
    if len(cleaned) > MAX_FILE_NAME_LENGTH:
        stem, ext = os.path.splitext(cleaned)
        cleaned = stem[: MAX_FILE_NAME_LENGTH - len(ext)] + ext
    return cleaned


def build_storage_key(project, stage, number: int, extension: str) -> str:
    """Chave gerada pelo servidor; o nome enviado pelo cliente nunca entra nela."""
    ext = f".{extension}" if extension else ""
    return f"deliveries/{project.pk}/{stage.pk}/v{number}/{uuid.uuid4().hex}{ext}"


def get_delivery_storage():
    return storages[STORAGE_ALIAS]


def save_delivery_file(*, file, key: str) -> int:
    """Grava o arquivo na chave e devolve o tamanho em bytes."""
    try:
        get_delivery_storage().save(key, file)
    except OSError as error:
        raise StorageUnavailable() from error
    return file.size


def delete_delivery_file(key: str) -> None:
    """Apaga o arquivo de uma tentativa que falhou; não mascara o erro original."""
    try:
        get_delivery_storage().delete(key)
    except OSError:
        logger.exception("Não foi possível apagar o arquivo órfão %s", key)


def open_delivery_file(key: str):
    """Abre o arquivo para leitura. FileNotFoundError sobe se ele não existe."""
    try:
        return get_delivery_storage().open(key, "rb")
    except FileNotFoundError:
        raise
    except OSError as error:
        raise StorageUnavailable() from error
