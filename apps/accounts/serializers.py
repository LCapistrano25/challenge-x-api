from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    # shortcut: o contrato usa "password"; "senha" fica até combinar com o front.
    senha = serializers.CharField(trim_whitespace=False)

    def validate_email(self, value):
        return value.strip().lower()


class StudentProfileSerializer(serializers.Serializer):
    registration_number = serializers.CharField(max_length=30)
    course_id = serializers.IntegerField()
    term = serializers.IntegerField(min_value=1)
