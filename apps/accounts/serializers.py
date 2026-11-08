from rest_framework import serializers


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    registration_number = serializers.CharField(max_length=50)
    course_id = serializers.IntegerField()
    term = serializers.IntegerField(min_value=1)

    def validate_email(self, value):
        return value.strip().lower()


class ConfirmEmailSerializer(serializers.Serializer):
    token = serializers.CharField()


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    # shortcut: o contrato usa "password"; "senha" fica até combinar com o front.
    senha = serializers.CharField(trim_whitespace=False)

    def validate_email(self, value):
        return value.strip().lower()
