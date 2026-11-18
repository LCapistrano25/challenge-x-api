from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsTeacher
from apps.editions.models import Stage
from apps.evaluations.models import Evaluation
from apps.evaluations.rules import ensure_teacher_in_challenge_course
from apps.evaluations.serializers import (
    EvaluationFormSerializer,
    EvaluationSerializer,
    EvaluationWriteSerializer,
)
from apps.evaluations.use_cases.evaluate_submission import evaluate_submission
from apps.projects.models import Project


def get_project_and_stage(project_id, stage_id):
    # NotFound do DRF, não Http404: config/exception.py não trata o Http404 puro.
    project = Project.objects.select_related("challenge").filter(pk=project_id).first()
    stage = Stage.objects.filter(pk=stage_id).first()
    if project is None or stage is None:
        raise NotFound("Projeto ou etapa não encontrados.")
    return project, stage


def get_evaluation(project, stage, user):
    return (
        Evaluation.objects.prefetch_related("items")
        .filter(project=project, stage=stage, teacher__user=user)
        .first()
    )


class StageEvaluationView(APIView):
    permission_classes = [IsTeacher]

    def get(self, request, project_id, stage_id):
        project, stage = get_project_and_stage(project_id, stage_id)
        ensure_teacher_in_challenge_course(request.user.teacher, project)
        form = {
            "project": project,
            "stage": stage,
            "criteria": stage.criterion_links.select_related("criterion"),
            "evaluation": get_evaluation(project, stage, request.user),
        }
        return Response(EvaluationFormSerializer(form).data)

    def put(self, request, project_id, stage_id):
        project, stage = get_project_and_stage(project_id, stage_id)
        serializer = EvaluationWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        evaluate_submission(
            actor=request.user,
            project=project,
            stage=stage,
            items=data["items"],
            comment=data["comment"],
            finalize=data["status"] == "FINALIZED",
        )
        evaluation = get_evaluation(project, stage, request.user)
        return Response(EvaluationSerializer(evaluation).data)
