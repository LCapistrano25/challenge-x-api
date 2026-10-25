import factory
from factory.django import DjangoModelFactory

from apps.core.models import Course, Sdg


class CourseFactory(DjangoModelFactory):
    class Meta:
        model = Course

    name = factory.Sequence(lambda n: f"Curso {n}")
    term_count = 8


class SdgFactory(DjangoModelFactory):
    class Meta:
        model = Sdg
        # As ODS 1, 2, 3, 9 e 16 já vêm do seed; reaproveita em vez de duplicar.
        django_get_or_create = ("number",)

    number = factory.Sequence(lambda n: n % 17 + 1)
    title = factory.LazyAttribute(lambda o: f"ODS {o.number}")
