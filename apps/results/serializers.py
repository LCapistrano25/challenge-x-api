from rest_framework import serializers


class FinalistsWriteSerializer(serializers.Serializer):
    # Sem a lista, ficam os 3 primeiros de cada curso (Cap. VIII IV).
    project_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), allow_empty=False, required=False
    )

    def validate_project_ids(self, value):
        if len(set(value)) != len(value):
            raise serializers.ValidationError("Há projeto repetido na lista.")
        return value


class ProjectRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()


class TeamRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    code = serializers.CharField()


class NamedRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class ResultRowSerializer(serializers.Serializer):
    """Linha do ranking, a partir de um ProjectResult classificado."""

    project = ProjectRefSerializer()
    team = TeamRefSerializer(source="project.team")
    course = NamedRefSerializer(source="project.challenge.course")
    category = NamedRefSerializer(source="project.category", allow_null=True)
    final_score = serializers.DecimalField(max_digits=5, decimal_places=2)
    course_rank = serializers.IntegerField()
    finalist = serializers.BooleanField()


class ExcludedProjectSerializer(serializers.Serializer):
    """Projeto fora do ranking, a partir de um Standing."""

    project_id = serializers.IntegerField(source="project.pk")
    team_id = serializers.IntegerField(source="project.team_id")
    reason = serializers.CharField(source="exclusion")


class EditionResultsSerializer(serializers.Serializer):
    edition_id = serializers.IntegerField()
    approved_at = serializers.DateTimeField(allow_null=True)
    results = ResultRowSerializer(many=True)
    excluded = ExcludedProjectSerializer(many=True)
