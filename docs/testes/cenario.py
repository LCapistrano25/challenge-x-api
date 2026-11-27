# Cenario dos roteiros de teste manual (docs/testes/README.md).
#
# Rode num banco limpo, depois de migrate e seed_users:
#   uv run python manage.py shell -c "exec(open('docs/testes/cenario.py').read())"
# Roteiro 5 (resultados): defina CENARIO=resultados antes (as duas etapas de
# entrega ja encerradas e avaliadas, para o fechamento ir ate a homologacao).
#
# Arquivo so em ASCII de proposito: open() no Windows le em cp1252.
import os
from datetime import timedelta
from decimal import Decimal

from django.test import Client
from django.utils import timezone

from apps.accounts.factories import StudentFactory, UserFactory
from apps.accounts.models import User
from apps.core.factories import CourseFactory
from apps.core.models import Course, Sdg
from apps.editions.enums import EditionStatus, FieldKind
from apps.editions.factories import (
    CategoryFactory,
    ChallengeFactory,
    CriterionFactory,
    EditionFactory,
    EditionReviewerFactory,
    StageCriterionFactory,
    StageFactory,
    StageSubmissionFieldFactory,
)
from apps.editions.models import Edition
from apps.evaluations.enums import EvaluationStatus
from apps.evaluations.factories import EvaluationFactory, EvaluationItemFactory
from apps.evaluations.use_cases.recalculate_stage_score import recalculate_stage_score
from apps.notifications.models import Notification
from apps.projects.factories import (
    ProjectFactory,
    SubmissionFactory,
    SubmissionItemFactory,
    SubmissionReceiptFactory,
    SubmissionVersionFactory,
)
from apps.results.models import ProjectResult
from apps.support.factories import SupportTicketFactory
from apps.teams.enums import MemberRole
from apps.teams.factories import (
    InvitationFactory,
    JoinRequestFactory,
    LeadershipRequestFactory,
    TeamFactory,
    TeamMemberFactory,
)
from apps.teams.models import MemberNote

RESULTADOS = os.environ.get("CENARIO") == "resultados"
PASSWORD = "TesteForte!2026x"  # senha dos usuarios criados aqui (UserFactory)
DOMAIN = "aluno.desafiox.local"
now = timezone.now()

if Edition.objects.filter(status=EditionStatus.PUBLISHED).exists():
    raise SystemExit(
        "Ja existe edicao publicada neste banco: recrie o banco e rode de novo."
    )

seed_student = User.objects.get(email=f"aluno@{DOMAIN}")
teacher_user = User.objects.get(email="professor@professor.desafiox.local")
reviewer_user = User.objects.get(email="avaliador@empresa.local")
admin_user = User.objects.get(email="admin@desafiox.local")
course = Course.objects.get(name="Engenharia de Software")
other_course = CourseFactory(name="Curso Sem Integrantes", term_count=8)


def student(slug, **kwargs):
    user = UserFactory(email=f"{slug}@{DOMAIN}", name=slug.capitalize(), **kwargs)
    return StudentFactory(user=user, course=course)


edition = EditionFactory(
    year=2030,
    semester=1,
    name="Desafio X Roteiros",
    status=EditionStatus.PUBLISHED,
    published_at=now,
)
StageFactory(
    edition=edition,
    order=1,
    name="Formacao",
    formation=True,
    starts_at=now - timedelta(days=1),
    ends_at=now + timedelta(days=7),
)
# Etapa 2: envio encerrado, avaliacao aberta (roteiro 4 finaliza avaliacao).
closed = StageFactory(
    edition=edition,
    order=2,
    name="Ideia",
    starts_at=now - timedelta(days=10),
    ends_at=now - timedelta(days=1),
    evaluation_ends_at=now + timedelta(days=7),
)
# Etapa 3: envio aberto (roteiro 3); no modo resultados ja encerrada.
open_ends = now - timedelta(hours=1) if RESULTADOS else now + timedelta(days=14)
opened = StageFactory(
    edition=edition,
    order=3,
    name="Prototipo",
    starts_at=now - timedelta(days=5),
    ends_at=open_ends,
    evaluation_ends_at=open_ends + timedelta(days=7),
)
criteria = {}
for stage in (closed, opened):
    StageSubmissionFieldFactory(
        stage=stage, kind=FieldKind.LINK, label="Link do repositorio"
    )
    criteria[stage.pk] = StageCriterionFactory(
        stage=stage,
        criterion=CriterionFactory(edition=edition),
        max_score=Decimal("10.00"),
    )
# Campo de arquivo opcional na etapa aberta, para o envio multipart (roteiro 3).
file_field = StageSubmissionFieldFactory(
    stage=opened,
    kind=FieldKind.FILE,
    label="Relatorio (PDF)",
    required=False,
    formats="pdf",
    max_size_mb=1,
)

sdg = Sdg.objects.order_by("number").first()
challenge = ChallengeFactory(edition=edition, course=course, sdg=sdg)
ChallengeFactory(
    edition=edition, course=other_course, sdg=sdg, description="Desafio de outro curso"
)
category = CategoryFactory(edition=edition, name="Prototipos e Artefatos")
CategoryFactory(edition=edition, name="Categoria Inativa", active=False)

# Equipe A: aluno seed lider + 2 membros, projeto completo, versao na etapa 2.
team_a = TeamFactory(edition=edition, name="Equipe Seed", leader=False)
TeamMemberFactory(team=team_a, student=seed_student.student, role=MemberRole.LEADER)
membro1 = TeamMemberFactory(team=team_a, student=student("membro1"))
TeamMemberFactory(team=team_a, student=student("membro2"))
project_a = ProjectFactory(
    team=team_a, challenge=challenge, category=category, title="Projeto Seed"
)
version = SubmissionVersionFactory(
    submission=SubmissionFactory(project=project_a, stage=closed),
    number=1,
    submitted_at=now - timedelta(days=2),
)
item = SubmissionItemFactory(version=version, field=closed.submission_fields.get())
SubmissionReceiptFactory(version=version)
MemberNote.objects.create(
    member=membro1, author=seed_student.student, text="Faltou a duas reunioes."
)

# Equipes sem lider: B com pedido de lideranca pendente (roteiro 4),
# C sem pedido (roteiro 2).
team_b = TeamFactory(edition=edition, name="Equipe Sem Lider B", leader=False)
b_members = [
    TeamMemberFactory(team=team_b, student=student(f"semliderb{i}")) for i in (1, 2, 3)
]
project_b = ProjectFactory(
    team=team_b, challenge=challenge, category=category, title="Projeto B"
)
LeadershipRequestFactory(team=team_b, requester=b_members[0].student)
team_c = TeamFactory(edition=edition, name="Equipe Sem Lider C", leader=False)
for i in (1, 2, 3):
    TeamMemberFactory(team=team_c, student=student(f"semliderc{i}"))

# Alunos sem equipe (convites, pedidos de entrada, nova equipe) e um inativo.
livres = [student(f"livre{i}") for i in range(1, 7)]
student("inativo", is_active=False)
InvitationFactory(
    team=team_a, student=livres[3]
)  # livre4 tem convite pendente da Equipe Seed
JoinRequestFactory(
    team=team_a, student=livres[2]
)  # livre3 pediu entrada na Equipe Seed

EditionReviewerFactory(edition=edition, reviewer=reviewer_user.external_reviewer)
SupportTicketFactory(requester=seed_student, title="Correcao de matricula")
SupportTicketFactory(requester=teacher_user, title="Chamado do professor")
# Usuarios sem perfil, para o autocadastro (/api/auth/students e /api/auth/teachers).
UserFactory(email=f"novoaluno@{DOMAIN}", name="Novo Aluno")
UserFactory(
    email="novoprof@professor.desafiox.local", name="Novo Professor", role="TEACHER"
)
Notification.objects.create(
    user=seed_student,
    type="SYSTEM",
    title="Bem-vindo",
    message="Notificacao do cenario.",
)

if RESULTADOS:
    # Equipe A avaliada e com nota definitiva nas duas etapas de entrega.
    for stage in (closed, opened):
        if stage is opened:
            v = SubmissionVersionFactory(
                submission=SubmissionFactory(project=project_a, stage=opened),
                number=1,
                submitted_at=now - timedelta(hours=2),
            )
            SubmissionItemFactory(
                version=v, field=opened.submission_fields.get(kind=FieldKind.LINK)
            )
            SubmissionReceiptFactory(version=v)
        evaluation = EvaluationFactory(
            project=project_a,
            stage=stage,
            teacher=teacher_user.teacher,
            status=EvaluationStatus.FINALIZED,
            finalized_at=now,
        )
        EvaluationItemFactory(
            evaluation=evaluation,
            stage_criterion=criteria[stage.pk],
            points=Decimal("8.00"),
        )
        recalculate_stage_score(project=project_a, stage=stage)
else:
    # Equipe A finalista, para o painel do avaliador externo (roteiro 4).
    ProjectResult.objects.create(
        project=project_a, final_score=Decimal("0.00"), course_rank=1, finalist=True
    )

mode = "resultados" if RESULTADOS else "padrao"
print(f"MODO {mode}  senha dos alunos criados: {PASSWORD}")
ids = {
    "EDITION": edition,
    "STAGE_FORMACAO": edition.stages.get(order=1),
    "STAGE_ENCERRADA": closed,
    "STAGE_ABERTA": opened,
    "CHALLENGE": challenge,
    "CATEGORY": category,
    "CATEGORY_INATIVA": edition.categories.get(active=False),
    "OTHER_COURSE": other_course,
    "COURSE_ES": course,
    "TEAM_A": team_a,
    "PROJECT_A": project_a,
    "VERSION_A": version,
    "ITEM_A": item,
    "TEAM_B": team_b,
    "PROJECT_B": project_b,
    "TEAM_C": team_c,
    "MEMBRO1_MEMBER_ID": membro1,
    "LEADERSHIP_REQUEST_B": team_b.leadership_requests.get(),
    "INVITATION_LIVRE4": team_a.invitations.get(),
    "JOIN_REQUEST_LIVRE3": team_a.join_requests.get(),
    "FIELD_LINK_ENCERRADA": closed.submission_fields.get(),
    "FIELD_LINK_ABERTA": opened.submission_fields.get(kind=FieldKind.LINK),
    "FIELD_FILE_ABERTA": file_field,
    "STAGE_CRITERION_ENCERRADA": criteria[closed.pk],
    "STAGE_CRITERION_ABERTA": criteria[opened.pk],
    "LIVRE1_STUDENT_ID": livres[0],
    "LIVRE2_STUDENT_ID": livres[1],
    "LIVRE5_STUDENT_ID": livres[4],
}
for name, obj in ids.items():
    print(f"{name}={obj.pk}")
for user in (
    admin_user,
    seed_student,
    teacher_user,
    reviewer_user,
    livres[0].user,
    livres[3].user,
):
    c = Client()
    c.force_login(user)
    print(f"SESSION {user.role:<17} {user.email:<36} {c.cookies['sessionid'].value}")
