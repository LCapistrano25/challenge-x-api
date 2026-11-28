from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from apps.core.admin import ReadOnlyMixin
from apps.core.exceptions import AppError
from apps.teams.models import (
    Invitation,
    JoinRequest,
    LeadershipRequest,
    MemberNote,
    Team,
    TeamMember,
)
from apps.teams.use_cases.assign_leader import assign_leader
from apps.teams.use_cases.reinstate_team import reinstate_team


def _run_for_each(modeladmin, request, queryset, step, done) -> None:
    for obj in queryset:
        try:
            step(actor=request.user, obj=obj)
        except AppError as error:
            modeladmin.message_user(request, f"{obj}: {error}", messages.ERROR)
        else:
            modeladmin.message_user(request, f"{obj}: {done}")


class TeamMemberFormSet(BaseInlineFormSet):
    def clean(self):
        # O inline grava direto: confere o máximo da edição antes (RF48).
        super().clean()
        if not self.instance.edition_id:
            return  # equipe nova sem edição: o próprio formulário acusa
        active = sum(
            1
            for form in self.forms
            if form.cleaned_data
            and not form.cleaned_data.get("DELETE")
            and form.cleaned_data.get("active")
        )
        maximum = self.instance.edition.max_members
        if active > maximum:
            raise ValidationError(f"{active} integrantes ativos; o máximo é {maximum}.")


class TeamMemberInline(admin.TabularInline):
    model = TeamMember
    formset = TeamMemberFormSet
    extra = 0
    autocomplete_fields = ("student",)


@admin.action(description="Reverter desclassificação")
def reinstate_team_action(modeladmin, request, queryset):
    _run_for_each(
        modeladmin,
        request,
        queryset,
        lambda actor, obj: reinstate_team(actor=actor, team=obj),
        "desclassificação revertida; recalcule os resultados se já calculados.",
    )


@admin.action(description="Tornar líder da equipe")
def assign_leader_action(modeladmin, request, queryset):
    _run_for_each(
        modeladmin,
        request,
        queryset.select_related("team", "student__user"),
        lambda actor, obj: assign_leader(actor=actor, member=obj),
        "agora é o líder.",
    )


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "edition", "status", "situation")
    list_filter = ("edition", "status", "situation")
    list_select_related = ("edition",)
    search_fields = ("name", "code")
    inlines = (TeamMemberInline,)
    actions = (reinstate_team_action,)


@admin.register(TeamMember)
class TeamMemberAdmin(ReadOnlyMixin, admin.ModelAdmin):
    """Só consulta; a troca de líder passa pelo caso de uso (com notificação)."""

    list_display = ("student", "team", "role", "active")
    list_filter = ("role", "active", "team__edition")
    list_select_related = ("team", "student__user")
    search_fields = ("team__name", "student__user__name", "student__user__email")
    actions = (assign_leader_action,)


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("team", "student", "status")
    list_filter = ("status",)
    list_select_related = ("team", "student__user")
    search_fields = ("team__name", "student__user__email")


@admin.register(JoinRequest)
class JoinRequestAdmin(admin.ModelAdmin):
    list_display = ("team", "student", "status")
    list_filter = ("status",)
    list_select_related = ("team", "student__user")


@admin.register(LeadershipRequest)
class LeadershipRequestAdmin(admin.ModelAdmin):
    list_display = ("team", "requester", "status", "teacher")
    list_filter = ("status",)
    list_select_related = ("team", "requester__user", "teacher__user")


@admin.register(MemberNote)
class MemberNoteAdmin(admin.ModelAdmin):
    list_display = ("member", "author", "created_at")
    list_select_related = ("member__team", "member__student__user", "author__user")
