from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.enums import UserRole
from apps.accounts.models import (
    EmailDomain,
    ExternalReviewer,
    Student,
    Teacher,
    TeacherCourse,
    User,
)
from apps.core.models import Course

STUDENT_DOMAIN = "aluno.desafiox.local"
TEACHER_DOMAIN = "professor.desafiox.local"


class Command(BaseCommand):
    help = "Cria um usuário de cada perfil para desenvolvimento local."

    def add_arguments(self, parser):
        parser.add_argument("--password", required=True, help="Senha dos usuários.")

    @transaction.atomic
    def handle(self, *args, password, **options):
        # Senha conhecida por todos: nunca rodar fora do ambiente local.
        if not settings.DEBUG:
            raise CommandError("seed_users só roda com DEBUG=True.")

        EmailDomain.objects.get_or_create(
            name=STUDENT_DOMAIN, defaults={"role": UserRole.STUDENT}
        )
        EmailDomain.objects.get_or_create(
            name=TEACHER_DOMAIN, defaults={"role": UserRole.TEACHER}
        )
        course = Course.objects.get(name="Engenharia de Software")

        # O papel ADMIN já dá acesso ao painel (User.save).
        self.user("admin@desafiox.local", password, UserRole.ADMIN, "Administrador")

        student = self.user(
            f"aluno@{STUDENT_DOMAIN}", password, UserRole.STUDENT, "Aluno Seed"
        )
        Student.objects.get_or_create(
            user=student,
            defaults={"registration_number": "SEED001", "course": course, "term": 1},
        )

        teacher_user = self.user(
            f"professor@{TEACHER_DOMAIN}", password, UserRole.TEACHER, "Professor Seed"
        )
        teacher, _ = Teacher.objects.get_or_create(user=teacher_user)
        TeacherCourse.objects.get_or_create(teacher=teacher, course=course)

        reviewer = self.user(
            "avaliador@empresa.local",
            password,
            UserRole.EXTERNAL_REVIEWER,
            "Avaliador Seed",
        )
        ExternalReviewer.objects.get_or_create(
            user=reviewer, defaults={"institution": "Empresa Parceira"}
        )

        self.stdout.write(self.style.SUCCESS("Usuários de desenvolvimento criados."))

    def user(self, email, password, role, name):
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "name": name,
                "role": role,
                "is_active": True,
                "email_confirmed": True,
            },
        )
        if created:
            user.set_password(password)
            user.save(update_fields=["password"])
        return user
