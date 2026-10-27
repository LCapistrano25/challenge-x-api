from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.accounts.factories import StudentFactory
from apps.results.factories import (
    CertificateFactory,
    CertificateTemplateFactory,
    ProjectResultFactory,
    StudentScoreFactory,
)
from apps.results.models import StudentScore

pytestmark = pytest.mark.django_db


# Critérios de pronto da issue BM7


def test_uma_pontuacao_por_aluno_no_projeto():
    pontuacao = StudentScoreFactory()
    with pytest.raises(IntegrityError):
        StudentScoreFactory(project=pontuacao.project, student=pontuacao.student)


def test_um_certificado_por_usuario_no_modelo():
    certificado = CertificateFactory()
    with pytest.raises(IntegrityError):
        CertificateFactory(template=certificado.template, user=certificado.user)


# Resultado do projeto


def test_um_resultado_por_projeto():
    resultado = ProjectResultFactory()
    with pytest.raises(IntegrityError):
        ProjectResultFactory(project=resultado.project)


@pytest.mark.parametrize("final_score", [Decimal("-0.01"), Decimal("10.01")])
def test_nota_final_de_0_a_10(final_score):
    with pytest.raises(IntegrityError):
        ProjectResultFactory(final_score=final_score)


def test_premiacao_so_de_1_a_3():
    with pytest.raises(IntegrityError):
        ProjectResultFactory(award=4)


# Pontuação do aluno


def test_periodo_congelado_nao_muda_com_o_aluno():
    pontuacao = StudentScoreFactory(term=3)
    pontuacao.student.term = 4
    pontuacao.student.save()
    pontuacao.refresh_from_db()
    assert pontuacao.term == 3


@pytest.mark.parametrize("term", [0, 11])
def test_periodo_de_1_a_10(term):
    with pytest.raises(IntegrityError):
        StudentScoreFactory(term=term)


def test_pontos_nao_negativos():
    with pytest.raises(IntegrityError):
        StudentScoreFactory(points=Decimal("-0.01"))


def test_aluno_fora_da_equipe_e_recusado():
    pontuacao = StudentScoreFactory()
    outra = StudentScore(
        project=pontuacao.project,
        student=StudentFactory(),
        term=3,
        points=Decimal("1.00"),
    )
    with pytest.raises(ValidationError, match="não integrou a equipe"):
        outra.full_clean()


# Certificados


def test_um_modelo_por_tipo_na_edicao():
    modelo = CertificateTemplateFactory()
    with pytest.raises(IntegrityError):
        CertificateTemplateFactory(edition=modelo.edition, kind=modelo.kind)


def test_carga_horaria_so_20_ou_40():
    with pytest.raises(IntegrityError):
        CertificateFactory(workload_hours=30)


def test_codigo_de_verificacao_proprio():
    assert CertificateFactory().verification_code != (
        CertificateFactory().verification_code
    )


# Factories válidas


@pytest.mark.parametrize(
    "factory",
    [
        ProjectResultFactory,
        StudentScoreFactory,
        CertificateTemplateFactory,
        CertificateFactory,
    ],
)
def test_factory_gera_registro_valido(factory):
    factory().full_clean()


def test_trait_premiado_valido():
    ProjectResultFactory(awarded=True).full_clean()
