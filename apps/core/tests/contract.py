"""Confere uma resposta da API contra um schema do contrato (docs/api/openapi.yaml).

O contrato é a autoridade da interface: o teste lê o schema do próprio YAML, em vez
de repetir no teste os nomes que o código usa.

shortcut: confere chaves, enums e nulos, não tipos nem formatos; trocar pelo teste
de contrato geral (I-04) quando ele existir.
"""

from functools import cache
from pathlib import Path

import yaml

CONTRACT = Path(__file__).resolve().parents[3] / "docs" / "api" / "openapi.yaml"


@cache
def _spec():
    return yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))


def schema(name: str) -> dict:
    return _spec()["components"]["schemas"][name]


def _resolve(node: dict) -> dict:
    while "$ref" in node:
        node = schema(node["$ref"].rsplit("/", 1)[-1])
    return node


def mismatches(data, node: dict, path: str = "$") -> list[str]:
    """Lista as divergências entre `data` e o schema; vazia quando conforme."""
    node = _resolve(node)
    if "oneOf" in node or "anyOf" in node:
        options = node.get("oneOf") or node["anyOf"]
        found = [mismatches(data, option, path) for option in options]
        return [] if any(not f for f in found) else min(found, key=len)
    kinds = node.get("type")
    kinds = kinds if isinstance(kinds, list) else [kinds]
    if data is None:
        return [] if "null" in kinds else [f"{path}: nulo não permitido"]
    if "enum" in node and data not in node["enum"]:
        return [f"{path}: {data!r} fora de {node['enum']}"]
    if "object" in kinds and isinstance(data, dict):
        props = node.get("properties", {})
        errors = [
            f"{path}: chave fora do contrato: {k}" for k in data if k not in props
        ]
        errors += [
            f"{path}: falta a chave {k}"
            for k in node.get("required", [])
            if k not in data
        ]
        for key, value in data.items():
            if key in props:
                errors += mismatches(value, props[key], f"{path}.{key}")
        return errors
    if "array" in kinds and isinstance(data, list):
        return [
            e
            for i, item in enumerate(data)
            for e in mismatches(item, node["items"], f"{path}[{i}]")
        ]
    return []
