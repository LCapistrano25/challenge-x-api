from types import SimpleNamespace

import pytest
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.projects import files
from apps.projects.exceptions import StorageUnavailable
from apps.projects.tests.conftest import stored_keys

project = SimpleNamespace(pk=7)
stage = SimpleNamespace(pk=3)


def test_chave_nao_usa_o_nome_do_cliente_nem_caminho_relativo():
    key = files.build_storage_key(project, stage, 2, "pdf")
    assert key.startswith("deliveries/7/3/v2/")
    assert key.endswith(".pdf")
    assert ".." not in key


def test_chaves_do_mesmo_envio_sao_diferentes():
    assert files.build_storage_key(project, stage, 1, "pdf") != files.build_storage_key(
        project, stage, 1, "pdf"
    )


def test_chave_sem_extensao_nao_deixa_ponto():
    assert not files.build_storage_key(project, stage, 1, "").endswith(".")


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("relatorio final.pdf", "relatorio_final.pdf"),
        ("../../etc/passwd", "passwd"),
        ("C:\\Users\\x\\foto.png", "foto.png"),
        ("a/b/c.txt", "c.txt"),
        ("", "arquivo"),
        ("..", "arquivo"),
    ],
)
def test_nome_para_exibir_sai_limpo(name, expected):
    assert files.clean_file_name(name) == expected


def test_nome_longo_e_cortado_e_mantem_a_extensao():
    cleaned = files.clean_file_name("a" * 400 + ".pdf")
    assert len(cleaned) == 255
    assert cleaned.endswith(".pdf")


@pytest.mark.parametrize(
    ("name", "expected"),
    [("a.PDF", "pdf"), ("a.tar.gz", "gz"), ("sem_extensao", ""), (".env", "")],
)
def test_extensao_em_minuscula_sem_ponto(name, expected):
    assert files.get_extension(name) == expected


def test_grava_e_le_de_volta_o_mesmo_conteudo(delivery_storage_root):
    upload = SimpleUploadedFile("a.pdf", b"%PDF-conteudo")
    key = files.build_storage_key(project, stage, 1, "pdf")

    size = files.save_delivery_file(file=upload, key=key)

    assert size == len(b"%PDF-conteudo")
    assert stored_keys(delivery_storage_root) == [key]
    with files.open_delivery_file(key) as stream:
        assert stream.read() == b"%PDF-conteudo"


def test_apagar_remove_o_arquivo_e_e_idempotente(delivery_storage_root):
    key = files.build_storage_key(project, stage, 1, "pdf")
    files.save_delivery_file(file=ContentFile(b"x", name="a.pdf"), key=key)

    files.delete_delivery_file(key)
    files.delete_delivery_file(key)

    assert stored_keys(delivery_storage_root) == []


def test_abrir_arquivo_inexistente_levanta_file_not_found():
    with pytest.raises(FileNotFoundError):
        files.open_delivery_file("deliveries/1/1/v1/nao-existe.pdf")


def test_erro_do_storage_ao_gravar_vira_storage_unavailable(monkeypatch):
    def broken(*args, **kwargs):
        raise OSError("disco cheio")

    monkeypatch.setattr(files.get_delivery_storage().__class__, "save", broken)

    with pytest.raises(StorageUnavailable):
        files.save_delivery_file(file=ContentFile(b"x", name="a.pdf"), key="k/a.pdf")


def test_erro_do_storage_ao_abrir_vira_storage_unavailable(monkeypatch):
    def broken(*args, **kwargs):
        raise PermissionError("sem acesso")

    monkeypatch.setattr(files.get_delivery_storage().__class__, "open", broken)

    with pytest.raises(StorageUnavailable):
        files.open_delivery_file("k/a.pdf")


def test_erro_ao_apagar_nao_levanta(monkeypatch):
    def broken(*args, **kwargs):
        raise OSError("sem acesso")

    monkeypatch.setattr(files.get_delivery_storage().__class__, "delete", broken)

    files.delete_delivery_file("k/a.pdf")
