from rest_framework import serializers

from apps.accounts.rules import MICROSOFT_ROLES

# Formato e unicidade do nome ficam em rules.py, chamadas pelos casos de uso.
INSTITUTIONAL_ROLE_CHOICES = sorted(MICROSOFT_ROLES)


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
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    # Opcional e anulável no contrato; o model guarda vazio.
    institution = serializers.CharField(
        max_length=150, required=False, allow_blank=True, allow_null=True
    )

    def validate_email(self, value):
        return value.strip().lower()

    def validate_institution(self, value):
        return value or ""


class EmailDomainFilterSerializer(serializers.Serializer):
    active = serializers.BooleanField(required=False, allow_null=True, default=None)
    role = serializers.ChoiceField(
        choices=INSTITUTIONAL_ROLE_CHOICES, required=False, allow_blank=True
    )


class EmailDomainCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    role = serializers.ChoiceField(choices=INSTITUTIONAL_ROLE_CHOICES)
    active = serializers.BooleanField(default=True)


class AtLeastOneFieldSerializer(serializers.Serializer):
    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "Informe ao menos um campo para atualizar."
            )
        return attrs


class AdminUserFilterSerializer(serializers.Serializer):
    search = serializers.CharField(required=False, allow_blank=True)
    active = serializers.BooleanField(required=False, allow_null=True, default=None)
    course_id = serializers.IntegerField(required=False)


class StudentAdminUpdateSerializer(AtLeastOneFieldSerializer):
    name = serializers.CharField(max_length=150, required=False)
    registration_number = serializers.CharField(max_length=30, required=False)
    course_id = serializers.IntegerField(required=False)
    term = serializers.IntegerField(min_value=1, required=False)


class TeacherCourseLinkWriteSerializer(serializers.Serializer):
    course_id = serializers.IntegerField()
    active = serializers.BooleanField()


class TeacherAdminUpdateSerializer(AtLeastOneFieldSerializer):
    name = serializers.CharField(max_length=150, required=False)
    courses = TeacherCourseLinkWriteSerializer(many=True, required=False)

    def validate_courses(self, value):
        ids = [link["course_id"] for link in value]
        if len(set(ids)) != len(ids):
            raise serializers.ValidationError("Curso repetido.")
        return value


class ExternalEvaluatorAdminUpdateSerializer(AtLeastOneFieldSerializer):
    name = serializers.CharField(max_length=150, required=False)
    # Anulável no contrato; o model guarda vazio.
    institution = serializers.CharField(
        max_length=150, required=False, allow_blank=True, allow_null=True
    )

    def validate_institution(self, value):
        return value or ""


class EmailDomainUpdateSerializer(AtLeastOneFieldSerializer):
    name = serializers.CharField(max_length=100, required=False)
    role = serializers.ChoiceField(choices=INSTITUTIONAL_ROLE_CHOICES, required=False)
    active = serializers.BooleanField(required=False)


class UserStatusUpdateSerializer(serializers.Serializer):
    active = serializers.BooleanField()
