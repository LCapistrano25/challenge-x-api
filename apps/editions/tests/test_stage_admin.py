import pytest
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.factories import UserFactory
from apps.editions.enums import EditionStatus
from apps.editions.factories import (
    EditionFactory,
    StageCriterionFactory,
    StageFactory,
    StageSubmissionFieldFactory,
)
from apps.editions.models import Stage, StageSubmissionField
from apps.projects.factories import SubmissionItemFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(client):
    client.force_login(
        UserFactory(role=UserRole.ADMIN, is_staff=True, is_superuser=True)
    )
    return client


def stage_form(stage, *, field=None):
    body = {
        "edition": stage.edition_id,
        "order": stage.order,
        "kind": stage.kind,
        "name": stage.name,
        "scored": "on" if stage.scored else "",
        "max_score": "" if stage.max_score is None else str(stage.max_score),
        "min_evaluations": stage.min_evaluations,
        "criterion_links-TOTAL_FORMS": 0,
        "criterion_links-INITIAL_FORMS": 0,
        "submission_fields-TOTAL_FORMS": int(field is not None),
        "submission_fields-INITIAL_FORMS": int(field is not None),
    }
    for name in ("starts_at", "ends_at", "evaluation_ends_at"):
        value = getattr(stage, name)
        local = timezone.localtime(value) if value is not None else None
        body[f"{name}_0"] = local.date().isoformat() if local is not None else ""
        body[f"{name}_1"] = local.time().isoformat() if local is not None else ""
    if field is not None:
        body.update(
            {
                "submission_fields-0-id": field.pk,
                "submission_fields-0-stage": stage.pk,
                "submission_fields-0-kind": field.kind,
                "submission_fields-0-label": field.label,
                "submission_fields-0-required": "on" if field.required else "",
                "submission_fields-0-formats": field.formats,
                "submission_fields-0-max_size_mb": field.max_size_mb or "",
            }
        )
    return body


def test_admin_cria_formacao_mas_recusa_segunda(admin_client):
    edition = EditionFactory()
    first = StageFactory.build(edition=edition, order=1, formation=True)
    url = reverse("admin:editions_stage_add")
    assert admin_client.post(url, stage_form(first)).status_code == 302
    second = StageFactory.build(edition=edition, order=2, formation=True)
    response = admin_client.post(url, stage_form(second))
    assert response.status_code == 200
    assert "formação" in str(response.context["adminform"].form.errors)
    assert list(
        Stage.objects.filter(edition=edition)
        .order_by("order")
        .values_list("order", flat=True)
    ) == [1]


def test_admin_pode_alterar_etapa_publicada(admin_client):
    stage = StageFactory(edition__status=EditionStatus.PUBLISHED)
    url = reverse("admin:editions_stage_change", args=[stage.pk])
    response = admin_client.post(url, stage_form(stage) | {"name": "Revisada"})
    assert response.status_code == 302
    stage.refresh_from_db()
    assert stage.name == "Revisada"


@pytest.mark.parametrize("bulk", [False, True])
@pytest.mark.parametrize("closed", [False, True])
def test_admin_exclui_etapa_so_em_edicao_nao_encerrada(admin_client, bulk, closed):
    stage = StageFactory(
        edition__status=EditionStatus.CLOSED if closed else EditionStatus.PUBLISHED
    )
    other = StageFactory()
    if bulk:
        response = admin_client.post(
            reverse("admin:editions_stage_changelist"),
            {
                "action": "delete_selected",
                ACTION_CHECKBOX_NAME: [stage.pk, other.pk],
                "post": "yes",
            },
        )
        assert Stage.objects.filter(pk=other.pk).exists() == closed
    else:
        response = admin_client.post(
            reverse("admin:editions_stage_delete", args=[stage.pk]), {"post": "yes"}
        )
    assert response.status_code == (403 if closed else 302)
    assert Stage.objects.filter(pk=stage.pk).exists() == closed


@pytest.mark.parametrize("status", [EditionStatus.PUBLISHED, EditionStatus.CLOSED])
def test_exclusao_de_campo_pelo_inline(admin_client, status):
    field = StageSubmissionFieldFactory(stage__edition__status=status)
    stage = field.stage
    response = admin_client.post(
        reverse("admin:editions_stage_change", args=[stage.pk]),
        stage_form(stage, field=field) | {"submission_fields-0-DELETE": "on"},
    )
    if status == EditionStatus.PUBLISHED:
        assert response.status_code == 302
        assert not StageSubmissionField.objects.filter(pk=field.pk).exists()
    else:
        assert response.status_code == 200
        assert StageSubmissionField.objects.filter(pk=field.pk).exists()


def test_admin_mostra_erro_em_campo_link_com_opcao_de_arquivo(admin_client):
    field = StageSubmissionFieldFactory(kind="LINK")
    stage = field.stage
    response = admin_client.post(
        reverse("admin:editions_stage_change", args=[stage.pk]),
        stage_form(stage, field=field) | {"submission_fields-0-formats": "pdf"},
    )
    assert response.status_code == 200
    field.refresh_from_db()
    assert field.formats == ""


def test_full_clean_bloqueia_desativar_pontuacao_com_criterio():
    stage = StageFactory()
    StageCriterionFactory(stage=stage)
    stage.scored = False
    stage.max_score = None
    with pytest.raises(ValidationError, match="critérios"):
        stage.full_clean()
    stage.refresh_from_db()
    assert stage.scored is True


def test_full_clean_bloqueia_trocar_tipo_de_campo_usado():
    field = StageSubmissionFieldFactory(kind="LINK")
    SubmissionItemFactory(field=field)
    field.kind = "FILE"
    with pytest.raises(ValidationError, match="entrega"):
        field.full_clean()
    field.refresh_from_db()
    assert field.kind == "LINK"
