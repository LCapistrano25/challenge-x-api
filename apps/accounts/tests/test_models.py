from django.db import IntegrityError
from django.db.models import ProtectedError
from django.test import TestCase

from apps.accounts.enums import UserRole
from apps.accounts.models import EmailDomain, Student, Teacher, TeacherCourse, User
from apps.core.models import Course


class UserManagerTests(TestCase):
    def test_create_user_normaliza_email(self):
        user = User.objects.create_user(
            "Aluno@Aluno.Unicatolica.edu.br", "TesteForte!2026x"
        )

        self.assertEqual(user.email, "aluno@aluno.unicatolica.edu.br")
        self.assertTrue(user.check_password("TesteForte!2026x"))

    def test_create_superuser_e_admin(self):
        user = User.objects.create_superuser("admin@teste.com", "TesteForte!2026x")

        self.assertEqual(user.role, UserRole.ADMIN)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_role_comporta_external_reviewer(self):
        user = User.objects.create_user(
            "avaliador@empresa.com",
            "TesteForte!2026x",
            role=UserRole.EXTERNAL_REVIEWER,
        )

        user.refresh_from_db()
        self.assertEqual(user.role, UserRole.EXTERNAL_REVIEWER)


class ConstraintTests(TestCase):
    def test_email_unico(self):
        User.objects.create_user("a@teste.com", "x")

        with self.assertRaises(IntegrityError):
            User.objects.create_user("a@teste.com", "x")

    def test_dominio_unico(self):
        EmailDomain.objects.create(name="teste.edu.br", role=UserRole.STUDENT)

        with self.assertRaises(IntegrityError):
            EmailDomain.objects.create(name="teste.edu.br", role=UserRole.TEACHER)

    def student(self, email, registration_number, term=1):
        user = User.objects.create_user(email, "x", role=UserRole.STUDENT)
        course = Course.objects.get(name="Direito")
        return Student.objects.create(
            user=user, registration_number=registration_number, course=course, term=term
        )

    def test_matricula_unica(self):
        self.student("a@teste.com", "123")

        with self.assertRaises(IntegrityError):
            self.student("b@teste.com", "123")

    def test_periodo_do_aluno_comeca_em_1(self):
        with self.assertRaises(IntegrityError):
            self.student("a@teste.com", "123", term=0)

    def test_professor_nao_repete_curso(self):
        user = User.objects.create_user("prof@teste.com", "x", role=UserRole.TEACHER)
        teacher = Teacher.objects.create(user=user)
        course = Course.objects.get(name="Direito")
        TeacherCourse.objects.create(teacher=teacher, course=course)

        with self.assertRaises(IntegrityError):
            TeacherCourse.objects.create(teacher=teacher, course=course)

    def test_curso_com_aluno_nao_pode_ser_apagado(self):
        aluno = self.student("a@teste.com", "123")

        with self.assertRaises(ProtectedError):
            aluno.course.delete()
