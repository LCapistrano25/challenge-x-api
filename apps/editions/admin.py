from django.contrib import admin
from django.forms.models import BaseInlineFormSet

from apps.editions.enums import EditionStatus
from apps.editions.exceptions import EditionClosed
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
from apps.editions.rules import (
    ensure_edition_not_closed,
    ensure_sdg_not_used_by_challenges,
)


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
    # Publicar e encerrar só pelos casos de uso: o encerramento é irreversível (RF47).
    readonly_fields = ("status", "published_at", "closed_at")
    inlines = (EditionSdgInline, CategoryInline, EditionReviewerInline)

    def get_readonly_fields(self, request, obj=None):
        # Limites congelam com a publicação (RF48), como no update_edition.
        if obj is not None and obj.status != EditionStatus.SETUP:
            return (*self.readonly_fields, "min_members", "max_members")
        return self.readonly_fields

    def has_change_permission(self, request, obj=None):
        # Encerrada não aceita alteração (ensure_edition_not_closed).
        if obj is not None and obj.status == EditionStatus.CLOSED:
            return False
        return super().has_change_permission(request, obj)


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ("__str__", "edition", "course", "sdg", "active")
    list_filter = ("edition", "course", "sdg", "active")
    list_select_related = ("edition", "course", "sdg")
    search_fields = ("description",)


class StageSubmissionFieldInline(admin.TabularInline):
    model = StageSubmissionField
    extra = 0

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.edition.status == EditionStatus.CLOSED:
            return False
        return super().has_delete_permission(request, obj)


class StageCriterionInline(admin.TabularInline):
    model = StageCriterion
    extra = 0


@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ("__str__", "kind", "starts_at", "ends_at", "max_score")
    list_filter = ("edition", "kind")
    list_select_related = ("edition",)
    inlines = (StageSubmissionFieldInline, StageCriterionInline)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.edition.status == EditionStatus.CLOSED:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(Criterion)
class CriterionAdmin(admin.ModelAdmin):
    list_display = ("name", "edition", "tiebreak_order")
    list_filter = ("edition",)
    list_select_related = ("edition",)
    search_fields = ("name",)

    def has_delete_permission(self, request, obj=None):
        if not super().has_delete_permission(request, obj):
            return False
        if obj is not None:
            try:
                ensure_edition_not_closed(obj.edition)
            except EditionClosed:
                return False
        return True
