from django.contrib import admin
from django.forms.models import BaseInlineFormSet

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
from apps.editions.rules import ensure_sdg_not_used_by_challenges


class EditionSdgFormSet(BaseInlineFormSet):
    def clean(self):
        # Valida antes de salvar: o erro aparece na tela em vez de virar erro 500.
        super().clean()
        for form in self.deleted_forms:
            if form.instance.pk:
                ensure_sdg_not_used_by_challenges(
                    form.instance.edition_id, form.instance.sdg_id
                )


class EditionSdgInline(admin.TabularInline):
    model = EditionSdg
    formset = EditionSdgFormSet
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
    list_display = ("__str__", "edition", "course", "sdg", "active")
    list_filter = ("edition", "course", "sdg", "active")
    list_select_related = ("edition", "course", "sdg")
    search_fields = ("description",)


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
