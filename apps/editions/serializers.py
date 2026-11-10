# apps/editions/serializers.py
from rest_framework import serializers

from apps.editions.models.edition import EditionReviewer


class EvaluatorSummarySerializer(serializers.Serializer):
    user_id = serializers.IntegerField(source="user.pk")
    name = serializers.CharField(source="user.name")
    email = serializers.EmailField(source="user.email")
    institution = serializers.CharField()


class CourseSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class EditionReviewerSerializer(serializers.ModelSerializer):
    evaluator = EvaluatorSummarySerializer(source="reviewer")
    course = CourseSummarySerializer(allow_null=True)

    class Meta:
        model = EditionReviewer
        fields = ["id", "edition_id", "evaluator", "course", "created_at", "updated_at"]
