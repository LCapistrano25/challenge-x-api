from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel
from apps.teams.enums import InvitationStatus, RequestStatus


class Invitation(TimeStampedModel):
    """Convite do líder para um aluno já cadastrado (RF22, RF23)."""

    team = models.ForeignKey(
        "teams.Team", on_delete=models.PROTECT, related_name="invitations"
    )
    student = models.ForeignKey(
        "accounts.Student", on_delete=models.PROTECT, related_name="invitations"
    )
    status = models.CharField(
        max_length=20, choices=InvitationStatus, default=InvitationStatus.PENDING
    )
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "convite"
        verbose_name_plural = "convites"
        constraints = [
            # Um convite pendente por aluno; recusados e cancelados ficam no histórico.
            models.UniqueConstraint(
                fields=["team", "student"],
                condition=Q(status=InvitationStatus.PENDING),
                name="unique_pending_invitation_per_student",
            ),
        ]

    def __str__(self):
        return f"{self.team} -> {self.student}"


class JoinRequest(TimeStampedModel):
    """Pedido do aluno para entrar numa equipe (RF24, RF25)."""

    team = models.ForeignKey(
        "teams.Team", on_delete=models.PROTECT, related_name="join_requests"
    )
    student = models.ForeignKey(
        "accounts.Student", on_delete=models.PROTECT, related_name="join_requests"
    )
    status = models.CharField(
        max_length=20, choices=RequestStatus, default=RequestStatus.PENDING
    )
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "solicitação de entrada"
        verbose_name_plural = "solicitações de entrada"
        constraints = [
            models.UniqueConstraint(
                fields=["team", "student"],
                condition=Q(status=RequestStatus.PENDING),
                name="unique_pending_join_request",
            ),
        ]

    def __str__(self):
        return f"{self.student} -> {self.team}"


class LeadershipRequest(TimeStampedModel):
    """Pedido de liderança por abandono, decidido pelo professor (RF28, RF40)."""

    team = models.ForeignKey(
        "teams.Team", on_delete=models.PROTECT, related_name="leadership_requests"
    )
    requester = models.ForeignKey(
        "accounts.Student",
        on_delete=models.PROTECT,
        related_name="leadership_requests",
    )
    justification = models.TextField()
    status = models.CharField(
        max_length=20, choices=RequestStatus, default=RequestStatus.PENDING
    )
    # Quem decidiu (RF40).
    teacher = models.ForeignKey(
        "accounts.Teacher",
        on_delete=models.PROTECT,
        related_name="leadership_decisions",
        null=True,
        blank=True,
    )
    decision_justification = models.TextField(blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "solicitação de liderança"
        verbose_name_plural = "solicitações de liderança"
        constraints = [
            models.UniqueConstraint(
                fields=["team"],
                condition=Q(status=RequestStatus.PENDING),
                name="unique_pending_leadership_request",
            ),
        ]

    def __str__(self):
        return f"{self.requester} -> {self.team}"
