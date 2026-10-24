from django.contrib import admin

from apps.editions.models import (
    Category,
    Challenge,
    Criterion,
    Edition,
    EditionReviewer,
    EditionSdg,
    Stage,
    StageCriterion,
    StageSubmissionField,
)


class EditionSdgInline(admin.TabularInline):
    model = EditionSdg
    extra = 0


class CategoryInline(admin.TabularInline):
    model = Category
    extra = 0


class EditionReviewerInline(admin.TabularInline):
    model = EditionReviewer
    extra = 0
    autocomplete_fields = ("reviewer",)


@admin.register(Edition)
class EditionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "year", "semester", "status")
    list_filter = ("status",)
    inlines = (EditionSdgInline, CategoryInline, EditionReviewerInline)


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ("title", "edition", "course", "sdg", "active")
    list_filter = ("edition", "course", "sdg", "active")
    list_select_related = ("edition", "course", "sdg")
    search_fields = ("title",)


class StageSubmissionFieldInline(admin.TabularInline):
    model = StageSubmissionField
    extra = 0


class StageCriterionInline(admin.TabularInline):
    model = StageCriterion
    extra = 0


@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ("__str__", "kind", "starts_at", "ends_at", "max_score")
    list_filter = ("edition", "kind")
    list_select_related = ("edition",)
    inlines = (StageSubmissionFieldInline, StageCriterionInline)


@admin.register(Criterion)
class CriterionAdmin(admin.ModelAdmin):
    list_display = ("name", "edition", "tiebreak_order")
    list_filter = ("edition",)
    list_select_related = ("edition",)
    search_fields = ("name",)
