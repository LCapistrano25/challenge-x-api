from django.contrib import admin

from apps.teams.models import (
    Invitation,
    JoinRequest,
    LeadershipRequest,
    MemberNote,
    Team,
    TeamMember,
)


class TeamMemberInline(admin.TabularInline):
    model = TeamMember
    extra = 0
    autocomplete_fields = ("student",)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "edition", "status", "situation")
    list_filter = ("edition", "status", "situation")
    list_select_related = ("edition",)
    search_fields = ("name", "code")
    inlines = (TeamMemberInline,)


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
