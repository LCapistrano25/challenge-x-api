from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

from apps.accounts.enums import UserRole


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

    # shortcut: dados do aluno ficam no User até o model Student existir.
    registration_number = models.CharField(
        max_length=30,
        unique=True,
        null=True,
        blank=True,
    )
    course = models.CharField(max_length=150, blank=True)
    term = models.PositiveSmallIntegerField(null=True, blank=True)
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
