from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection
from django.db.models import ProtectedError
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

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


class ProfileValidationTests(TestCase):
    """Validações que o admin aplica via full_clean()."""

    def test_periodo_acima_do_curso_e_recusado(self):
        user = User.objects.create_user("a@teste.com", "x", role=UserRole.STUDENT)
        course = Course.objects.get(name="Engenharia de Software")  # 8 períodos
        student = Student(user=user, registration_number="1", course=course, term=9)

        with self.assertRaisesMessage(ValidationError, "entre 1 e 8"):
            student.full_clean()

        student.term = 8
        student.full_clean()

    def test_perfil_exige_usuario_do_mesmo_papel(self):
        aluno = User.objects.create_user("a@teste.com", "x", role=UserRole.STUDENT)

        for profile in (Teacher(user=aluno), ExternalReviewer(user=aluno)):
            with self.subTest(profile=type(profile).__name__):
                with self.assertRaises(ValidationError):
                    profile.full_clean()


class AdminListQueriesTests(TestCase):
    def test_lista_de_alunos_nao_faz_consulta_por_linha(self):
        admin = User.objects.create_superuser("admin@teste.com", "x")
        self.client.force_login(admin)
        course = Course.objects.get(name="Direito")

        def add_students(start, count):
            for i in range(start, start + count):
                user = User.objects.create_user(f"a{i}@t.com", "x", role="STUDENT")
                Student.objects.create(
                    user=user, registration_number=str(i), course=course, term=1
                )

        def list_queries():
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(
                    "/admin/accounts/student/", HTTP_HOST="localhost"
                )
            self.assertEqual(response.status_code, 200)
            return len(queries)

        add_students(0, 1)
        one = list_queries()
        add_students(1, 10)

        self.assertEqual(list_queries(), one)


class UserAdminPagesTests(TestCase):
    def test_telas_de_usuario_abrem_com_nome_unico(self):
        admin = User.objects.create_superuser("admin@teste.com", "x", name="Admin")
        self.client.force_login(admin)

        for url in (
            "/admin/accounts/user/",
            "/admin/accounts/user/add/",
            f"/admin/accounts/user/{admin.pk}/change/",
        ):
            with self.subTest(url=url):
                response = self.client.get(url, HTTP_HOST="localhost")
                self.assertEqual(response.status_code, 200)

        self.assertEqual(admin.get_full_name(), "Admin")
