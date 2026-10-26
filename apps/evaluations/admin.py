from django.contrib import admin

from apps.evaluations.models import (
    Evaluation,
    EvaluationItem,
    FinalAnswer,
    FinalEvaluation,
    FinalForm,
    FinalQuestion,
    ScoreRectification,
    StageScore,
)
from apps.evaluations.use_cases.rectify_score import rectify_score


class EvaluationItemInline(admin.TabularInline):
    model = EvaluationItem
    extra = 0


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ("project", "stage", "teacher", "status", "finalized_at")
    list_filter = ("status", "stage__edition")
    list_select_related = ("project", "stage__edition", "teacher__user")
    inlines = (EvaluationItemInline,)


@admin.register(StageScore)
class StageScoreAdmin(admin.ModelAdmin):
    list_display = ("project", "stage", "value", "evaluation_count", "status")
    list_filter = ("status", "stage__edition")
    list_select_related = ("project", "stage__edition")


class FinalQuestionInline(admin.TabularInline):
    model = FinalQuestion
    extra = 0


@admin.register(FinalForm)
class FinalFormAdmin(admin.ModelAdmin):
    list_display = ("__str__", "edition", "published")
    list_select_related = ("edition",)
    inlines = (FinalQuestionInline,)


class FinalAnswerInline(admin.TabularInline):
    model = FinalAnswer
    extra = 0


@admin.register(FinalEvaluation)
class FinalEvaluationAdmin(admin.ModelAdmin):
    list_display = ("project", "reviewer", "status", "finalized_at")
    list_filter = ("status",)
    list_select_related = ("project", "reviewer__user")
    inlines = (FinalAnswerInline,)


@admin.register(ScoreRectification)
class ScoreRectificationAdmin(admin.ModelAdmin):
    """O admin retifica pelo caso de uso; depois, a linha é histórico (RF14)."""

    fields = ("item", "new_points", "reason")
    list_display = (
        "item",
        "previous_points",
        "new_points",
        "rectified_by",
        "rectified_at",
    )
    list_select_related = ("item__stage_criterion", "rectified_by")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        saved = rectify_score(
            actor=request.user,
            item=obj.item,
            new_points=obj.new_points,
            reason=obj.reason,
        )
        obj.pk = saved.pk
