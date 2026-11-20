from rest_framework import serializers

from apps.editions.models import StageCriterion
from apps.evaluations.enums import EvaluationStatus, QuestionKind, ScoreStatus
from apps.evaluations.models import StageScore


class EvaluationItemWriteSerializer(serializers.Serializer):
    stage_criterion_id = serializers.PrimaryKeyRelatedField(
        queryset=StageCriterion.objects.all(), source="stage_criterion"
    )
    points = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0)
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class EvaluationWriteSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=EvaluationStatus.choices)
    comment = serializers.CharField(required=False, allow_blank=True, default="")
    items = EvaluationItemWriteSerializer(many=True)


class EvaluationItemSerializer(serializers.Serializer):
    stage_criterion_id = serializers.IntegerField()
    points = serializers.DecimalField(max_digits=5, decimal_places=2)
    comment = serializers.CharField()


class EvaluationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    project_id = serializers.IntegerField()
    stage_id = serializers.IntegerField()
    status = serializers.CharField()
    comment = serializers.CharField()
    items = EvaluationItemSerializer(many=True)
    total = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()
    finalized_at = serializers.DateTimeField(allow_null=True)

    def get_total(self, evaluation):
        return str(sum(item.points for item in evaluation.items.all()))


class CriterionFormSerializer(serializers.Serializer):
    stage_criterion_id = serializers.IntegerField(source="pk")
    criterion = serializers.SerializerMethodField()
    max_score = serializers.DecimalField(max_digits=4, decimal_places=2)

    def get_criterion(self, link):
        criterion = link.criterion
        return {
            "id": criterion.pk,
            "name": criterion.name,
            "description": criterion.rubric,
        }


class EvaluationFormSerializer(serializers.Serializer):
    project = serializers.SerializerMethodField()
    stage = serializers.SerializerMethodField()
    criteria = CriterionFormSerializer(many=True)
    evaluation = EvaluationSerializer(allow_null=True)

    def get_project(self, form):
        return {"id": form["project"].pk, "title": form["project"].title}

    def get_stage(self, form):
        stage = form["stage"]
        return {
            "id": stage.pk,
            "name": stage.name,
            "points_value": str(stage.max_score),
        }


class TeacherProjectQuerySerializer(serializers.Serializer):
    course_id = serializers.IntegerField(required=False)
    stage_id = serializers.IntegerField(required=False)
    pending_only = serializers.BooleanField(required=False, default=False)


class TeacherProjectRowSerializer(serializers.Serializer):
    project = serializers.SerializerMethodField()
    team = serializers.SerializerMethodField()
    challenge_course = serializers.SerializerMethodField()
    stage = serializers.SerializerMethodField()
    deliverable_status = serializers.CharField()
    evaluation_count = serializers.IntegerField()
    min_evaluators = serializers.IntegerField()
    my_evaluation_status = serializers.CharField()

    def get_project(self, row):
        return {"id": row["project"].pk, "title": row["project"].title}

    def get_team(self, row):
        team = row["team"]
        return {"id": team.pk, "name": team.name, "code": team.code}

    def get_challenge_course(self, row):
        course = row["challenge_course"]
        return {"id": course.pk, "name": course.name}

    def get_stage(self, row):
        stage = row["stage"]
        return {"id": stage.pk, "name": stage.name, "position": stage.order}


class StageScoreDetailSerializer(serializers.Serializer):
    stage = serializers.SerializerMethodField()
    points_value = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    value = serializers.DecimalField(
        max_digits=5, decimal_places=2, allow_null=True, coerce_to_string=True
    )
    evaluation_count = serializers.IntegerField()
    min_evaluators = serializers.SerializerMethodField()
    deliverable_status = serializers.CharField()
    criteria = serializers.SerializerMethodField()
    feedback = serializers.SerializerMethodField()

    def get_stage(self, row):
        stage = row["stage"]
        return {"id": stage.pk, "name": stage.name, "position": stage.order}

    def get_points_value(self, row):
        return str(row["stage"].max_score)

    def get_status(self, row):
        # O contrato tem PENDING e FINALIZED; zero sem entrega também é final.
        return "PENDING" if row["status"] == ScoreStatus.PENDING else "FINALIZED"

    def get_min_evaluators(self, row):
        return row["stage"].min_evaluations

    def get_criteria(self, row):
        return [
            {
                "criterion": {"id": c["criterion"].pk, "name": c["criterion"].name},
                "max_score": str(c["max_score"]),
                "average": None if c["average"] is None else str(c["average"]),
            }
            for c in row["criteria"]
        ]

    def get_feedback(self, row):
        return [
            {
                "comment": f["comment"] or None,
                "items": [
                    {
                        "criterion_name": i["criterion_name"],
                        "points": str(i["points"]),
                        "comment": i["comment"] or None,
                    }
                    for i in f["items"]
                ],
            }
            for f in row["feedback"]
        ]


class ProjectScoresSerializer(serializers.Serializer):
    project = serializers.SerializerMethodField()
    stages = StageScoreDetailSerializer(many=True)

    def get_project(self, data):
        return {"id": data["project"].pk, "title": data["project"].title}


class RectificationWriteSerializer(serializers.Serializer):
    stage_criterion_id = serializers.IntegerField()
    new_points = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0)
    reason = serializers.CharField()


class RectificationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    evaluation_id = serializers.IntegerField(source="item.evaluation_id")
    stage_criterion_id = serializers.IntegerField(source="item.stage_criterion_id")
    previous_points = serializers.DecimalField(max_digits=5, decimal_places=2)
    new_points = serializers.DecimalField(max_digits=5, decimal_places=2)
    reason = serializers.CharField()
    rectified_by = serializers.IntegerField(source="rectified_by_id")
    rectified_at = serializers.DateTimeField()
    stage_score = serializers.SerializerMethodField()

    def get_stage_score(self, rectification):
        evaluation = rectification.item.evaluation
        score = StageScore.objects.get(
            project=evaluation.project, stage=evaluation.stage
        )
        return {
            "value": None if score.value is None else str(score.value),
            "evaluation_count": score.evaluation_count,
        }


class FinalQuestionWriteSerializer(serializers.Serializer):
    order = serializers.IntegerField(min_value=1)
    prompt = serializers.CharField()
    kind = serializers.ChoiceField(choices=QuestionKind.choices)
    max_score = serializers.DecimalField(
        max_digits=4, decimal_places=2, required=False, allow_null=True
    )

    def validate(self, data):
        max_score = data.get("max_score")
        if data["kind"] == QuestionKind.SCORE:
            if max_score is None or max_score <= 0:
                raise serializers.ValidationError(
                    {"max_score": "Pergunta de nota exige pontuação máxima positiva."}
                )
        elif max_score is not None:
            raise serializers.ValidationError(
                {"max_score": "Só pergunta de nota tem pontuação máxima."}
            )
        data["max_score"] = max_score
        return data


class FinalFormWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=150, allow_blank=True, allow_null=True)
    questions = FinalQuestionWriteSerializer(many=True, allow_empty=False)

    def validate_questions(self, questions):
        orders = [q["order"] for q in questions]
        if len(orders) != len(set(orders)):
            raise serializers.ValidationError("A ordem das perguntas não pode repetir.")
        return questions


class FinalQuestionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    order = serializers.IntegerField()
    prompt = serializers.CharField()
    kind = serializers.CharField()
    max_score = serializers.DecimalField(
        max_digits=4, decimal_places=2, allow_null=True
    )


class FinalFormSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    edition_id = serializers.IntegerField()
    title = serializers.SerializerMethodField()
    published = serializers.BooleanField()
    questions = FinalQuestionSerializer(many=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    def get_title(self, form):
        return form.title or None


class FinalistQuerySerializer(serializers.Serializer):
    course_id = serializers.IntegerField(required=False)
    category_id = serializers.IntegerField(required=False)


class PublicProjectSerializer(serializers.Serializer):
    """Identidade pública do projeto: nunca traz entrega, nota ou observação."""

    id = serializers.IntegerField()
    edition = serializers.SerializerMethodField()
    title = serializers.CharField()
    summary = serializers.CharField()
    course = serializers.SerializerMethodField()
    sdg = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()

    def get_edition(self, project):
        edition = project.edition
        return {
            "id": edition.pk,
            "year": edition.year,
            "semester": edition.semester,
            "name": edition.name or None,
            "status": edition.status,
        }

    def get_course(self, project):
        course = project.challenge.course
        return {"id": course.pk, "name": course.name}

    def get_sdg(self, project):
        sdg = project.challenge.sdg
        return {"id": sdg.pk, "number": sdg.number, "title": sdg.title}

    def get_category(self, project):
        category = project.category
        return {"id": category.pk, "name": category.name} if category else None

    def get_members(self, project):
        members = project.team.members.filter(active=True).select_related(
            "student__user"
        )
        return [{"name": member.student.user.name} for member in members]


class FinalistRowSerializer(serializers.Serializer):
    project = PublicProjectSerializer()
    team = serializers.SerializerMethodField()
    my_evaluation_status = serializers.CharField()

    def get_team(self, row):
        team = row["team"]
        return {"id": team.pk, "name": team.name, "code": team.code}


class FinalAnswerWriteSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    value = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True
    )
    answer_text = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )


class FinalEvaluationWriteSerializer(serializers.Serializer):
    # IN_PROGRESS salva o rascunho; FINALIZED tranca a avaliação.
    status = serializers.ChoiceField(choices=["IN_PROGRESS", "FINALIZED"])
    comment = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    answers = FinalAnswerWriteSerializer(many=True)


class FinalAnswerSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    type = serializers.CharField(source="question.kind")
    value = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    answer_text = serializers.SerializerMethodField()

    def get_answer_text(self, answer):
        return answer.text or None


class FinalEvaluationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField()
    comment = serializers.SerializerMethodField()
    answers = FinalAnswerSerializer(many=True)
    finalized_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    def get_comment(self, evaluation):
        return evaluation.comment or None


class FinalEvaluationFormSerializer(serializers.Serializer):
    project = PublicProjectSerializer()
    form = FinalFormSerializer()
    evaluation = FinalEvaluationSerializer(allow_null=True)
