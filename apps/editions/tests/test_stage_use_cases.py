from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import NotAdminActor
from apps.accounts.factories import UserFactory
from apps.editions.enums import EditionStatus, FieldKind, StageKind
from apps.editions.exceptions import EditionClosed, EditionPublished, StagePositionTaken
from apps.editions.factories import (
    EditionFactory,
    StageCriterionFactory,
    StageFactory,
    StageSubmissionFieldFactory,
)
from apps.editions.models import Stage, StageSubmissionField
from apps.editions.use_cases.create_stage import create_stage
from apps.editions.use_cases.update_stage import update_stage
from apps.projects.factories import SubmissionItemFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin():
    return UserFactory(role=UserRole.ADMIN)


@pytest.fixture
def stage_data():
    start = timezone.now()
    return {
        "order": 1,
        "name": "Etapa",
        "kind": StageKind.SUBMISSION,
        "starts_at": start,
        "ends_at": start + timedelta(days=1),
        "evaluation_ends_at": start + timedelta(days=2),
        "max_score": Decimal("3.00"),
    }


def test_cria_etapa_com_campos_e_defaults(admin, stage_data):
    edition = EditionFactory()
    stage = create_stage(
        actor=admin,
        edition=edition,
        **stage_data,
        submission_fields=[
            {"kind": FieldKind.LINK},
            {"kind": FieldKind.FILE, "max_size_mb": 32767},
        ],
    )
    stage.refresh_from_db()
    assert stage.edition_id == edition.pk
    assert stage.max_score == Decimal("3")
    assert stage.min_evaluations == 1
    assert list(
        stage.submission_fields.order_by("pk").values_list(
            "kind", "label", "required", "formats", "max_size_mb"
        )
    ) == [("LINK", "", True, "", None), ("FILE", "", True, "", 32767)]


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"name": None}, "name"),
        ({"name": "x" * 101}, "name"),
        ({"order": 0}, "order"),
        ({"order": 32768}, "order"),
        ({"min_evaluations": 0}, "min_evaluations"),
        ({"min_evaluations": 32768}, "min_evaluations"),
        ({"starts_at": None}, "starts_at"),
        ({"ends_at": None}, "ends_at"),
        ({"kind": None}, "kind"),
        ({"scored": None}, "scored"),
        ({"max_score": None}, "max_score"),
        ({"max_score": Decimal("0")}, "max_score"),
        ({"max_score": Decimal("0.001")}, "max_score"),
        ({"max_score": Decimal("NaN")}, "max_score"),
        ({"scored": False}, "max_score"),
        ({"evaluation_ends_at": None}, "evaluation_ends_at"),
        ({"kind": StageKind.FINAL}, "scored"),
        ({"kind": StageKind.FORMATION}, "scored"),
        ({"submission_fields": None}, "submission_fields"),
        (
            {"submission_fields": [{"kind": "FILE", "max_size_mb": 32768}]},
            "submission_fields",
        ),
        (
            {"submission_fields": [{"kind": "LINK", "formats": "pdf"}]},
            "submission_fields",
        ),
        (
            {"submission_fields": [{"kind": "CANVAS", "max_size_mb": 1}]},
            "submission_fields",
        ),
        (
            {"submission_fields": [{"kind": "SWOT", "formats": "pdf"}]},
            "submission_fields",
        ),
        ({"submission_fields": [{"kind": "LINK", "id": 1}]}, "submission_fields"),
    ],
)
def test_cria_recusa_dados_invalidos_sem_gravar(admin, stage_data, overrides, field):
    edition = EditionFactory()
    with pytest.raises(ValidationError) as caught:
        create_stage(actor=admin, edition=edition, **(stage_data | overrides))
    assert field in caught.value.message_dict
    assert not Stage.objects.filter(edition=edition).exists()
    assert not StageSubmissionField.objects.filter(stage__edition=edition).exists()


@pytest.mark.parametrize("field", ["starts_at", "ends_at", "evaluation_ends_at"])
def test_cria_recusa_data_sem_fuso(admin, stage_data, field):
    edition = EditionFactory()
    stage_data[field] = stage_data[field].replace(tzinfo=None)
    with pytest.raises(ValidationError) as caught:
        create_stage(actor=admin, edition=edition, **stage_data)
    assert field in caught.value.message_dict
    assert not edition.stages.exists()


@pytest.mark.parametrize("field", ["ends_at", "evaluation_ends_at"])
def test_cria_recusa_data_igual_ao_limite(admin, stage_data, field):
    edition = EditionFactory()
    previous = "starts_at" if field == "ends_at" else "ends_at"
    stage_data[field] = stage_data[previous]
    with pytest.raises(ValidationError) as caught:
        create_stage(actor=admin, edition=edition, **stage_data)
    assert field in caught.value.message_dict
    assert not edition.stages.exists()


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (EditionStatus.PUBLISHED, EditionPublished),
        (EditionStatus.CLOSED, EditionClosed),
    ],
)
def test_cria_relendo_estado_da_edicao(admin, stage_data, status, error):
    edition = EditionFactory()
    type(edition).objects.filter(pk=edition.pk).update(status=status)
    with pytest.raises(error):
        create_stage(actor=admin, edition=edition, **stage_data)
    assert not edition.stages.exists()


@pytest.mark.parametrize("role", [None, UserRole.STUDENT])
def test_cria_recusa_ator_sem_permissao(stage_data, role):
    edition = EditionFactory()
    actor = None if role is None else UserFactory(role=role)
    with pytest.raises(NotAdminActor):
        create_stage(actor=actor, edition=edition, **stage_data)
    assert not edition.stages.exists()


@pytest.mark.parametrize("skip_precheck", [False, True])
def test_cria_traduz_posicao_duplicada(admin, stage_data, monkeypatch, skip_precheck):
    stage = StageFactory(order=stage_data["order"])
    if skip_precheck:
        monkeypatch.setattr(
            "apps.editions.use_cases.create_stage.ensure_stage_position_is_free",
            lambda stage: None,
        )
    with pytest.raises(StagePositionTaken):
        create_stage(actor=admin, edition=stage.edition, **stage_data)
    assert list(stage.edition.stages.values_list("pk", flat=True)) == [stage.pk]


def test_soma_parcial_pode_chegar_a_dez_mas_nao_ultrapassar(admin, stage_data):
    edition = EditionFactory()
    StageFactory(edition=edition, order=2, max_score=Decimal("7"))
    create_stage(actor=admin, edition=edition, **stage_data)
    with pytest.raises(ValidationError, match="10 pontos"):
        create_stage(actor=admin, edition=edition, **(stage_data | {"order": 3}))
    assert edition.stages.count() == 2


def test_so_uma_formacao_por_edicao(admin, stage_data):
    edition = EditionFactory()
    formation = stage_data | dict(
        kind=StageKind.FORMATION, scored=False, max_score=None
    )
    create_stage(actor=admin, edition=edition, **formation)
    with pytest.raises(ValidationError) as caught:
        create_stage(actor=admin, edition=edition, **(formation | {"order": 2}))
    assert "kind" in caught.value.message_dict
    assert edition.stages.count() == 1
    create_stage(actor=admin, edition=EditionFactory(), **formation)


def test_atualiza_etapa_e_substitui_campos_preservando_valores_omitidos(admin):
    stage = StageFactory()
    known = StageSubmissionFieldFactory(
        stage=stage, kind=FieldKind.FILE, formats="pdf", max_size_mb=4, required=False
    )
    removed = StageSubmissionFieldFactory(stage=stage)
    changed = update_stage(
        actor=admin,
        stage=stage,
        name="Revisado",
        submission_fields=[
            {"id": known.pk, "kind": "FILE", "label": "Outro"},
            {"kind": "SWOT"},
        ],
    )
    changed.refresh_from_db()
    known.refresh_from_db()
    assert changed.name == "Revisado"
    assert (known.formats, known.max_size_mb, known.required, known.label) == (
        "pdf",
        4,
        False,
        "Outro",
    )
    assert not StageSubmissionField.objects.filter(pk=removed.pk).exists()
    assert changed.submission_fields.get(kind="SWOT").required is True


def snapshot(stage):
    return (
        Stage.objects.values().get(pk=stage.pk),
        list(stage.submission_fields.order_by("pk").values()),
    )


def test_patch_omite_campos_ou_limpa_explicitamente(admin):
    stage = StageFactory()
    field = StageSubmissionFieldFactory(stage=stage)
    update_stage(
        actor=admin, stage=stage, scored=False, max_score=None, evaluation_ends_at=None
    )
    stage.refresh_from_db()
    assert (stage.scored, stage.max_score, stage.evaluation_ends_at) == (
        False,
        None,
        None,
    )
    assert stage.submission_fields.filter(pk=field.pk).exists()
    update_stage(actor=admin, stage=stage, submission_fields=[])
    assert not stage.submission_fields.exists()


def test_patch_de_pontuacao_nao_conta_a_propria_etapa_duas_vezes(admin):
    stage = StageFactory(max_score=Decimal("4"))
    StageFactory(edition=stage.edition, max_score=Decimal("5"))
    update_stage(actor=admin, stage=stage, max_score=Decimal("5"))
    expected = snapshot(stage)
    with pytest.raises(ValidationError, match="10 pontos"):
        update_stage(actor=admin, stage=stage, max_score=Decimal("6"))
    assert snapshot(stage) == expected


@pytest.mark.parametrize(
    "scenario", ["duplicate", "foreign", "kind_with_options", "null"]
)
def test_patch_invalido_nao_altera_etapa_nem_campos(admin, scenario):
    stage = StageFactory()
    field = StageSubmissionFieldFactory(stage=stage, kind="FILE", formats="pdf")
    other = StageSubmissionFieldFactory()
    payloads = {
        "duplicate": [{"id": field.pk, "kind": "FILE"}] * 2,
        "foreign": [{"id": other.pk, "kind": "LINK"}],
        "kind_with_options": [{"id": field.pk, "kind": "LINK"}],
        "null": None,
    }
    expected = snapshot(stage)
    with pytest.raises(ValidationError):
        update_stage(
            actor=admin,
            stage=stage,
            name="Revisado",
            submission_fields=payloads[scenario],
        )
    assert snapshot(stage) == expected


def test_patch_permite_trocar_kind_sem_historico_e_limpar_opcoes(admin):
    stage = StageFactory()
    field = StageSubmissionFieldFactory(
        stage=stage, kind="FILE", formats="pdf", max_size_mb=1
    )
    update_stage(
        actor=admin,
        stage=stage,
        submission_fields=[
            {"id": field.pk, "kind": "LINK", "formats": None, "max_size_mb": None}
        ],
    )
    field.refresh_from_db()
    assert (field.kind, field.formats, field.max_size_mb) == ("LINK", "", None)


@pytest.mark.parametrize("remove", [True, False])
def test_patch_protege_campo_usado_em_entrega(admin, remove):
    field = StageSubmissionFieldFactory(kind="LINK")
    SubmissionItemFactory(field=field)
    expected = snapshot(field.stage)
    payload = [] if remove else [{"id": field.pk, "kind": "FILE"}]
    with pytest.raises(ValidationError, match="entrega"):
        update_stage(
            actor=admin, stage=field.stage, name="Revisado", submission_fields=payload
        )
    assert snapshot(field.stage) == expected


def test_patch_bloqueia_desativar_pontuacao_com_criterio(admin):
    stage = StageFactory()
    link = StageCriterionFactory(stage=stage)
    expected = snapshot(stage)
    with pytest.raises(ValidationError, match="critério"):
        update_stage(actor=admin, stage=stage, scored=False, max_score=None)
    assert snapshot(stage) == expected
    assert stage.criterion_links.filter(pk=link.pk).exists()


def test_patch_bloqueia_segunda_formacao(admin):
    stage = StageFactory(scored=False, max_score=None)
    StageFactory(edition=stage.edition, formation=True)
    expected = snapshot(stage)
    with pytest.raises(ValidationError, match="formação"):
        update_stage(actor=admin, stage=stage, kind="FORMATION")
    assert snapshot(stage) == expected


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (EditionStatus.PUBLISHED, EditionPublished),
        (EditionStatus.CLOSED, EditionClosed),
    ],
)
def test_patch_valida_estado_relido(admin, status, error):
    stage = StageFactory()
    type(stage.edition).objects.filter(pk=stage.edition_id).update(status=status)
    expected = snapshot(stage)
    with pytest.raises(error):
        update_stage(actor=admin, stage=stage, name="Revisado")
    assert snapshot(stage) == expected


@pytest.mark.parametrize(
    "changes",
    [
        {"scored": False},
        {"max_score": None},
        {"name": None},
        {"kind": "FINAL"},
        {"starts_at": None},
        {"ends_at": None},
    ],
)
def test_patch_valida_estado_final_e_nao_persiste(admin, changes):
    stage = StageFactory()
    expected = snapshot(stage)
    with pytest.raises(ValidationError):
        update_stage(actor=admin, stage=stage, **changes)
    assert snapshot(stage) == expected


@pytest.mark.parametrize("skip_precheck", [False, True])
def test_patch_posicao_conflitante(admin, monkeypatch, skip_precheck):
    stage = StageFactory()
    other = StageFactory(edition=stage.edition)
    if skip_precheck:
        monkeypatch.setattr(
            "apps.editions.use_cases.update_stage.ensure_stage_position_is_free",
            lambda stage: None,
        )
    StageSubmissionFieldFactory(stage=stage)
    expected = snapshot(stage)
    with pytest.raises(StagePositionTaken):
        update_stage(
            actor=admin,
            stage=stage,
            order=other.order,
            submission_fields=[{"kind": "FILE"}],
        )
    assert snapshot(stage) == expected


def test_patch_recusa_ator_sem_permissao():
    stage = StageFactory()
    expected = snapshot(stage)
    with pytest.raises(NotAdminActor):
        update_stage(actor=None, stage=stage, name="Revisado")
    assert snapshot(stage) == expected
