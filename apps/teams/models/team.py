from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.core.models import TimeStampedModel
from apps.teams.enums import MemberRole, TeamSituation, TeamStatus
from apps.teams.rules import ensure_member_edition_matches_team


class Team(TimeStampedModel):
    """Equipe da edição; o líder é o TeamMember com role LEADER (RF13, RF21, RF51)."""

    edition = models.ForeignKey(
        "editions.Edition", on_delete=models.PROTECT, related_name="teams"
    )
    name = models.CharField(max_length=150)
    # Código usado nos convites (RF21).
    code = models.CharField(max_length=20, unique=True)
    status = models.CharField(
        max_length=20, choices=TeamStatus, default=TeamStatus.ACTIVE
    )
    situation = models.CharField(
        max_length=30, choices=TeamSituation, null=True, blank=True
    )
    # Motivo, data e responsável da desclassificação andam juntos (RF13, P-22).
    disqualification_reason = models.TextField(blank=True)
    disqualified_at = models.DateTimeField(null=True, blank=True)
    disqualified_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="disqualified_teams",
        limit_choices_to={"role": UserRole.ADMIN},
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "equipe"
        verbose_name_plural = "equipes"
        constraints = [
            models.UniqueConstraint(
                fields=["edition", "name"], name="unique_team_name_per_edition"
            ),
            models.CheckConstraint(
                condition=(
                    Q(status=TeamStatus.DISQUALIFIED)
                    & ~Q(disqualification_reason="")
                    & Q(disqualified_at__isnull=False, disqualified_by__isnull=False)
                )
                | (
                    ~Q(status=TeamStatus.DISQUALIFIED)
                    & Q(
                        disqualification_reason="",
                        disqualified_at__isnull=True,
                        disqualified_by__isnull=True,
                    )
                ),
                name="team_disqualification_matches_status",
            ),
        ]

    def __str__(self):
        return self.name


class TeamMember(TimeStampedModel):
    """Integrante da equipe; saídas e retornos ficam no histórico (RF22 a RF27)."""

    team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="members")
    # Repetido da equipe para a unicidade por edição; rules garante que não diverge.
    edition = models.ForeignKey(
        "editions.Edition", on_delete=models.PROTECT, related_name="team_members"
    )
    student = models.ForeignKey(
        "accounts.Student", on_delete=models.PROTECT, related_name="memberships"
    )
    role = models.CharField(
        max_length=20, choices=MemberRole, default=MemberRole.MEMBER
    )
    joined_at = models.DateTimeField(default=timezone.now)
    left_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "integrante da equipe"
        verbose_name_plural = "integrantes da equipe"
        constraints = [
            # As unicidades valem só para vínculos ativos, preservando o histórico.
            models.UniqueConstraint(
                fields=["edition", "student"],
                condition=Q(active=True),
                name="unique_active_team_per_edition",
            ),
            models.UniqueConstraint(
                fields=["team", "student"],
                condition=Q(active=True),
                name="unique_active_student_per_team",
            ),
            models.UniqueConstraint(
                fields=["team"],
                condition=Q(active=True, role=MemberRole.LEADER),
                name="single_active_leader_per_team",
            ),
            models.CheckConstraint(
                condition=Q(active=True, left_at__isnull=True)
                | Q(active=False, left_at__isnull=False),
                name="team_member_left_at_iff_inactive",
            ),
        ]

    def clean(self):
        if self.team_id and self.edition_id:
            ensure_member_edition_matches_team(self.team, self.edition_id)

    def __str__(self):
        return f"{self.team} - {self.student}"
