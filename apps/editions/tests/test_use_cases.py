import pytest
from django.core.exceptions import ValidationError

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import NotAdminActor
from apps.accounts.factories import ExternalReviewerFactory, UserFactory
from apps.core.factories import CourseFactory
from apps.editions import use_cases
from apps.editions.enums import EditionStatus
from apps.editions.exceptions import (
    EditionAlreadyExists,
    EditionClosed,
    InvalidTeamLimits,
    ReviewerAlreadyLinked,
    TeamLimitsLocked,
)
from apps.editions.factories import EditionFactory
from apps.editions.models import Edition, EditionReviewer
from apps.editions.use_cases.configure_team_limits import configure_team_limits
from apps.editions.use_cases.create_edition import create_edition
from apps.editions.use_cases.link_reviewer_to_edition import (
    link_reviewer_to_edition,
)
from apps.editions.use_cases.update_reviewer_scope import update_reviewer_scope

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin():
    return UserFactory(role=UserRole.ADMIN)


# Cadastro de edição (UC18, RF47, RN05)


def test_cria_edicao_em_configuracao_com_limites_padrao(admin):
    edicao = create_edition(actor=admin, year=2030, semester=1, name="Desafio X 2030/1")

    edicao.refresh_from_db()
    assert (edicao.year, edicao.semester) == (2030, 1)
    assert edicao.name == "Desafio X 2030/1"
    assert edicao.status == EditionStatus.SETUP
    assert (edicao.min_members, edicao.max_members) == (3, 5)
    assert edicao.published_at is None
    assert edicao.closed_at is None


def test_nome_pode_ficar_vazio(admin):
    edicao = create_edition(actor=admin, year=2030, semester=2)
    assert edicao.name == ""


@pytest.mark.parametrize("semester", [1, 2])
def test_aceita_os_dois_semestres(admin, semester):
    assert create_edition(actor=admin, year=2030, semester=semester).pk


def test_mesmo_ano_com_outro_semestre_e_aceito(admin):
    EditionFactory(year=2030, semester=1)
    assert create_edition(actor=admin, year=2030, semester=2).pk


@pytest.mark.parametrize("semester", [0, 3, -1])
def test_semestre_invalido_e_recusado(admin, semester):
    with pytest.raises(ValidationError):
        create_edition(actor=admin, year=2030, semester=semester)
    assert not Edition.objects.filter(year=2030).exists()


def test_edicao_duplicada_e_recusada(admin):
    existente = EditionFactory()
    antes = Edition.objects.count()

    with pytest.raises(EditionAlreadyExists):
        create_edition(actor=admin, year=existente.year, semester=existente.semester)

    assert Edition.objects.count() == antes


def test_corrida_na_criacao_vira_edition_already_exists(admin, monkeypatch):
    # A checagem prévia não vê a edição (outra requisição ainda não tinha gravado
    # quando ela rodou); quem recusa é a unicidade do banco.
    monkeypatch.setattr(
        use_cases.create_edition,
        "ensure_edition_identification_is_free",
        lambda *a: None,
    )
    existente = EditionFactory()

    with pytest.raises(EditionAlreadyExists):
        create_edition(actor=admin, year=existente.year, semester=existente.semester)

    # A transação segue utilizável depois do conflito.
    assert Edition.objects.filter(pk=existente.pk).exists()


@pytest.mark.parametrize(
    "role", [UserRole.STUDENT, UserRole.TEACHER, UserRole.EXTERNAL_REVIEWER]
)
def test_quem_nao_e_admin_nao_cadastra(role):
    with pytest.raises(NotAdminActor):
        create_edition(actor=UserFactory(role=role), year=2030, semester=1)
    assert not Edition.objects.filter(year=2030).exists()


def test_sem_ator_nao_cadastra():
    with pytest.raises(NotAdminActor):
        create_edition(actor=None, year=2030, semester=1)
    assert not Edition.objects.filter(year=2030).exists()


# Limites da equipe (UC19, RF48, RN07)


@pytest.fixture
def edicao():
    return EditionFactory()


def limites(edicao):
    edicao.refresh_from_db()
    return edicao.min_members, edicao.max_members


@pytest.mark.parametrize("novos", [(2, 4), (3, 5), (1, 1), (4, 4)])
def test_configura_limites_validos(admin, edicao, novos):
    resultado = configure_team_limits(
        actor=admin, edition=edicao, min_members=novos[0], max_members=novos[1]
    )

    assert (resultado.min_members, resultado.max_members) == novos
    assert limites(edicao) == novos
    assert edicao.status == EditionStatus.SETUP


@pytest.mark.parametrize("novos", [(0, 5), (3, 0), (0, 0), (-1, 5), (3, -1), (6, 5)])
def test_limites_invalidos_nao_alteram_a_edicao(admin, edicao, novos):
    with pytest.raises(InvalidTeamLimits):
        configure_team_limits(
            actor=admin, edition=edicao, min_members=novos[0], max_members=novos[1]
        )
    assert limites(edicao) == (3, 5)


@pytest.mark.parametrize("status", [EditionStatus.PUBLISHED, EditionStatus.CLOSED])
def test_edicao_publicada_ou_encerrada_trava_os_limites(admin, status):
    edicao = EditionFactory(status=status)

    with pytest.raises(TeamLimitsLocked):
        configure_team_limits(actor=admin, edition=edicao, min_members=2, max_members=4)
    assert limites(edicao) == (3, 5)


def test_status_vale_o_do_banco_e_nao_o_do_objeto_recebido(admin, edicao):
    # O objeto em mãos ainda diz SETUP, mas outra requisição já publicou.
    Edition.objects.filter(pk=edicao.pk).update(status=EditionStatus.PUBLISHED)
    assert edicao.status == EditionStatus.SETUP

    with pytest.raises(TeamLimitsLocked):
        configure_team_limits(actor=admin, edition=edicao, min_members=2, max_members=4)
    assert limites(edicao) == (3, 5)


@pytest.mark.parametrize(
    "role", [UserRole.STUDENT, UserRole.TEACHER, UserRole.EXTERNAL_REVIEWER]
)
def test_quem_nao_e_admin_nao_configura_limites(edicao, role):
    with pytest.raises(NotAdminActor):
        configure_team_limits(
            actor=UserFactory(role=role), edition=edicao, min_members=2, max_members=4
        )
    assert limites(edicao) == (3, 5)


def test_sem_ator_nao_configura_limites(edicao):
    with pytest.raises(NotAdminActor):
        configure_team_limits(actor=None, edition=edicao, min_members=2, max_members=4)
    assert limites(edicao) == (3, 5)


# Vínculo do avaliador externo com a edição (UC11, RF11)


@pytest.fixture
def avaliador():
    return ExternalReviewerFactory()


def vincular(actor, edicao, avaliador_id, course_id=None):
    return link_reviewer_to_edition(
        actor=actor, edition=edicao, evaluator_id=avaliador_id, course_id=course_id
    )


def test_vincula_avaliador_a_todos_os_cursos(admin, avaliador):
    edicao = EditionFactory()

    link = vincular(admin, edicao, avaliador.pk)

    assert (link.edition, link.reviewer, link.course) == (edicao, avaliador, None)


def test_vincula_avaliador_a_um_curso(admin, avaliador):
    curso = CourseFactory()

    link = vincular(admin, EditionFactory(), avaliador.pk, curso.pk)

    assert link.course == curso


def test_avaliador_ja_vinculado_e_recusado(admin, avaliador):
    edicao = EditionFactory()
    vincular(admin, edicao, avaliador.pk)

    with pytest.raises(ReviewerAlreadyLinked):
        vincular(admin, edicao, avaliador.pk)


def test_edicao_encerrada_nao_aceita_vinculo(admin, avaliador):
    with pytest.raises(EditionClosed):
        vincular(admin, EditionFactory(status=EditionStatus.CLOSED), avaliador.pk)


def test_avaliador_inexistente_aponta_o_campo(admin):
    with pytest.raises(ValidationError) as error:
        vincular(admin, EditionFactory(), 999999)

    assert "evaluator_id" in error.value.message_dict


def test_usuario_que_nao_e_avaliador_nao_e_vinculado(admin):
    with pytest.raises(ValidationError):
        vincular(admin, EditionFactory(), admin.pk)


@pytest.mark.parametrize("inativo", [True, False])
def test_curso_inativo_ou_inexistente_aponta_o_campo(admin, avaliador, inativo):
    course_id = CourseFactory(active=False).pk if inativo else 999999

    with pytest.raises(ValidationError) as error:
        vincular(admin, EditionFactory(), avaliador.pk, course_id)

    assert "course_id" in error.value.message_dict


@pytest.mark.parametrize("role", [UserRole.TEACHER, UserRole.EXTERNAL_REVIEWER])
def test_quem_nao_e_admin_nao_vincula(avaliador, role):
    with pytest.raises(NotAdminActor):
        vincular(UserFactory(role=role), EditionFactory(), avaliador.pk)


def test_troca_a_abrangencia_do_avaliador(admin, avaliador):
    curso = CourseFactory()
    link = EditionReviewer.objects.create(edition=EditionFactory(), reviewer=avaliador)

    update_reviewer_scope(actor=admin, link=link, course_id=curso.pk)
    link.refresh_from_db()
    assert link.course == curso

    update_reviewer_scope(actor=admin, link=link, course_id=None)
    link.refresh_from_db()
    assert link.course is None


def test_edicao_encerrada_nao_muda_a_abrangencia(admin, avaliador):
    link = EditionReviewer.objects.create(
        edition=EditionFactory(status=EditionStatus.CLOSED), reviewer=avaliador
    )

    with pytest.raises(EditionClosed):
        update_reviewer_scope(actor=admin, link=link, course_id=CourseFactory().pk)


def test_quem_nao_e_admin_nao_muda_a_abrangencia(avaliador):
    link = EditionReviewer.objects.create(edition=EditionFactory(), reviewer=avaliador)

    with pytest.raises(NotAdminActor):
        update_reviewer_scope(
            actor=UserFactory(role=UserRole.TEACHER), link=link, course_id=None
        )
