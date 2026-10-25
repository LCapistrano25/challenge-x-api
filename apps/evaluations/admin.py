from django.contrib import admin

from apps.evaluations.models import (
    Evaluation,
    EvaluationItem,
    FinalAnswer,
    FinalEvaluation,
    FinalForm,
    FinalQuestion,
    StageScore,
)


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
