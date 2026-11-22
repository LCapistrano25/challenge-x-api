"""O verificador de contrato acusa chave extra, chave faltando, enum e nulo."""

from apps.core.tests.contract import mismatches

SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["PENDING", "DEFINITIVE"]},
        "value": {"type": ["string", "null"]},
        "stage": {"$ref": "#/components/schemas/StageRef"},
    },
    "required": ["status", "value", "stage"],
}
STAGE = {"id": 1, "name": "Etapa", "order": 1}


def test_resposta_conforme_nao_tem_divergencia():
    data = {"status": "PENDING", "value": None, "stage": STAGE}
    assert mismatches(data, SCHEMA) == []


def test_acusa_chave_extra_chave_faltando_enum_e_nulo():
    data = {"status": "FINALIZED", "stage": {"id": 1, "name": "E", "position": 1}}
    erros = mismatches(data, SCHEMA)
    assert "$: falta a chave value" in erros
    assert any("FINALIZED" in e for e in erros)
    assert "$.stage: chave fora do contrato: position" in erros
    assert "$.stage: falta a chave order" in erros
    assert mismatches({"status": None, "value": None, "stage": STAGE}, SCHEMA) == [
        "$.status: nulo não permitido"
    ]
