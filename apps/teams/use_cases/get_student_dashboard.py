from django.utils import timezone

from apps.accounts.models import User
from apps.editions.enums import EditionStatus, StageKind
from apps.editions.models import Edition, Stage
from apps.evaluations.selectors import get_project_scores
from apps.projects.selectors import get_delivery_status, get_phase_status
from apps.projects.serializers import ProjectSerializer
from apps.teams.enums import (
    InvitationStatus,
    MemberRole,
    RequestStatus,
    TeamSituation,
)
from apps.teams.models import Invitation, JoinRequest, TeamMember
from apps.teams.rules import compute_unmet_requirements
from apps.teams.serializers import StudentDashboardTeamSerializer


def _get_incomplete_requirements(team) -> list[str]:
    if team.situation not in {
        TeamSituation.INCOMPLETE,
        TeamSituation.REQUIREMENTS_NOT_MET,
    }:
        return []

    unmet = compute_unmet_requirements(team)
    requirements = []

    if any("mínimo é" in item for item in unmet):
        requirements.append("MIN_MEMBERS")

    if "Sem desafio escolhido." in unmet:
        requirements.append("CHALLENGE_NOT_SELECTED")

    if any(item in unmet for item in ("Projeto sem título.", "Projeto sem resumo.")):
        requirements.append("PROJECT_DATA_MISSING")

    return requirements


def _serialize_edition(edition):
    if edition is None:
        return None

    return {
        "id": edition.pk,
        "year": edition.year,
        "semester": edition.semester,
        "name": edition.name or None,
        "status": edition.status,
    }


def _get_dashboard_stages(edition, project=None):
    stages = Stage.objects.filter(edition=edition).order_by("order")

    scores = {}
    if project:
        scores = {item["stage"].pk: item for item in get_project_scores(project)}

    dashboard_stages = []

    for stage in stages:
        deliverable_status = None
        if project and stage.kind == StageKind.SUBMISSION:
            deliverable_status = get_delivery_status(project, stage)

        score = None
        score_data = scores.get(stage.pk)

        if score_data:
            value = score_data["value"]
            score = {
                "status": score_data["status"],
                "value": str(value) if value is not None else None,
            }

        dashboard_stages.append(
            {
                "stage": {
                    "id": stage.pk,
                    "order": stage.order,
                    "name": stage.name,
                    "kind": stage.kind,
                    "starts_at": stage.starts_at,
                    "ends_at": stage.ends_at,
                    "evaluation_ends_at": stage.evaluation_ends_at,
                    "scored": stage.scored,
                    "max_score": (
                        str(stage.max_score) if stage.max_score is not None else None
                    ),
                    "phase_status": get_phase_status(stage),
                },
                "deliverable_status": deliverable_status,
                "score": score,
            }
        )

    return dashboard_stages


def _get_pending_actions(actor, edition, team, project, is_leader):
    actions = []

    invitations = Invitation.objects.filter(
        student__user=actor,
        team__edition=edition,
        status=InvitationStatus.PENDING,
    ).select_related("team")

    for invitation in invitations:
        actions.append(
            {
                "kind": "INVITATION_RECEIVED",
                "description": (
                    f"Você recebeu um convite para entrar na equipe "
                    f"{invitation.team.name}."
                ),
                "reference_id": invitation.pk,
            }
        )

    if team and is_leader:
        requests = JoinRequest.objects.filter(
            team=team,
            status=RequestStatus.PENDING,
        ).select_related("student__user")

        for request in requests:
            student_name = (
                request.student.user.get_full_name() or request.student.user.email
            )

            actions.append(
                {
                    "kind": "JOIN_REQUEST_TO_REVIEW",
                    "description": (f"{student_name} solicitou entrada na equipe."),
                    "reference_id": request.pk,
                }
            )

    if team and (project is None or not project.title or not project.summary):
        actions.append(
            {
                "kind": "PROJECT_DATA_PENDING",
                "description": "Preencha os dados obrigatórios do projeto.",
                "reference_id": project.pk if project else None,
            }
        )

    if team and project:
        stages = Stage.objects.filter(
            edition=edition,
            kind=StageKind.SUBMISSION,
            starts_at__lte=timezone.now(),
        ).order_by("order")

        for stage in stages:
            if get_delivery_status(project, stage) == "NOT_SUBMITTED":
                actions.append(
                    {
                        "kind": "DELIVERABLE_PENDING",
                        "description": (f"Entregue a atividade da etapa {stage.name}."),
                        "reference_id": stage.pk,
                    }
                )
    return actions


def get_student_dashboard(*, actor: User) -> dict:
    """Retorna os dados do painel do acadêmico na edição publicada."""

    edition = Edition.objects.filter(
        status=EditionStatus.PUBLISHED,
    ).first()

    dashboard = {
        "edition": _serialize_edition(edition),
        "team": None,
        "is_leader": False,
        "incomplete_requirements": [],
        "project": None,
        "stages": _get_dashboard_stages(edition) if edition else [],
        "pending_actions": [],
    }

    if edition is None:
        return dashboard

    membership = (
        TeamMember.objects.filter(
            student__user=actor,
            edition=edition,
            active=True,
        )
        .select_related("team", "team__edition")
        .first()
    )

    if membership is None:
        dashboard["pending_actions"] = _get_pending_actions(
            actor,
            edition,
            None,
            None,
            False,
        )
        return dashboard

    team = membership.team
    project = getattr(team, "project", None)
    is_leader = membership.role == MemberRole.LEADER

    dashboard.update(
        {
            "team": StudentDashboardTeamSerializer(team).data,
            "is_leader": is_leader,
            "incomplete_requirements": _get_incomplete_requirements(team),
            "project": ProjectSerializer(project).data if project else None,
            "stages": _get_dashboard_stages(edition, project),
            "pending_actions": _get_pending_actions(
                actor,
                edition,
                team,
                project,
                is_leader,
            ),
        }
    )

    return dashboard
