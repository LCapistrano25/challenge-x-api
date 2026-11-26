import factory

from apps.accounts.enums import UserRole
from apps.accounts.factories import UserFactory
from apps.support.enums import SupportTicketPriority, SupportTicketStatus
from apps.support.models import SupportTicket


class SupportTicketFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SupportTicket

    requester = factory.SubFactory(UserFactory, role=UserRole.STUDENT)
    assigned_to = None
    title = factory.Sequence(lambda n: f"Correção cadastral {n}")
    description = "Solicito correção dos meus dados cadastrais."
    status = SupportTicketStatus.OPEN
    priority = SupportTicketPriority.MEDIUM
    support_response = None
    resolved_at = None
