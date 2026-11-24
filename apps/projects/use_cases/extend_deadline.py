"""UC14 (prorrogação) — Prorrogar o prazo de entrega de uma equipe. RF14. P-21."""

from datetime import datetime

from django.db import IntegrityError, transaction

from apps.accounts.models import User
from apps.accounts.rules import ensure_actor_is_admin
from apps.editions.models import Stage
from apps.editions.rules import ensure_edition_not_closed
from apps.projects.exceptions import DeadlineExtensionAlreadyGranted
from apps.projects.models import DeadlineExtension, Project
from apps.projects.rules import ensure_no_extension_for_stage


@transaction.atomic
def extend_deadline(
    *, actor: User, project: Project, stage: Stage, ends_at: datetime, reason: str
) -> DeadlineExtension:
    """Grava a prorrogação do prazo da equipe na etapa, com a justificativa do admin.

    O registro é o histórico: depois de gravado, ninguém altera nem apaga.

    Levanta NotAdminActor se o actor não for admin, EditionClosed se a edição
    estiver encerrada, DeadlineExtensionAlreadyGranted se a equipe já tem
    prorrogação na etapa e ValidationError se a etapa for de outra edição, o novo
    prazo não for depois do fim da etapa ou a justificativa estiver vazia.
    """
    ensure_actor_is_admin(actor)
    ensure_edition_not_closed(project.edition)
    ensure_no_extension_for_stage(project, stage)

    extension = DeadlineExtension(
        project=project,
        stage=stage,
        ends_at=ends_at,
        reason=reason.strip(),
        granted_by=actor,
    )
    extension.full_clean()
    try:
        # Savepoint próprio: o IntegrityError da corrida não envenena a transação.
        with transaction.atomic():
            extension.save()
    except IntegrityError:
        raise DeadlineExtensionAlreadyGranted() from None
    return extension
