from rest_framework import serializers

from apps.editions.models import StageCriterion
from apps.evaluations.enums import EvaluationStatus


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
