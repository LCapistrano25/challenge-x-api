import pytest
from django.core.exceptions import ValidationError

from apps.accounts.enums import UserRole
from apps.accounts.exceptions import NotAdminActor
from apps.accounts.factories import UserFactory
from apps.notifications.models import Notification, NotificationType
from apps.support.enums import SupportTicketPriority, SupportTicketStatus
from apps.support.exceptions import InvalidStatusTransition
from apps.support.factories import SupportTicketFactory
from apps.support.models import SupportTicket
from apps.support.use_cases.answer_ticket import answer_ticket
from apps.support.use_cases.open_ticket import open_ticket

pytestmark = pytest.mark.django_db


# open_ticket


@pytest.mark.parametrize("role", [UserRole.STUDENT, UserRole.TEACHER])
def test_open_ticket_cria_chamado_para_aluno_e_professor(role):
    actor = UserFactory(role=role)

    ticket = open_ticket(
        actor=actor,
        title="  Correção de matrícula  ",
        description="  Minha matrícula está errada.  ",
    )

    ticket.refresh_from_db()
    assert ticket.requester == actor
    assert ticket.title == "Correção de matrícula"
    assert ticket.description == "Minha matrícula está errada."
    assert ticket.status == SupportTicketStatus.OPEN
    assert ticket.priority == SupportTicketPriority.MEDIUM
    assert ticket.support_response is None
    assert ticket.assigned_to is None
    assert ticket.resolved_at is None


def test_open_ticket_recusa_admin():
    admin = UserFactory(role=UserRole.ADMIN)

    with pytest.raises(ValidationError):
        open_ticket(actor=admin, title="Título", description="Descrição")

    assert not SupportTicket.objects.exists()


@pytest.mark.parametrize(
    ("title", "description", "field"),
    [
        ("", "Descrição", "title"),
        ("   ", "Descrição", "title"),
        ("x" * 151, "Descrição", "title"),
        ("Título", "", "description"),
        ("Título", "   ", "description"),
    ],
)
def test_open_ticket_valida_campos(title, description, field):
    student = UserFactory(role=UserRole.STUDENT)

    with pytest.raises(ValidationError) as exc:
        open_ticket(actor=student, title=title, description=description)

    assert field in exc.value.message_dict
    assert not SupportTicket.objects.exists()


# answer_ticket


def test_answer_ticket_exige_admin():
    ticket = SupportTicketFactory()
    student = UserFactory(role=UserRole.STUDENT)

    with pytest.raises(NotAdminActor):
        answer_ticket(
            actor=student,
            ticket=ticket,
            status=SupportTicketStatus.IN_PROGRESS,
        )


def test_answer_ticket_atualiza_status_prioridade_responsavel_e_resposta():
    admin = UserFactory(role=UserRole.ADMIN)
    assignee = UserFactory(role=UserRole.ADMIN)
    ticket = SupportTicketFactory()

    updated = answer_ticket(
        actor=admin,
        ticket=ticket,
        status=SupportTicketStatus.RESOLVED,
        priority=SupportTicketPriority.HIGH,
        support_response="Matrícula corrigida.",
        assigned_to=assignee,
    )

    updated.refresh_from_db()
    assert updated.status == SupportTicketStatus.RESOLVED
    assert updated.priority == SupportTicketPriority.HIGH
    assert updated.support_response == "Matrícula corrigida."
    assert updated.assigned_to == assignee
    assert updated.resolved_at is not None

    notif = Notification.objects.get(user=ticket.requester)
    assert notif.type == NotificationType.SYSTEM


def test_answer_ticket_reabrir_de_resolved_limpa_resolved_at():
    admin = UserFactory(role=UserRole.ADMIN)
    ticket = SupportTicketFactory()
    answer_ticket(
        actor=admin,
        ticket=ticket,
        status=SupportTicketStatus.RESOLVED,
        support_response="Corrigido.",
    )
    ticket.refresh_from_db()
    assert ticket.resolved_at is not None

    reopened = answer_ticket(
        actor=admin,
        ticket=ticket,
        status=SupportTicketStatus.IN_PROGRESS,
    )

    reopened.refresh_from_db()
    assert reopened.status == SupportTicketStatus.IN_PROGRESS
    assert reopened.resolved_at is None


def test_answer_ticket_closed_exige_support_response():
    admin = UserFactory(role=UserRole.ADMIN)
    ticket = SupportTicketFactory()

    with pytest.raises(ValidationError) as exc:
        answer_ticket(
            actor=admin,
            ticket=ticket,
            status=SupportTicketStatus.CLOSED,
        )

    assert "support_response" in exc.value.message_dict
    ticket.refresh_from_db()
    assert ticket.status == SupportTicketStatus.OPEN


def test_answer_ticket_closed_com_resposta_preenche_resolved_at():
    admin = UserFactory(role=UserRole.ADMIN)
    ticket = SupportTicketFactory()

    closed = answer_ticket(
        actor=admin,
        ticket=ticket,
        status=SupportTicketStatus.CLOSED,
        support_response="Solicitação fora do escopo.",
    )

    closed.refresh_from_db()
    assert closed.status == SupportTicketStatus.CLOSED
    assert closed.support_response == "Solicitação fora do escopo."
    assert closed.resolved_at is not None


@pytest.mark.parametrize(
    ("initial", "target"),
    [
        (SupportTicketStatus.IN_PROGRESS, SupportTicketStatus.OPEN),
        (SupportTicketStatus.RESOLVED, SupportTicketStatus.OPEN),
        (SupportTicketStatus.RESOLVED, SupportTicketStatus.WAITING_USER),
        (SupportTicketStatus.CLOSED, SupportTicketStatus.OPEN),
        (SupportTicketStatus.CLOSED, SupportTicketStatus.IN_PROGRESS),
        (SupportTicketStatus.CLOSED, SupportTicketStatus.WAITING_USER),
        (SupportTicketStatus.CLOSED, SupportTicketStatus.RESOLVED),
    ],
)
def test_answer_ticket_bloqueia_transicoes_proibidas(initial, target):
    admin = UserFactory(role=UserRole.ADMIN)
    ticket = SupportTicketFactory(status=initial)

    with pytest.raises(InvalidStatusTransition):
        answer_ticket(actor=admin, ticket=ticket, status=target)


@pytest.mark.parametrize(
    "assignee_kwargs",
    [
        {"role": UserRole.STUDENT, "is_active": True},
        {"role": UserRole.TEACHER, "is_active": True},
        {"role": UserRole.ADMIN, "is_active": False},
    ],
)
def test_answer_ticket_assigned_to_exige_admin_ativo(assignee_kwargs):
    admin = UserFactory(role=UserRole.ADMIN)
    invalid_assignee = UserFactory(**assignee_kwargs)
    ticket = SupportTicketFactory()

    with pytest.raises(ValidationError) as exc:
        answer_ticket(actor=admin, ticket=ticket, assigned_to=invalid_assignee)

    assert "assigned_to" in exc.value.message_dict


def test_answer_ticket_nao_notifica_se_so_mudar_prioridade_ou_responsavel():
    admin = UserFactory(role=UserRole.ADMIN)
    ticket = SupportTicketFactory()

    answer_ticket(
        actor=admin,
        ticket=ticket,
        priority=SupportTicketPriority.URGENT,
        assigned_to=admin,
    )

    assert not Notification.objects.exists()


def test_answer_ticket_notifica_quando_muda_so_a_resposta():
    admin = UserFactory(role=UserRole.ADMIN)
    ticket = SupportTicketFactory(status=SupportTicketStatus.IN_PROGRESS)

    answer_ticket(
        actor=admin,
        ticket=ticket,
        support_response="Estamos analisando sua solicitação.",
    )

    assert (
        Notification.objects.filter(
            user=ticket.requester,
            type=NotificationType.SYSTEM,
        ).count()
        == 1
    )


@pytest.mark.parametrize(
    ("initial", "target", "response"),
    [
        (SupportTicketStatus.OPEN, SupportTicketStatus.WAITING_USER, None),
        (SupportTicketStatus.IN_PROGRESS, SupportTicketStatus.WAITING_USER, None),
        (SupportTicketStatus.WAITING_USER, SupportTicketStatus.OPEN, None),
        (SupportTicketStatus.WAITING_USER, SupportTicketStatus.IN_PROGRESS, None),
        (SupportTicketStatus.WAITING_USER, SupportTicketStatus.RESOLVED, None),
        (
            SupportTicketStatus.WAITING_USER,
            SupportTicketStatus.CLOSED,
            "Encerrado após aguardar retorno.",
        ),
    ],
)
def test_answer_ticket_permite_transicoes_com_waiting_user(initial, target, response):
    admin = UserFactory(role=UserRole.ADMIN)
    ticket = SupportTicketFactory(status=initial)

    kwargs = {"status": target}
    if response is not None:
        kwargs["support_response"] = response

    updated = answer_ticket(actor=admin, ticket=ticket, **kwargs)

    updated.refresh_from_db()
    assert updated.status == target
