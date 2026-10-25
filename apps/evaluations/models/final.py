from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel
from apps.evaluations.enums import FinalEvaluationStatus, QuestionKind
from apps.evaluations.rules import (
    ensure_answer_matches_question,
    ensure_reviewer_in_edition,
    ensure_same_edition,
)

# A etapa final dos avaliadores externos não entra na nota de 0 a 10 nem nos
# pontos das disciplinas; serve só à premiação (RN08 do Avaliador).


class FinalForm(TimeStampedModel):
    """Formulário dos avaliadores externos, um por edição (RF12)."""

    edition = models.OneToOneField(
        "editions.Edition", on_delete=models.PROTECT, related_name="final_form"
    )
    title = models.CharField(max_length=150, blank=True)
    # Depois de publicado não muda se já houver resposta (regra do caso de uso).
    published = models.BooleanField(default=False)

    class Meta:
        verbose_name = "formulário final"
        verbose_name_plural = "formulários finais"

    def __str__(self):
        return self.title or f"Formulário final — {self.edition}"


class FinalQuestion(TimeStampedModel):
    """Pergunta do formulário final (RF12)."""

    # Pergunta só existe dentro do formulário (CASCADE).
    form = models.ForeignKey(
        FinalForm, on_delete=models.CASCADE, related_name="questions"
    )
    order = models.PositiveSmallIntegerField()
    prompt = models.TextField()
    kind = models.CharField(max_length=10, choices=QuestionKind)
    max_score = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True
    )

    class Meta:
        verbose_name = "pergunta final"
        verbose_name_plural = "perguntas finais"
        ordering = ["form", "order"]
        constraints = [
            models.UniqueConstraint(
                fields=["form", "order"], name="unique_question_order_per_form"
            ),
            # Nota exige pontuação máxima positiva; os demais tipos não têm.
            models.CheckConstraint(
                condition=Q(
                    kind=QuestionKind.SCORE, max_score__isnull=False, max_score__gt=0
                )
                | (~Q(kind=QuestionKind.SCORE) & Q(max_score__isnull=True)),
                name="final_question_max_score_matches_kind",
            ),
        ]

    def __str__(self):
        return f"{self.order}. {self.prompt[:50]}"


class FinalEvaluation(TimeStampedModel):
    """Avaliação de um avaliador externo sobre um projeto finalista (RF42, RF43)."""

    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="final_evaluations"
    )
    reviewer = models.ForeignKey(
        "accounts.ExternalReviewer",
        on_delete=models.PROTECT,
        related_name="final_evaluations",
    )
    form = models.ForeignKey(
        FinalForm, on_delete=models.PROTECT, related_name="evaluations"
    )
    comment = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=FinalEvaluationStatus,
        default=FinalEvaluationStatus.PENDING,
    )
    finalized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "avaliação final"
        verbose_name_plural = "avaliações finais"
        constraints = [
            models.UniqueConstraint(
                fields=["project", "reviewer"],
                name="unique_final_evaluation_per_reviewer",
            ),
            models.CheckConstraint(
                condition=Q(
                    status=FinalEvaluationStatus.PENDING, finalized_at__isnull=True
                )
                | Q(status=FinalEvaluationStatus.EVALUATED, finalized_at__isnull=False),
                name="final_evaluation_finalized_at_iff_evaluated",
            ),
        ]

    def clean(self):
        if self.project_id and self.form_id:
            ensure_same_edition(self.project, self.form.edition_id, "form")
        if self.project_id and self.reviewer_id:
            ensure_reviewer_in_edition(self)

    def __str__(self):
        return f"{self.project} — {self.reviewer}"


class FinalAnswer(TimeStampedModel):
    """Resposta a uma pergunta do formulário final (RF43)."""

    # Resposta só existe dentro da avaliação (CASCADE).
    evaluation = models.ForeignKey(
        FinalEvaluation, on_delete=models.CASCADE, related_name="answers"
    )
    question = models.ForeignKey(
        FinalQuestion, on_delete=models.PROTECT, related_name="answers"
    )
    value = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    text = models.TextField(blank=True)

    class Meta:
        verbose_name = "resposta final"
        verbose_name_plural = "respostas finais"
        constraints = [
            models.UniqueConstraint(
                fields=["evaluation", "question"], name="unique_answer_per_question"
            ),
        ]

    def clean(self):
        if self.evaluation_id and self.question_id:
            ensure_answer_matches_question(self)

    def __str__(self):
        return f"{self.question}: {self.value if self.value is not None else self.text}"
