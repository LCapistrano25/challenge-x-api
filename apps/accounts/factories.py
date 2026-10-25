import factory
from factory.django import DjangoModelFactory

from apps.accounts.enums import UserRole
from apps.accounts.models import (
    EmailDomain,
    ExternalReviewer,
    Student,
    Teacher,
    TeacherCourse,
    User,
)
from apps.core.factories import CourseFactory


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"usuario{n}@teste.com")
    name = factory.Sequence(lambda n: f"Usuário {n}")
    role = UserRole.STUDENT
    is_active = True
    email_confirmed = True
    password = factory.PostGenerationMethodCall("set_password", "TesteForte!2026x")

    @factory.post_generation
    def save_password(self, create, extracted, **kwargs):
        if create:
            self.save(update_fields=["password"])


class EmailDomainFactory(DjangoModelFactory):
    class Meta:
        model = EmailDomain

    name = factory.Sequence(lambda n: f"dominio{n}.edu.br")
    role = UserRole.STUDENT


class StudentFactory(DjangoModelFactory):
    class Meta:
        model = Student

    user = factory.SubFactory(UserFactory, role=UserRole.STUDENT)
    registration_number = factory.Sequence(lambda n: f"2026{n:05d}")
    course = factory.SubFactory(CourseFactory)
    term = 3


class TeacherFactory(DjangoModelFactory):
    class Meta:
        model = Teacher

    user = factory.SubFactory(UserFactory, role=UserRole.TEACHER)


class TeacherCourseFactory(DjangoModelFactory):
    class Meta:
        model = TeacherCourse

    teacher = factory.SubFactory(TeacherFactory)
    course = factory.SubFactory(CourseFactory)


class ExternalReviewerFactory(DjangoModelFactory):
    class Meta:
        model = ExternalReviewer

    user = factory.SubFactory(UserFactory, role=UserRole.EXTERNAL_REVIEWER)
    institution = "Empresa Parceira"
