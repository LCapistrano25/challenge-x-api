from collections import Counter, defaultdict
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import ExternalReviewer, Teacher
from apps.editions.enums import EditionStatus, StageKind
from apps.editions.models import EditionReviewer, Stage
from apps.evaluations.enums import EvaluationStatus, FinalEvaluationStatus, ScoreStatus
from apps.evaluations.exceptions import FinalFormNotPublished
from apps.evaluations.models import Evaluation, FinalEvaluation, FinalForm, StageScore
from apps.projects.enums import DeliveryStatus
from apps.projects.models import DeadlineExtension, Project, SubmissionVersion
from apps.projects.selectors import get_delivery_status


def list_teacher_rows(
    *,
    teacher: Teacher,
    course_id: int | None = None,
    stage_id: int | None = None,
    pending_only: bool = False,
) -> list[dict]:
    """Painel do professor: uma linha por projeto e etapa avaliável (RF37).

    Vale para projetos de edição publicada cujo desafio é de curso com vínculo
    ativo do professor. O status da entrega é derivado (P-27): versão no prazo
    da equipe = enviada; sem versão, prazo aberto = não enviada e prazo
    encerrado = não entregue.

    shortcut: monta as linhas em memória, em poucas consultas; trocar por
    paginação no banco se a edição passar de alguns milhares de projetos. A regra
    é a de projects.selectors.get_delivery_status, aqui em lote para evitar uma
    consulta por linha.
    """
    course_ids = set(
        teacher.course_links.filter(active=True).values_list("course_id", flat=True)
    )
    if course_id is not None:
        course_ids &= {course_id}
    projects = list(
        Project.objects.filter(
            challenge__course_id__in=course_ids,
            edition__status=EditionStatus.PUBLISHED,
        )
        .select_related("team", "challenge__course")
        .order_by("pk")
    )
    stages = Stage.objects.filter(
        edition_id__in={p.edition_id for p in projects},
        kind=StageKind.SUBMISSION,
        scored=True,
    ).order_by("order")
    if stage_id is not None:
        stages = stages.filter(pk=stage_id)
    stages = list(stages)

    sent_at = defaultdict(list)
    for project_id, sid, at in SubmissionVersion.objects.filter(
        submission__project__in=projects, submission__stage__in=stages
    ).values_list("submission__project_id", "submission__stage_id", "submitted_at"):
        sent_at[project_id, sid].append(at)
    extensions = {
        (project_id, sid): ends_at
        for project_id, sid, ends_at in DeadlineExtension.objects.filter(
            project__in=projects, stage__in=stages
        ).values_list("project_id", "stage_id", "ends_at")
    }
    finalized = Counter()
    mine = {}
    for project_id, sid, teacher_id, status in Evaluation.objects.filter(
        project__in=projects, stage__in=stages
    ).values_list("project_id", "stage_id", "teacher_id", "status"):
        if status == EvaluationStatus.FINALIZED:
            finalized[project_id, sid] += 1
        if teacher_id == teacher.pk:
            mine[project_id, sid] = status

    now = timezone.now()
    rows = []
    for project in projects:
        for stage in stages:
            if stage.edition_id != project.edition_id:
                continue
            key = (project.pk, stage.pk)
            deadline = extensions.get(key, stage.ends_at)
            if any(at <= deadline for at in sent_at[key]):
                deliverable = DeliveryStatus.SUBMITTED
            elif now <= deadline:
                deliverable = DeliveryStatus.NOT_SUBMITTED
            else:
                deliverable = DeliveryStatus.NOT_DELIVERED
            my_status = mine.get(key, "NOT_STARTED")
            if pending_only and (
                deliverable != DeliveryStatus.SUBMITTED
                or my_status == EvaluationStatus.FINALIZED
            ):
                continue
            rows.append(
                {
                    "project": project,
                    "team": project.team,
                    "challenge_course": project.challenge.course,
                    "stage": stage,
                    "deliverable_status": deliverable,
                    "evaluation_count": finalized[key],
                    "min_evaluators": stage.min_evaluations,
                    "my_evaluation_status": my_status,
                }
            )
    return rows


def get_project_scores(project: Project) -> list[dict]:
    """Nota, média por critério e feedbacks de cada etapa pontuada do projeto (RF32).

    Enquanto a nota está pendente (menos avaliações que o mínimo), valor, médias
    e feedbacks ficam ocultos: eles revelariam a nota de um único professor.
    """
    stages = Stage.objects.filter(
        edition_id=project.edition_id, kind=StageKind.SUBMISSION, scored=True
    ).order_by("order")
    scores = {s.stage_id: s for s in StageScore.objects.filter(project=project)}
    finalized = defaultdict(list)
    evaluations = Evaluation.objects.filter(
        project=project, status=EvaluationStatus.FINALIZED
    ).prefetch_related("items__stage_criterion__criterion")
    for evaluation in evaluations:
        finalized[evaluation.stage_id].append(evaluation)

    result = []
    for stage in stages:
        score = scores.get(stage.pk)
        status = score.status if score else ScoreStatus.PENDING
        visible = status != ScoreStatus.PENDING
        evaluations = finalized[stage.pk]
        criteria = []
        for link in stage.criterion_links.select_related("criterion"):
            points = [
                item.points
                for evaluation in evaluations
                for item in evaluation.items.all()
                if item.stage_criterion_id == link.pk
            ]
            average = None
            if visible and points:
                average = (sum(points) / len(points)).quantize(Decimal("0.01"))
            criteria.append(
                {
                    "criterion": link.criterion,
                    "max_score": link.max_score,
                    "average": average,
                }
            )
        feedback = [
            {
                "comment": evaluation.comment,
                "items": [
                    {
                        "criterion_name": item.stage_criterion.criterion.name,
                        "points": item.points,
                        "comment": item.comment,
                    }
                    for item in evaluation.items.all()
                ],
            }
            for evaluation in evaluations
            if visible
        ]
        result.append(
            {
                "stage": stage,
                "status": status,
                "value": score.value if score and visible else None,
                "evaluation_count": score.evaluation_count if score else 0,
                "deliverable_status": get_delivery_status(project, stage),
                "criteria": criteria,
                "feedback": feedback,
            }
        )
    return result


def list_finalists(
    *,
    reviewer: ExternalReviewer,
    course_id: int | None = None,
    category_id: int | None = None,
) -> list[dict]:
    """Finalistas da edição vigente dentro da abrangência do avaliador (RF42).

    Vínculo sem curso cobre todos os cursos; com curso, só os desafios dele.
    Levanta FinalFormNotPublished se a edição ainda não publicou o formulário.
    """
    links = list(
        EditionReviewer.objects.filter(
            reviewer=reviewer, edition__status=EditionStatus.PUBLISHED
        )
    )
    published = set(
        FinalForm.objects.filter(
            published=True, edition_id__in=[link.edition_id for link in links]
        ).values_list("edition_id", flat=True)
    )
    if links and not published:
        raise FinalFormNotPublished
    scope = Q(pk__in=[])
    for link in links:
        if link.edition_id in published:
            scope |= Q(edition_id=link.edition_id) & (
                Q(challenge__course_id=link.course_id) if link.course_id else Q()
            )
    projects = (
        Project.objects.filter(scope, result__finalist=True)
        .select_related(
            "team", "edition", "challenge__course", "challenge__sdg", "category"
        )
        .order_by("pk")
    )
    if course_id is not None:
        projects = projects.filter(challenge__course_id=course_id)
    if category_id is not None:
        projects = projects.filter(category_id=category_id)
    statuses = dict(
        FinalEvaluation.objects.filter(reviewer=reviewer).values_list(
            "project_id", "status"
        )
    )
    return [
        {
            "project": project,
            "team": project.team,
            "my_evaluation_status": statuses.get(
                project.pk, FinalEvaluationStatus.PENDING
            ),
        }
        for project in projects
    ]
