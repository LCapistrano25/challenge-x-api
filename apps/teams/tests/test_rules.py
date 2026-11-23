import pytest

from apps.editions.factories import CategoryFactory
from apps.projects.factories import ProjectFactory
from apps.teams.factories import TeamFactory, TeamMemberFactory
from apps.teams.rules import compute_unmet_requirements

pytestmark = pytest.mark.django_db


def adicionar_categoria(projeto):
    projeto.category = CategoryFactory(edition=projeto.edition)
    projeto.save(update_fields=["category"])


def completar(equipe, integrantes=3):
    for _ in range(integrantes - 1):
        TeamMemberFactory(team=equipe, edition=equipe.edition)
    return equipe


def test_equipe_completa_nao_tem_pendencias():
    projeto = ProjectFactory()
    projeto.category = CategoryFactory(edition=projeto.edition)
    projeto.save(update_fields=['category'])
    completar(projeto.team)
    assert compute_unmet_requirements(projeto.team) == []


def test_equipe_sem_projeto_lista_tudo():
    assert compute_unmet_requirements(TeamFactory()) == [
        "1 integrantes; o mínimo é 3.",
        "Sem desafio escolhido.",
        "Projeto sem título.",
        "Projeto sem resumo.",
        "Projeto sem categoria.",
    ]


def test_equipe_acima_do_maximo():
    projeto = ProjectFactory()
    adicionar_categoria(projeto)
    completar(projeto.team, integrantes=6)
    assert compute_unmet_requirements(projeto.team) == ["6 integrantes; o máximo é 5."]


def test_projeto_incompleto_aponta_o_que_falta():
    projeto = ProjectFactory(challenge=None, summary="", category=None)
    completar(projeto.team)
    assert compute_unmet_requirements(projeto.team) == [
        "Sem desafio escolhido.",
        "Projeto sem resumo.",
        "Projeto sem categoria.",
    ]


def test_integrante_que_saiu_nao_conta():
    projeto = ProjectFactory()
    adicionar_categoria(projeto)
    completar(projeto.team)
    saiu = projeto.team.members.filter(role="MEMBER").first()
    saiu.active = False
    saiu.left_at = saiu.created_at
    saiu.save()
    assert compute_unmet_requirements(projeto.team) == ["2 integrantes; o mínimo é 3."]
