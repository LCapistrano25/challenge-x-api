from rest_framework.permissions import BasePermission

from apps.accounts.enums import UserRole
from apps.accounts.rules import has_role_profile


class HasRole(BasePermission):
    """Usuário autenticado com o papel da classe e o perfil que ele exige."""

    role = None

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.role == self.role
            and has_role_profile(user)
        )


class IsAdmin(HasRole):
    role = UserRole.ADMIN


class IsStudent(HasRole):
    role = UserRole.STUDENT


class IsTeacher(HasRole):
    role = UserRole.TEACHER


class IsExternalReviewer(HasRole):
    role = UserRole.EXTERNAL_REVIEWER
