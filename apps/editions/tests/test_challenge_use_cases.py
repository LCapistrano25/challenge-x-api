import pytest
from django.core.exceptions import ValidationError

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import NotAdminActor
from apps.accounts.factories import UserFactory
from apps.core.factories import CourseFactory, SdgFactory
from apps.editions.enums import EditionStatus
from apps.editions.exceptions import EditionClosed
from apps.editions.factories import EditionFactory, EditionSdgFactory
from apps.editions.models import Challenge
from apps.editions.use_cases.create_challenge import create_challenge

pytestmark = pytest.mark.django_db


@pytest.fixture
def challenge_data():
    link = EditionSdgFactory(sdg=SdgFactory(number=4))
    return {
        "actor": UserFactory(role=UserRole.ADMIN),
        "edition": link.edition,
        "course_id": CourseFactory().pk,
        "sdg_id": link.sdg_id,
        "description": "Desafio da ODS principal; ODS secundária no texto.",
    }


def test_cadastra_mais_de_um_desafio_no_mesmo_par(challenge_data):
    first = create_challenge(**challenge_data)
    second = create_challenge(**challenge_data, active=False)

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.pk != second.pk
    assert first.active is True
    assert second.active is False
    assert first.edition_id == challenge_data["edition"].pk
    assert first.course_id == challenge_data["course_id"]
    assert first.sdg_id == challenge_data["sdg_id"]
    assert first.description == challenge_data["description"]


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("course_id", lambda: CourseFactory(active=False).pk),
        ("sdg_id", lambda: SdgFactory(number=6).pk),
    ],
)
def test_recusa_curso_inativo_ou_ods_nao_habilitada(challenge_data, field, replacement):
    challenge_data[field] = replacement()

    with pytest.raises(ValidationError):
        create_challenge(**challenge_data)

    assert not Challenge.objects.exists()


def test_recusa_ods_habilitada_mas_inativa(challenge_data):
    link = challenge_data["edition"].sdg_links.get()
    link.sdg.active = False
    link.sdg.save(update_fields=["active"])

    with pytest.raises(ValidationError):
        create_challenge(**challenge_data)

    assert not Challenge.objects.exists()


def test_recusa_edicao_encerrada(challenge_data):
    challenge_data["edition"] = EditionFactory(status=EditionStatus.CLOSED)
    with pytest.raises(EditionClosed):
        create_challenge(**challenge_data)
    assert not Challenge.objects.exists()


def test_recusa_ator_nao_administrador(challenge_data):
    challenge_data["actor"] = UserFactory(role=UserRole.TEACHER)
    with pytest.raises(NotAdminActor):
        create_challenge(**challenge_data)
    assert not Challenge.objects.exists()
