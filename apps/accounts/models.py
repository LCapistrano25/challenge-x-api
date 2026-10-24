from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.accounts.enums import UserRole
from apps.core.models import TimeStampedModel


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("O e-mail é obrigatório.")

        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", UserRole.ADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superusuário precisa ter is_staff=True.")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superusuário precisa ter is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Usuário do sistema, autenticado por e-mail (RF01, RF18, RF19, RF36, RF41)."""

    username = None

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=UserRole)
    email_confirmed = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"


class EmailDomain(models.Model):
    """Domínio institucional de e-mail que define o perfil no cadastro (RF02)."""

    name = models.CharField(max_length=255, unique=True)
    active = models.BooleanField(default=True)
    role = models.CharField(max_length=20, choices=UserRole)

    class Meta:
        verbose_name = "domínio de e-mail"
        verbose_name_plural = "domínios de e-mail"

    def __str__(self):
        return f"{self.name} - {self.role}"


# Os perfis estendem o User um para um; sem o usuário não fazem sentido (CASCADE).


class Student(TimeStampedModel):
    """Acadêmico: dados informados no autocadastro (RF19)."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="student",
        limit_choices_to={"role": UserRole.STUDENT},
    )
    registration_number = models.CharField(max_length=30, unique=True)
    course = models.ForeignKey(
        "core.Course", on_delete=models.PROTECT, related_name="students"
    )
    term = models.PositiveSmallIntegerField()

    class Meta:
        verbose_name = "acadêmico"
        verbose_name_plural = "acadêmicos"
        constraints = [
            models.CheckConstraint(condition=Q(term__gte=1), name="student_term_gte_1"),
        ]

    def clean(self):
        # O limite depende de outra tabela, então não cabe numa constraint (RN10).
        if self.course_id and self.term and self.term > self.course.term_count:
            raise ValidationError(
                {"term": f"O período deve estar entre 1 e {self.course.term_count}."}
            )

    def __str__(self):
        return f"{self.user.email} ({self.registration_number})"


class Teacher(TimeStampedModel):
    """Professor, vinculado a um ou mais cursos (RF10, RF36)."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="teacher",
        limit_choices_to={"role": UserRole.TEACHER},
    )
    courses = models.ManyToManyField(
        "core.Course", through="TeacherCourse", related_name="teachers"
    )

    class Meta:
        verbose_name = "professor"
        verbose_name_plural = "professores"

    def __str__(self):
        return self.user.email


class TeacherCourse(TimeStampedModel):
    """Vínculo professor–curso; define o escopo de avaliação (RF10, RN04)."""

    # O vínculo não existe sem o professor (CASCADE); o curso é protegido.
    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, related_name="course_links"
    )
    course = models.ForeignKey(
        "core.Course", on_delete=models.PROTECT, related_name="teacher_links"
    )
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "vínculo professor–curso"
        verbose_name_plural = "vínculos professor–curso"
        constraints = [
            models.UniqueConstraint(
                fields=["teacher", "course"], name="unique_course_per_teacher"
            ),
        ]

    def __str__(self):
        return f"{self.teacher} - {self.course}"


class ExternalReviewer(TimeStampedModel):
    """Avaliador externo; o vínculo com a edição fica em editions (RF11)."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="external_reviewer",
        limit_choices_to={"role": UserRole.EXTERNAL_REVIEWER},
    )
    institution = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "avaliador externo"
        verbose_name_plural = "avaliadores externos"

    def __str__(self):
        return self.user.email
