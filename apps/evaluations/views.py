from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdmin, IsExternalReviewer, IsStudent, IsTeacher
from apps.editions.models import Edition, Stage
from apps.evaluations.models import (
    Evaluation,
    EvaluationItem,
    FinalEvaluation,
    FinalForm,
    FinalQuestion,
)
from apps.evaluations.rules import (
    ensure_final_form_published,
    ensure_reviewer_covers_finalist,
    ensure_stage_is_evaluable,
    ensure_teacher_in_challenge_course,
)
from apps.evaluations.selectors import (
    get_project_scores,
    list_finalists,
    list_teacher_rows,
)
from apps.evaluations.serializers import (
    EvaluationFormSerializer,
    EvaluationSerializer,
    EvaluationWriteSerializer,
    FinalEvaluationFormSerializer,
    FinalEvaluationSerializer,
    FinalEvaluationWriteSerializer,
    FinalFormSerializer,
    FinalFormWriteSerializer,
    FinalistQuerySerializer,
    FinalistRowSerializer,
    ProjectScoresSerializer,
    RectificationSerializer,
    RectificationWriteSerializer,
    TeacherProjectQuerySerializer,
    TeacherProjectRowSerializer,
)
from apps.evaluations.use_cases.configure_final_form import configure_final_form
from apps.evaluations.use_cases.evaluate_finalist import evaluate_finalist
from apps.evaluations.use_cases.evaluate_submission import evaluate_submission
from apps.evaluations.use_cases.publish_final_form import publish_final_form
from apps.evaluations.use_cases.rectify_score import rectify_score
from apps.projects.models import Project
from apps.projects.rules import ensure_actor_can_view_project
from config.pagination import DefaultPagination


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
        try:
            ensure_stage_is_evaluable(stage)
        except DjangoValidationError as e:
            # Sem avaliação do professor não há formulário: 404, como no contrato.
            raise NotFound("A etapa não tem avaliação do professor.") from e
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
            comment=data["comment"] or "",
            finalize=data["status"] == "FINALIZED",
        )
        evaluation = get_evaluation(project, stage, request.user)
        return Response(EvaluationSerializer(evaluation).data)


class TeacherProjectListView(APIView):
    permission_classes = [IsTeacher]

    def get(self, request):
        query = TeacherProjectQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        rows = list_teacher_rows(teacher=request.user.teacher, **query.validated_data)
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        return paginator.get_paginated_response(
            TeacherProjectRowSerializer(page, many=True).data
        )


class ProjectScoresView(APIView):
    permission_classes = [IsStudent | IsTeacher | IsAdmin]

    def get(self, request, project_id):
        project = Project.objects.select_related("team").filter(pk=project_id).first()
        if project is None:
            raise NotFound("Projeto não encontrado.")
        ensure_actor_can_view_project(project.team, request.user)
        data = {"project": project, "stages": get_project_scores(project)}
        return Response(ProjectScoresSerializer(data).data)


class RectificationCreateView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, evaluation_id):
        if not Evaluation.objects.filter(pk=evaluation_id).exists():
            raise NotFound("Avaliação não encontrada.")
        serializer = RectificationWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        item = EvaluationItem.objects.filter(
            evaluation_id=evaluation_id, stage_criterion_id=data["stage_criterion_id"]
        ).first()
        if item is None:
            raise ValidationError(
                {"stage_criterion_id": "O critério não foi pontuado nesta avaliação."}
            )
        rectification = rectify_score(
            actor=request.user,
            item=item,
            new_points=data["new_points"],
            reason=data["reason"],
        )
        return Response(
            RectificationSerializer(rectification).data, status=status.HTTP_201_CREATED
        )


def get_final_form(edition_id):
    form = FinalForm.objects.filter(edition_id=edition_id).first()
    if form is None:
        raise NotFound("Formulário da etapa final não encontrado.")
    return form


class FinalFormView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request, edition_id):
        return Response(FinalFormSerializer(get_final_form(edition_id)).data)

    def put(self, request, edition_id):
        edition = Edition.objects.filter(pk=edition_id).first()
        if edition is None:
            raise NotFound("Edição não encontrada.")
        serializer = FinalFormWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        form = configure_final_form(
            actor=request.user,
            edition=edition,
            title=serializer.validated_data.get("title"),
            questions=serializer.validated_data["questions"],
        )
        return Response(FinalFormSerializer(form).data)


class FinalFormPublishView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, edition_id):
        form = publish_final_form(actor=request.user, form=get_final_form(edition_id))
        return Response(FinalFormSerializer(form).data)


class FinalistListView(APIView):
    permission_classes = [IsExternalReviewer]

    def get(self, request):
        query = FinalistQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        rows = list_finalists(
            reviewer=request.user.external_reviewer, **query.validated_data
        )
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        return paginator.get_paginated_response(
            FinalistRowSerializer(page, many=True).data
        )


class FinalEvaluationView(APIView):
    permission_classes = [IsExternalReviewer]

    def get_project(self, project_id):
        project = (
            Project.objects.select_related("edition", "challenge__course")
            .filter(pk=project_id)
            .first()
        )
        if project is None:
            raise NotFound("Projeto finalista não encontrado.")
        ensure_reviewer_covers_finalist(self.request.user.external_reviewer, project)
        return project

    def get(self, request, project_id):
        project = self.get_project(project_id)
        form = FinalForm.objects.filter(edition_id=project.edition_id).first()
        ensure_final_form_published(form)
        evaluation = (
            FinalEvaluation.objects.prefetch_related("answers__question")
            .filter(project=project, reviewer=request.user.external_reviewer)
            .first()
        )
        data = {"project": project, "form": form, "evaluation": evaluation}
        return Response(FinalEvaluationFormSerializer(data).data)

    def put(self, request, project_id):
        project = self.get_project(project_id)
        serializer = FinalEvaluationWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        questions = FinalQuestion.objects.in_bulk(
            [a["question_id"] for a in data["answers"]]
        )
        answers = []
        for answer in data["answers"]:
            question = questions.get(answer["question_id"])
            if question is None:
                raise ValidationError({"answers": "Pergunta inexistente."})
            answers.append(
                {
                    "question": question,
                    "value": answer.get("value"),
                    "text": answer.get("text") or "",
                }
            )
        evaluation = evaluate_finalist(
            actor=request.user,
            project=project,
            answers=answers,
            comment=data.get("comment") or "",
            finalize=data["status"] == "EVALUATED",
        )
        return Response(FinalEvaluationSerializer(evaluation).data)
