import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.editions.enums import FieldKind
from apps.editions.factories import (
    CategoryFactory,
    ChallengeFactory,
    EditionFactory,
    StageFactory,
)
from apps.projects.factories import (
    ProjectFactory,
    SubmissionFactory,
    SubmissionItemFactory,
    SubmissionReceiptFactory,
    SubmissionVersionFactory,
)
from apps.projects.models import Project, Submission
from apps.teams.factories import TeamFactory

pytestmark = pytest.mark.django_db


# Unicidades


def test_titulo_unico_na_edicao_sem_diferenciar_maiusculas():
    projeto = ProjectFactory(title="Água Limpa")
    equipe = TeamFactory(edition=projeto.edition)
    with pytest.raises(IntegrityError):
        ProjectFactory(team=equipe, title="ÁGUA LIMPA")


def test_mesmo_titulo_em_outra_edicao_pode():
    ProjectFactory(title="Água Limpa")
    assert ProjectFactory(title="Água Limpa").pk


def test_um_projeto_por_equipe():
    projeto = ProjectFactory()
    with pytest.raises(IntegrityError):
        ProjectFactory(team=projeto.team)


def test_uma_entrega_por_etapa():
    entrega = SubmissionFactory()
    with pytest.raises(IntegrityError):
        SubmissionFactory(project=entrega.project, stage=entrega.stage)


def test_numero_da_versao_unico_na_entrega():
    versao = SubmissionVersionFactory(number=1)
    with pytest.raises(IntegrityError):
        SubmissionVersionFactory(submission=versao.submission, number=1)


def test_numero_da_versao_comeca_em_1():
    with pytest.raises(IntegrityError):
        SubmissionVersionFactory(number=0)


def test_um_comprovante_por_versao():
    comprovante = SubmissionReceiptFactory()
    with pytest.raises(IntegrityError):
        SubmissionReceiptFactory(version=comprovante.version)


def test_comprovante_gera_codigo_de_verificacao_unico():
    assert SubmissionReceiptFactory().verification_code != (
        SubmissionReceiptFactory().verification_code
    )


# Item da entrega: o conteúdo bate com o tipo


def test_item_link_exige_link():
    with pytest.raises(IntegrityError):
        SubmissionItemFactory(kind=FieldKind.LINK, link="")


def test_item_arquivo_exige_arquivo():
    with pytest.raises(IntegrityError):
        SubmissionItemFactory(kind=FieldKind.FILE, link="", file_url="")


def test_item_arquivo_valido():
    item = SubmissionItemFactory(
        kind=FieldKind.FILE, link="", file_url="entregas/relatorio.pdf"
    )
    assert item.pk


# Regras de edição (validadas no admin e nos casos de uso)


def test_projeto_recusa_desafio_de_outra_edicao():
    equipe = TeamFactory()
    projeto = Project(
        team=equipe,
        edition=equipe.edition,
        challenge=ChallengeFactory(edition=EditionFactory()),
        title="Projeto",
        summary="Resumo",
    )
    with pytest.raises(ValidationError, match="desafio"):
        projeto.full_clean()


def test_projeto_recusa_categoria_de_outra_edicao():
    equipe = TeamFactory()
    projeto = Project(
        team=equipe,
        edition=equipe.edition,
        challenge=ChallengeFactory(edition=equipe.edition),
        category=CategoryFactory(edition=EditionFactory()),
        title="Projeto",
        summary="Resumo",
    )
    with pytest.raises(ValidationError, match="categoria"):
        projeto.full_clean()


def test_entrega_recusa_etapa_de_outra_edicao():
    entrega = Submission(project=ProjectFactory(), stage=StageFactory())
    with pytest.raises(ValidationError, match="etapa"):
        entrega.full_clean()


# Factories válidas para os próximos apps


@pytest.mark.parametrize(
    "factory",
    [
        ProjectFactory,
        SubmissionFactory,
        SubmissionVersionFactory,
        SubmissionItemFactory,
        SubmissionReceiptFactory,
    ],
)
def test_factory_gera_registro_valido(factory):
    factory().full_clean()
