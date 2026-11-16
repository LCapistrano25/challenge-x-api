from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)

    def validate_email(self, value):
        return value.strip().lower()


class StudentProfileSerializer(serializers.Serializer):
    registration_number = serializers.CharField(max_length=30)
    course_id = serializers.IntegerField()
    term = serializers.IntegerField(min_value=1)


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
