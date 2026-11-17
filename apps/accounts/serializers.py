from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)

    def validate_email(self, value):
        return value.strip().lower()


class MicrosoftLoginSerializer(serializers.Serializer):
    code = serializers.CharField()


class StudentProfileSerializer(serializers.Serializer):
    registration_number = serializers.CharField(max_length=30)
    course_id = serializers.IntegerField()
    term = serializers.IntegerField(min_value=1)


class TeacherProfileSerializer(serializers.Serializer):
    course_ids = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False
    )

    def validate_course_ids(self, value):
        if len(set(value)) != len(value):
            raise serializers.ValidationError("Curso repetido.")
        return value


class ExternalReviewSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    # Opcional e anulável no contrato; o model guarda vazio.
    institution = serializers.CharField(
        max_length=150, required=False, allow_blank=True, allow_null=True
    )

    def validate_email(self, value):
        return value.strip().lower()

    def validate_institution(self, value):
        return value or ""
