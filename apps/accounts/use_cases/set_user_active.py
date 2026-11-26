"""Ativar ou desativar usuário da plataforma pelo administrador (RFXX)."""

from django.db import transaction

from apps.accounts.exceptions import UserNotFound
from apps.accounts.models import User
from apps.accounts.rules import PROFILE_BY_ROLE, ensure_actor_is_admin


@transaction.atomic
def set_user_active(*, actor: User, user_id: int, role: str, active: bool) -> User:
    """Grava o status explícito do usuário com o papel da rota.

    Contas ADMIN nunca chegam aqui: o papel vem da rota (aluno, professor ou
    avaliador). A sessão aberta cai porque a autenticação confere is_active a
    cada requisição; nada é excluído.
    """
    ensure_actor_is_admin(actor)
    # Como na consulta da rota, só conta quem tem o perfil do papel.
    profile = {f"{PROFILE_BY_ROLE[role]}__isnull": False}
    user = User.objects.filter(pk=user_id, role=role, **profile).first()
    if user is None:
        raise UserNotFound()
    user.is_active = active
    user.save(update_fields=["is_active", "updated_at"])
    return user
