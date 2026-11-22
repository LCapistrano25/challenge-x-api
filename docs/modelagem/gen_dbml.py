"""Gera docs/modelagem/desafio-x.dbml a partir das models. Edite as models, nunca o DBML.

Rode da raiz do projeto: uv run python docs/modelagem/gen_dbml.py
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.apps import apps  # noqa: E402
from django.conf import settings  # noqa: E402
from django.db import connection, models  # noqa: E402

# Cor do cabeçalho por app, para o diagrama no DrawDB.
COLORS = {
    "core": "#175e7a",
    "accounts": "#1e6b52",
    "editions": "#8a5a00",
    "teams": "#6b2d7a",
    "projects": "#7a1f2b",
    "evaluations": "#2b4a8a",
    "results": "#4a6b1e",
    "notifications": "#555555",
}
ON_DELETE = {
    models.CASCADE: "cascade",
    models.PROTECT: "restrict",
    models.RESTRICT: "restrict",
    models.SET_NULL: "set null",
    models.SET_DEFAULT: "set default",
    models.DO_NOTHING: "no action",
}
OPS = {"exact": "=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<=", "in": "in"}


def quote(text) -> str:
    text = str(text).replace("\\", "\\\\")
    if "\n" in text:
        return "'''" + text.replace("'''", "\\'''") + "'''"
    return "'" + text.replace("'", "\\'") + "'"


def render(node) -> str:
    """Q de uma constraint em texto legível: (scored = False OR max_score > 0)."""
    if isinstance(node, models.Q):
        parts = [render(child) for child in node.children]
        text = f" {node.connector} ".join(parts)
        text = f"({text})" if len(parts) > 1 else text
        return f"NOT {text}" if node.negated else text
    lookup, value = node
    field, _, op = lookup.rpartition("__")
    if op not in OPS and op != "isnull":
        field, op = lookup, "exact"
    if isinstance(value, models.F):
        value = value.name
    elif isinstance(value, list | tuple):
        value = [getattr(v, "value", v) for v in value]
    elif isinstance(value, str):
        value = repr(getattr(value, "value", value))
    if op == "isnull":
        return f"{field} is {'null' if value else 'not null'}"
    return f"{field} {OPS[op]} {value}"


def project_apps():
    labels = [a.split(".")[1] for a in settings.INSTALLED_APPS if a.startswith("apps.")]
    return [apps.get_app_config(label) for label in labels]


def links_project_only(model) -> bool:
    """Tabela automática de M2M entra só se ligar duas tabelas do projeto."""
    return all(
        f.related_model._meta.app_label in COLORS
        for f in model._meta.local_fields
        if f.is_relation
    )


def column_type(field) -> str:
    if field.choices and isinstance(field, models.CharField):
        return f"{field.model._meta.db_table}_{field.column}"
    db_type = field.db_type(connection) or "integer"
    db_type = db_type.replace("timestamp with time zone", "timestamptz")
    db_type = db_type.replace(", ", ",")
    return f'"{db_type}"' if " " in db_type else db_type


# Palavras do DBML que não podem ser nome de coluna sem aspas.
RESERVED = {"order", "note", "indexes", "ref", "enum", "table", "project"}


def name(column) -> str:
    return f'"{column}"' if column in RESERVED else column


def default_of(field):
    if not field.has_default() or callable(field.default):
        return None
    value = field.default
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    return quote(value)


def column(field) -> str:
    opts = []
    if field.primary_key:
        opts.append("pk")
        if isinstance(field, models.AutoField | models.BigAutoField):
            opts.append("increment")
    elif not field.null:
        opts.append("not null")
    if field.unique and not field.primary_key:
        opts.append("unique")
    default = default_of(field)
    if default is not None:
        opts.append(f"default: {default}")
    # Só o verbose_name escrito na model; o automático repete o nome da coluna.
    note = str(field.verbose_name)
    if note == field.name.replace("_", " "):
        note = ""
    if field.choices and not isinstance(field, models.CharField):
        note += " (valores: " + ", ".join(str(v) for v, _ in field.choices) + ")"
    if field.has_default() and callable(field.default):
        note += f" (padrão: {field.default.__name__})"
    if note.strip():
        opts.append(f"note: {quote(note.strip())}")
    spec = f" [ {', '.join(opts)} ]" if opts else ""
    return f"\t{name(field.column)} {column_type(field)}{spec}"


def indexes(model) -> list[str]:
    opts = model._meta
    lines = []
    for fields in opts.unique_together:
        cols = ", ".join(name(opts.get_field(f).column) for f in fields)
        lines.append(f"\t\t({cols}) [ unique ]")
    for c in opts.constraints:
        if isinstance(c, models.UniqueConstraint) and c.fields:
            cols = ", ".join(name(opts.get_field(f).column) for f in c.fields)
            extra = (
                f", note: {quote('onde ' + render(c.condition))}" if c.condition else ""
            )
            lines.append(f"\t\t({cols}) [ unique, name: {quote(c.name)}{extra} ]")
    for index in opts.indexes:
        cols = ", ".join(
            name(opts.get_field(f.lstrip("-")).column) for f in index.fields
        )
        lines.append(f"\t\t({cols}) [ name: {quote(index.name)} ]")
    return lines


def table(model, color) -> str:
    opts = model._meta
    lines = [f"Table {opts.db_table} [headercolor: {color}] {{"]
    lines += [column(f) for f in opts.local_fields]
    idx = indexes(model)
    if idx:
        lines += ["", "\tindexes {", *idx, "\t}"]
    notes = [f"{opts.verbose_name} ({opts.label})"]
    notes += [
        f"CHECK {c.name}: {render(c.condition)}"
        for c in opts.constraints
        if isinstance(c, models.CheckConstraint)
    ]
    lines += ["", f"\tNote: {quote(chr(10).join(notes))}", "}"]
    return "\n".join(lines)


def enums(model) -> list[str]:
    out = []
    for field in model._meta.local_fields:
        if field.choices and isinstance(field, models.CharField):
            values = "\n".join(
                f"\t{value} [ note: {quote(label)} ]" for value, label in field.choices
            )
            out.append(f"Enum {column_type(field)} {{\n{values}\n}}")
    return out


def refs(model, known) -> list[str]:
    out = []
    for field in model._meta.local_fields:
        if not (field.many_to_one or field.one_to_one):
            continue
        target = field.related_model._meta
        if target.db_table not in known:
            continue
        kind = "-" if field.one_to_one else ">"
        action = ON_DELETE.get(field.remote_field.on_delete, "no action")
        out.append(
            f"Ref: {model._meta.db_table}.{name(field.column)} {kind} "
            f"{target.db_table}.{name(field.target_field.column)} [ delete: {action} ]"
        )
    return out


def main() -> None:
    selected = [
        (config, model)
        for config in project_apps()
        for model in config.get_models(include_auto_created=True)
        if not model._meta.auto_created or links_project_only(model)
    ]
    known = {model._meta.db_table for _, model in selected}
    parts = [
        "// Gerado por docs/modelagem/gen_dbml.py a partir das models. Não edite à mão:",
        "// mude a model, crie a migration e rode o gerador (o CI compara).",
        "",
        "Project desafio_x {",
        "\tdatabase_type: 'PostgreSQL'",
        "\tNote: 'Plataforma Desafio X (UniCatólica). Tabelas com os nomes reais do banco.'",
        "}",
    ]
    for config, model in selected:
        parts += ["", table(model, COLORS.get(config.label, "#555555"))]
    enum_blocks = [e for _, model in selected for e in enums(model)]
    ref_lines = [r for _, model in selected for r in refs(model, known)]
    for block in enum_blocks:
        parts += ["", block]
    parts += ["", *ref_lines, ""]
    out = Path(__file__).with_name("desafio-x.dbml")
    out.write_text("\n".join(parts), encoding="utf-8", newline="\n")
    print(f"tabelas: {len(selected)} enums: {len(enum_blocks)} refs: {len(ref_lines)}")


if __name__ == "__main__":
    main()
