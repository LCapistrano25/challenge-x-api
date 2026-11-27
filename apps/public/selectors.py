from django.db.models import Prefetch, Q, QuerySet

from apps.editions.enums import EditionStatus
from apps.editions.models import Challenge, Edition
from apps.projects.enums import ProjectStatus
from apps.projects.models import Project
from apps.results.models import ProjectResult
from apps.teams.enums import TeamStatus
from apps.teams.models import TeamMember


def get_current_edition() -> Edition | None:
    """Edição vigente: a publicada (RF44, P-41), com etapas, ODS e desafios."""
    return (
        Edition.objects.filter(status=EditionStatus.PUBLISHED)
        .prefetch_related(
            "stages",
            "sdg_links__sdg",
            Prefetch(
                "challenges",
                queryset=Challenge.objects.filter(active=True).select_related(
                    "course", "sdg"
                ),
            ),
        )
        .first()
    )


def list_closed_editions() -> QuerySet[Edition]:
    """Edições encerradas (RF35, RF46)."""
    return Edition.objects.filter(status=EditionStatus.CLOSED).order_by(
        "-year", "-semester"
    )


def list_edition_winners(edition: Edition) -> QuerySet[ProjectResult]:
    """Galeria de vencedores da edição (RF35/RF46)."""
    if edition.status != EditionStatus.CLOSED:
        return ProjectResult.objects.none()

    return (
        ProjectResult.objects.filter(
            project__edition=edition,
            award__isnull=False,
            approved_at__isnull=False,
            project__in=_visible_projects(),
        )
        .select_related(
            "project__edition",
            "project__category",
            "project__team",
            "project__challenge__course",
            "project__challenge__sdg",
        )
        .prefetch_related(
            Prefetch(
                "project__team__members",
                queryset=TeamMember.objects.filter(active=True).select_related(
                    "student__user"
                ),
                to_attr="active_members",
            )
        )
        # Pódio por categoria na edição inteira (D-01).
        .order_by("project__category__name", "award", "project_id")
    )


def _visible_projects() -> QuerySet[Project]:
    """Projetos que podem ir à vitrine.

    Fora: projeto ou equipe desclassificados (RF13) e projeto sem desafio, que
    ainda não tem curso nem ODS para mostrar.
    """
    return (
        Project.objects.exclude(status=ProjectStatus.DISQUALIFIED)
        .exclude(team__status=TeamStatus.DISQUALIFIED)
        .filter(challenge__isnull=False)
    )


def list_public_projects(
    edition_id=None, course_id=None, sdg_id=None, category_id=None, search=None
) -> QuerySet[Project]:
    """Vitrine e acervo de projetos (público) - RF34."""
    qs = _visible_projects()

    if edition_id:
        qs = qs.filter(edition_id=edition_id)
    else:
        qs = qs.filter(edition__status=EditionStatus.PUBLISHED)

    # Regra P-28: Nas edições encerradas (CLOSED), apenas projetos homologados
    projetos_homologados_ids = ProjectResult.objects.filter(
        approved_at__isnull=False
    ).values("project_id")

    qs = qs.filter(
        Q(edition__status=EditionStatus.PUBLISHED)
        | Q(edition__status=EditionStatus.CLOSED, id__in=projetos_homologados_ids)
    )

    # Filtros opcionais
    if course_id:
        qs = qs.filter(challenge__course_id=course_id)
    if sdg_id:
        qs = qs.filter(challenge__sdg_id=sdg_id)
    if category_id:
        qs = qs.filter(category_id=category_id)
    if search:
        qs = qs.filter(Q(title__icontains=search) | Q(summary__icontains=search))

    return (
        qs.select_related(
            "edition", "category", "team", "challenge__course", "challenge__sdg"
        )
        .prefetch_related(
            Prefetch(
                "team__members",
                queryset=TeamMember.objects.filter(active=True).select_related(
                    "student__user"
                ),
                to_attr="active_members",
            )
        )
        .order_by("-created_at")
    )


def get_public_project(project_id: int) -> Project | None:
    """Detalhe público do projeto (público) - RF45."""
    projetos_homologados_ids = ProjectResult.objects.filter(
        approved_at__isnull=False
    ).values("project_id")

    qs = _visible_projects().filter(
        Q(edition__status=EditionStatus.PUBLISHED)
        | Q(edition__status=EditionStatus.CLOSED, id__in=projetos_homologados_ids)
    )

    return (
        qs.filter(id=project_id)
        .select_related(
            "edition", "category", "team", "challenge__course", "challenge__sdg"
        )
        .prefetch_related(
            Prefetch(
                "team__members",
                queryset=TeamMember.objects.filter(active=True).select_related(
                    "student__user"
                ),
                to_attr="active_members",
            )
        )
        .first()
    )
