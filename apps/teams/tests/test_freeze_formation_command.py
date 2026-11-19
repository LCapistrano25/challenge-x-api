import pytest
from django.core.management import CommandError, call_command

from apps.accounts.enums import UserRole
from apps.accounts.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_freeze_formation_command_success(capsys, monkeypatch):
    admin = UserFactory(role=UserRole.ADMIN, is_active=True)
    expected_result = {
        "frozen_teams": 3,
        "cancelled_invitations": 2,
    }

    def fake_freeze(*, actor):
        assert actor == admin
        return expected_result

    monkeypatch.setattr(
        "apps.teams.management.commands.freeze_formation_period.freeze_formation_period",
        fake_freeze,
    )

    call_command("freeze_formation_period")

    output = capsys.readouterr().out
    assert "3 equipe(s) atualizada(s)" in output
    assert "2 convite(s) cancelado(s)" in output


def test_freeze_formation_command_rejects_when_no_active_admin():
    UserFactory(role=UserRole.ADMIN, is_active=False)

    with pytest.raises(
        CommandError,
        match="Não existe administrador ativo",
    ):
        call_command("freeze_formation_period")
