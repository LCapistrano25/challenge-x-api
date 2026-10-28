from uuid import uuid4

from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from apps.core.models import TimeStampedModel
from apps.projects.enums import ProjectStatus
from apps.projects.rules import ensure_project_in_team_edition


def new_verification_code():
    return uuid4().hex


class Project(TimeStampedModel):
    """Projeto da equipe; curso e ODS vêm do desafio (RF29, RF30, RF34)."""

    team = models.OneToOneField(
        "teams.Team", on_delete=models.PROTECT, related_name="project"
    )
    # Repetido da equipe para a unicidade do título; rules garante que não diverge.
    edition = models.ForeignKey(
        "editions.Edition", on_delete=models.PROTECT, related_name="projects"
    )
    # Título, resumo e desafio ficam em branco até a equipe preencher: o desafio
    # vem antes (RF29) e some quando o curso perde representante (RF26). P-25.
    title = models.CharField(max_length=200, blank=True)
    summary = models.TextField(blank=True)
    objective = models.TextField(blank=True)
    challenge = models.ForeignKey(
        "editions.Challenge",
        on_delete=models.PROTECT,
        related_name="projects",
        null=True,
        blank=True,
    )
    category = models.ForeignKey(
        "editions.Category",
        on_delete=models.PROTECT,
        related_name="projects",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20, choices=ProjectStatus, default=ProjectStatus.IN_PROGRESS
    )

    class Meta:
        verbose_name = "projeto"
        verbose_name_plural = "projetos"
        constraints = [
            # Título único na edição sem diferenciar maiúsculas (RN03); os
            # espaços extras saem no save. Título em branco não conta.
            models.UniqueConstraint(
                "edition",
                Lower("title"),
                condition=~Q(title=""),
                name="unique_project_title_per_edition",
            ),
        ]

    def save(self, *args, **kwargs):
        self.title = " ".join(self.title.split())
        super().save(*args, **kwargs)

    def clean(self):
        if self.team_id and self.edition_id:
            ensure_project_in_team_edition(self)

    def __str__(self):
        return self.title or f"Projeto de {self.team}"
