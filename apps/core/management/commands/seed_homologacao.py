"""Banco de homologação com o volume de uma faculdade (#303).

Cria alunos de todos os cursos e períodos, professores, avaliadores externos,
duas edições encerradas com resultado homologado, a edição vigente no meio do
caminho e uma edição em configuração, com os casos de borda que os testes
manuais precisam. As notas e os resultados saem dos próprios casos de uso.
"""

import random
import string
import unicodedata
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.accounts.models import (
    EmailDomain,
    ExternalReviewer,
    Student,
    Teacher,
    TeacherCourse,
    User,
)
from apps.core.models import Course, Sdg
from apps.editions.enums import EditionStatus, FieldKind, StageKind
from apps.editions.models import (
    Category,
    Challenge,
    Criterion,
    Edition,
    EditionReviewer,
    EditionSdg,
    Stage,
    StageCriterion,
    StageSubmissionField,
)
from apps.evaluations.enums import EvaluationStatus, FinalEvaluationStatus, QuestionKind
from apps.evaluations.models import (
    Evaluation,
    EvaluationItem,
    FinalAnswer,
    FinalEvaluation,
    FinalForm,
    FinalQuestion,
)
from apps.evaluations.use_cases.apply_zero_for_missing_submission import (
    apply_zero_for_missing_submission,
)
from apps.evaluations.use_cases.recalculate_stage_score import (
    recalculate_stage_score,
)
from apps.notifications.models import Notification, NotificationType
from apps.projects.enums import ProjectStatus
from apps.projects.models import (
    DeadlineExtension,
    Project,
    Submission,
    SubmissionItem,
    SubmissionReceipt,
    SubmissionVersion,
)
from apps.projects.rules import CANVAS_BLOCKS, SWOT_QUADRANTS
from apps.results.models import ProjectResult
from apps.results.use_cases.approve_finalists import approve_finalists
from apps.results.use_cases.calculate_results import calculate_results
from apps.results.use_cases.compute_awards import compute_awards
from apps.results.use_cases.select_finalists import select_finalists
from apps.support.enums import SupportTicketPriority, SupportTicketStatus
from apps.support.models import SupportTicket
from apps.teams.enums import (
    InvitationStatus,
    MemberRole,
    RequestStatus,
    TeamSituation,
    TeamStatus,
)
from apps.teams.models import (
    Invitation,
    JoinRequest,
    LeadershipRequest,
    MemberNote,
    Team,
    TeamMember,
)

STUDENT_DOMAIN = "aluno.desafiox.local"
TEACHER_DOMAIN = "professor.desafiox.local"
DAY = timedelta(days=1)

FIRST_NAMES = (
    "Ana", "Bruno", "Camila", "Daniel", "Eduarda", "Felipe", "Gabriela", "Heitor",
    "Isabela", "João", "Larissa", "Lucas", "Mariana", "Mateus", "Natália",
    "Otávio", "Paula", "Rafael", "Sofia", "Thiago", "Valentina", "Vinícius",
    "Yasmin", "Arthur", "Beatriz", "Caio", "Débora", "Enzo", "Fernanda",
    "Guilherme", "Helena", "Igor", "Júlia", "Kaique", "Lívia", "Miguel",
    "Nicole", "Pedro", "Rebeca", "Samuel",
)  # fmt: skip
LAST_NAMES = (
    "Silva", "Santos", "Oliveira", "Souza", "Rodrigues", "Ferreira", "Alves",
    "Pereira", "Lima", "Gomes", "Costa", "Ribeiro", "Martins", "Carvalho",
    "Almeida", "Lopes", "Soares", "Fernandes", "Vieira", "Barbosa", "Rocha",
    "Dias", "Nascimento", "Andrade", "Moreira", "Nunes", "Marques", "Machado",
    "Mendes", "Freitas", "Cardoso", "Ramos", "Gonçalves", "Santana", "Teixeira",
    "Araújo", "Batista", "Moura", "Coelho", "Pinto",
)  # fmt: skip
TEAM_WORDS = (
    "Ipê", "Araguaia", "Jalapão", "Capim Dourado", "Buriti", "Cerrado",
    "Tocantins", "Siriema", "Pequi", "Arara", "Lobo-guará", "Babaçu",
)  # fmt: skip
TITLE_PREFIXES = (
    "Plataforma", "Aplicativo", "Sistema", "Programa", "Rede", "Laboratório",
    "Observatório", "Hub",
)  # fmt: skip
TITLE_SUBJECTS = (
    "de monitoramento hídrico", "de apoio a pequenos produtores",
    "de saúde mental", "de reaproveitamento de resíduos", "de inclusão digital",
    "de mobilidade urbana", "de educação financeira", "de segurança alimentar",
    "de acessibilidade", "de energia solar", "de adoção responsável",
    "de telessaúde", "de regularização fundiária", "de manejo do solo",
)  # fmt: skip
TITLE_AUDIENCES = (
    "no Tocantins", "para escolas públicas", "para comunidades ribeirinhas",
    "em Palmas", "para idosos", "para a agricultura familiar",
    "na periferia urbana", "para cooperativas",
)  # fmt: skip
INSTITUTIONS = (
    ("Sebrae Tocantins", "sebrae-to.com.br"),
    ("Embrapa Pesca e Aquicultura", "embrapa.br"),
    ("Prefeitura de Palmas", "palmas.to.gov.br"),
    ("Energisa", "energisa.com.br"),
    ("Hospital Geral de Palmas", "hgp.to.gov.br"),
    ("Startup Cerrado Tech", "cerradotech.com.br"),
)
CATEGORIES = (
    ("Impacto Social", "Projetos voltados a comunidades e políticas públicas."),
    ("Inovação Tecnológica", "Soluções com base em software, dados ou hardware."),
    ("Sustentabilidade Ambiental", "Uso de recursos naturais e resíduos."),
    ("Saúde e Bem-estar", "Promoção de saúde física e mental."),
)
CRITERIA = (
    ("Inovação", 1, "0–3 pouco original; 4–7 adapta ideias; 8–10 solução inédita."),
    ("Viabilidade", 2, "0–3 inviável; 4–7 viável com ajustes; 8–10 pronta."),
    ("Impacto", None, "0–3 baixo alcance; 4–7 regional; 8–10 transformador."),
    ("Apresentação", None, "Clareza, organização e domínio do tema."),
)
TICKET_SUBJECTS = (
    "Não consigo enviar a entrega",
    "Convite da equipe não aparece",
    "Erro ao abrir o comprovante",
    "Nota da etapa não apareceu",
    "Quero trocar de equipe",
    "Professor não consegue avaliar meu projeto",
    "Dúvida sobre o prazo de formação",
    "Arquivo maior que o limite",
)


@dataclass
class Entry:
    """Equipe montada pela carga, com o projeto e os integrantes ativos."""

    team: Team
    project: Project
    members: list[Student]
    quality: float
    left: list[Student] = field(default_factory=list)

    @property
    def leader(self) -> Student:
        return self.members[0]


class Command(BaseCommand):
    help = (
        "Monta o banco de homologação: vários cursos e períodos, edições "
        "encerradas, a vigente e uma em configuração, com casos de borda."
    )

    def add_arguments(self, parser):
        parser.add_argument("--password", required=True, help="Senha de todos.")
        parser.add_argument(
            "--students-per-course",
            type=int,
            default=60,
            help="Alunos por curso (padrão 60; mínimo 10).",
        )
        parser.add_argument(
            "--seed", type=int, default=2026, help="Semente: mesma carga sempre."
        )

    def handle(self, *args, password, students_per_course, seed, **options):
        # Senha conhecida por todos: só em desenvolvimento ou homologação.
        if not (settings.DEBUG or settings.ALLOW_PASSWORD_LOGIN_FOR_ALL_ROLES):
            raise CommandError(
                "seed_homologacao só roda com DEBUG=True ou com "
                "ALLOW_PASSWORD_LOGIN_FOR_ALL_ROLES=True (homologação)."
            )
        if students_per_course < 10:
            raise CommandError("Use pelo menos 10 alunos por curso.")
        if Edition.objects.exists():
            raise CommandError(
                "O banco já tem edição. Rode num banco recém-migrado "
                "(apague o banco, rode migrate e depois este comando)."
            )

        with transaction.atomic():
            seeder = Seeder(random.Random(seed), password, students_per_course)
            accounts = seeder.run()

        self.stdout.write(self.style.SUCCESS("Banco de homologação montado."))
        for label, model in (
            ("alunos", Student),
            ("professores", Teacher),
            ("avaliadores externos", ExternalReviewer),
            ("edições", Edition),
            ("equipes", Team),
            ("versões de entrega", SubmissionVersion),
            ("avaliações", Evaluation),
            ("resultados", ProjectResult),
            ("notificações", Notification),
            ("chamados", SupportTicket),
        ):
            self.stdout.write(f"  {model.objects.count():>6} {label}")
        self.stdout.write("\nContas para os testes (todas com a mesma senha):")
        for label, email in accounts.items():
            self.stdout.write(f"  {label:<55} {email}")


class Seeder:
    def __init__(self, rng: random.Random, password: str, per_course: int):
        self.rng = rng
        self.password_hash = make_password(password)
        self.per_course = per_course
        self.now = timezone.now()
        self.emails: set[str] = set()
        self.codes: set[str] = set()
        self.accounts: dict[str, str] = {}

    # Pessoas -----------------------------------------------------------------

    def run(self) -> dict[str, str]:
        self.courses = list(Course.objects.filter(active=True).order_by("name"))
        self.sdgs = list(Sdg.objects.filter(active=True))
        if not self.courses or not self.sdgs:
            raise CommandError("Faltam cursos ou ODS: rode o migrate antes.")
        EmailDomain.objects.get_or_create(
            name=STUDENT_DOMAIN, defaults={"role": UserRole.STUDENT}
        )
        EmailDomain.objects.get_or_create(
            name=TEACHER_DOMAIN, defaults={"role": UserRole.TEACHER}
        )
        self.admin = self._admin("admin@desafiox.local", "Administrador")
        self._admin("coordenacao@desafiox.local", "Coordenação do Desafio X")
        self.accounts["Admin"] = self.admin.email
        self.accounts["Admin (coordenação)"] = "coordenacao@desafiox.local"
        self.students = self._students()
        self.teachers_by_course = self._teachers()
        self.reviewers = self._reviewers()

        year, semester = self.now.year, 1 if self.now.month <= 6 else 2
        current_base = self.now - 80 * DAY
        previous = self._previous(year, semester)
        older = self._previous(*previous)
        self._closed_edition(*older, current_base - 364 * DAY)
        self._closed_edition(*previous, current_base - 182 * DAY)
        self._current_edition(year, semester, current_base)
        self._setup_edition(*self._next(year, semester))
        self._support_tickets()
        return self.accounts

    def _admin(self, email: str, name: str) -> User:
        user, _ = User.objects.get_or_create(
            email=email,
            defaults={
                "name": name,
                "role": UserRole.ADMIN,
                "is_active": True,
                "email_confirmed": True,
            },
        )
        user.password = self.password_hash
        user.save(update_fields=["password"])
        self.emails.add(email)
        return user

    def _person(self, domain: str, role: str) -> User:
        first = self.rng.choice(FIRST_NAMES)
        middle, last = self.rng.sample(LAST_NAMES, 2)
        base = _ascii(f"{first}.{last}").lower()
        email, n = f"{base}@{domain}", 1
        while email in self.emails:
            n += 1
            email = f"{base}{n}@{domain}"
        self.emails.add(email)
        return User(
            email=email,
            name=f"{first} {middle} {last}",
            role=role,
            is_active=True,
            email_confirmed=True,
            password=self.password_hash,
        )

    def _students(self) -> list[Student]:
        users, students = [], []
        for index, course in enumerate(self.courses, start=1):
            for i in range(self.per_course):
                user = self._person(STUDENT_DOMAIN, UserRole.STUDENT)
                term = 1 + i % course.term_count  # todos os períodos do curso
                entry_year = self.now.year - (term - 1) // 2
                users.append(user)
                students.append(
                    Student(
                        user=user,
                        course=course,
                        term=term,
                        registration_number=f"{entry_year}{index:02d}{i:04d}",
                    )
                )
        User.objects.bulk_create(users)
        return Student.objects.bulk_create(students)

    def _teachers(self) -> dict[int, list[Teacher]]:
        by_course: dict[int, list[Teacher]] = {c.pk: [] for c in self.courses}
        links = []
        for course in self.courses:
            for _ in range(3):
                user = self._person(TEACHER_DOMAIN, UserRole.TEACHER)
                user.save()
                teacher = Teacher.objects.create(user=user)
                by_course[course.pk].append(teacher)
                links.append(TeacherCourse(teacher=teacher, course=course))
        # Alguns professores dão aula em dois cursos (RF10).
        for course, other in list(zip(self.courses, self.courses[1:], strict=False))[
            :5
        ]:
            teacher = by_course[course.pk][0]
            by_course[other.pk].append(teacher)
            links.append(TeacherCourse(teacher=teacher, course=other))
        TeacherCourse.objects.bulk_create(links)
        shared = by_course[self.courses[0].pk][0]
        self.accounts["Professor em dois cursos"] = shared.user.email
        self.accounts["Professor com avaliações a fazer (edição vigente)"] = by_course[
            self.courses[1].pk
        ][1].user.email
        return by_course

    def _reviewers(self) -> list[ExternalReviewer]:
        reviewers = []
        for i in range(12):
            institution, domain = INSTITUTIONS[i % len(INSTITUTIONS)]
            user = self._person(domain, UserRole.EXTERNAL_REVIEWER)
            user.save()
            reviewers.append(
                ExternalReviewer.objects.create(user=user, institution=institution)
            )
        return reviewers

    # Edições -----------------------------------------------------------------

    @staticmethod
    def _previous(year: int, semester: int) -> tuple[int, int]:
        return (year, 1) if semester == 2 else (year - 1, 2)

    @staticmethod
    def _next(year: int, semester: int) -> tuple[int, int]:
        return (year, 2) if semester == 1 else (year + 1, 1)

    def _edition(self, year, semester, base, status=EditionStatus.PUBLISHED):
        edition = Edition.objects.create(
            year=year,
            semester=semester,
            name=f"Desafio X {year}/{semester}",
            status=status,
            regulation_url="https://desafiox.local/regulamento.pdf",
            published_at=base - 7 * DAY if status != EditionStatus.SETUP else None,
        )
        sdgs = self.rng.sample(self.sdgs, min(10, len(self.sdgs)))
        EditionSdg.objects.bulk_create(
            EditionSdg(edition=edition, sdg=sdg) for sdg in sdgs
        )
        categories = Category.objects.bulk_create(
            Category(edition=edition, name=name, description=description)
            for name, description in CATEGORIES
        )
        criteria = Criterion.objects.bulk_create(
            Criterion(edition=edition, name=name, tiebreak_order=order, rubric=rubric)
            for name, order, rubric in CRITERIA
        )
        return edition, sdgs, categories, criteria

    def _challenges(self, edition, sdgs) -> dict[int, list[Challenge]]:
        by_course = {}
        for course in self.courses:
            by_course[course.pk] = Challenge.objects.bulk_create(
                Challenge(
                    edition=edition,
                    course=course,
                    sdg=sdg,
                    description=(
                        f"Desafio de {course.name} ligado à ODS {sdg.number} "
                        f"({sdg.title}): propor uma solução aplicável à região."
                    ),
                )
                for sdg in self.rng.sample(sdgs, 2)
            )
        return by_course

    def _stages(self, edition, base, criteria) -> list[Stage]:
        """Formação, três entregas pontuadas (3 + 4 + 3 = 10) e a final."""
        plan = (
            (StageKind.FORMATION, "Formação de equipes", 0, 30, None, None, 1),
            (StageKind.SUBMISSION, "Ideação", 30, 60, 30, "3.00", 2),
            (StageKind.SUBMISSION, "Protótipo", 60, 90, 30, "4.00", 2),
            (StageKind.SUBMISSION, "Pitch", 90, 120, 30, "3.00", 1),
            (StageKind.FINAL, "Apresentação final", 155, 156, None, None, 1),
        )
        stages = []
        for order, (kind, name, start, end, review, score, minimum) in enumerate(
            plan, start=1
        ):
            stages.append(
                Stage.objects.create(
                    edition=edition,
                    order=order,
                    name=name,
                    kind=kind,
                    starts_at=base + start * DAY,
                    ends_at=base + end * DAY,
                    evaluation_ends_at=base + (end + review) * DAY if review else None,
                    scored=score is not None,
                    max_score=Decimal(score) if score else None,
                    min_evaluations=minimum,
                )
            )
        ideation, prototype, pitch = stages[1:4]
        StageSubmissionField.objects.bulk_create(
            [
                StageSubmissionField(
                    stage=ideation, kind=FieldKind.LINK, label="Vídeo da ideia"
                ),
                StageSubmissionField(stage=ideation, kind=FieldKind.CANVAS),
                StageSubmissionField(
                    stage=prototype, kind=FieldKind.LINK, label="Repositório"
                ),
                StageSubmissionField(stage=prototype, kind=FieldKind.SWOT),
                StageSubmissionField(
                    stage=prototype,
                    kind=FieldKind.FILE,
                    label="Relatório técnico",
                    required=False,
                    formats="pdf",
                    max_size_mb=10,
                ),
                StageSubmissionField(
                    stage=pitch, kind=FieldKind.LINK, label="Vídeo do pitch"
                ),
                StageSubmissionField(
                    stage=pitch,
                    kind=FieldKind.FILE,
                    label="Slides",
                    required=False,
                    formats="pdf,pptx",
                    max_size_mb=20,
                ),
            ]
        )
        StageCriterion.objects.bulk_create(
            StageCriterion(stage=stage, criterion=criterion, max_score=Decimal(10))
            for stage in (ideation, prototype, pitch)
            for criterion in criteria
        )
        return stages

    def _reviewer_links(self, edition, count: int, scoped: int = 0):
        reviewers = self.rng.sample(self.reviewers, count)
        EditionReviewer.objects.bulk_create(
            EditionReviewer(
                edition=edition,
                reviewer=reviewer,
                course=self.courses[i] if i < scoped else None,
            )
            for i, reviewer in enumerate(reviewers)
        )
        return reviewers

    def _final_form(self, edition, published: bool) -> FinalForm:
        form = FinalForm.objects.create(
            edition=edition, title="Avaliação da banca", published=published
        )
        questions = [
            ("Inovação e originalidade da solução", QuestionKind.SCORE),
            ("Viabilidade de implantação", QuestionKind.SCORE),
            ("Qualidade da apresentação", QuestionKind.SCORE),
            ("Comentário geral para a equipe", QuestionKind.TEXT),
        ]
        FinalQuestion.objects.bulk_create(
            FinalQuestion(
                form=form,
                order=order,
                prompt=prompt,
                kind=kind,
                max_score=Decimal(10) if kind == QuestionKind.SCORE else None,
            )
            for order, (prompt, kind) in enumerate(questions, start=1)
        )
        return form

    # Equipes e projetos ------------------------------------------------------

    def _code(self) -> str:
        alphabet = string.ascii_uppercase + string.digits
        while True:
            code = "".join(self.rng.choice(alphabet) for _ in range(6))
            if code not in self.codes:
                self.codes.add(code)
                return code

    def _teams(self, edition, base, challenges, categories, share) -> list[Entry]:
        """Equipes de 3 a 5 alunos de cursos misturados; o líder define o desafio."""
        pool = self.rng.sample(self.students, int(len(self.students) * share))
        groups = []
        while len(pool) >= 3:
            size = self.rng.randint(edition.min_members, edition.max_members)
            groups.append(pool[:size])
            pool = pool[size:]

        titles: set[str] = set()
        entries = []
        for i, members in enumerate(groups):
            team = Team(
                edition=edition,
                name=f"{self.rng.choice(TEAM_WORDS)} {i + 1}",
                code=self._code(),
                situation=TeamSituation.COMPLETE,
            )
            challenge = self.rng.choice(challenges[members[0].course_id])
            title = " ".join(
                (
                    self.rng.choice(TITLE_PREFIXES),
                    self.rng.choice(TITLE_SUBJECTS),
                    self.rng.choice(TITLE_AUDIENCES),
                )
            )
            if title in titles:
                title = f"{title} — {team.code}"
            titles.add(title)
            project = Project(
                team=team,
                edition=edition,
                title=title,
                summary=(
                    f"{title} é uma proposta da equipe {team.name} para o desafio "
                    f"de {challenge.course.name}, com foco na ODS "
                    f"{challenge.sdg.number}."
                ),
                objective="Validar a solução com o público-alvo até o fim da edição.",
                challenge=challenge,
                category=self.rng.choice(categories),
            )
            entries.append(
                Entry(team, project, members, quality=self.rng.uniform(4.5, 9.8))
            )

        Team.objects.bulk_create(e.team for e in entries)
        for entry in entries:
            entry.project.team = entry.team
        Project.objects.bulk_create(e.project for e in entries)
        TeamMember.objects.bulk_create(
            TeamMember(
                team=e.team,
                edition=edition,
                student=student,
                role=MemberRole.LEADER if n == 0 else MemberRole.MEMBER,
                joined_at=base + self.rng.uniform(0, 20) * DAY,
            )
            for e in entries
            for n, student in enumerate(e.members)
        )
        return entries

    def _disqualify(self, entry: Entry, when, reason: str) -> None:
        team = entry.team
        team.status = TeamStatus.DISQUALIFIED
        team.disqualification_reason = reason
        team.disqualified_at = when
        team.disqualified_by = self.admin
        team.save()
        entry.project.status = ProjectStatus.DISQUALIFIED
        entry.project.save(update_fields=["status", "updated_at"])

    # Entregas e avaliações ---------------------------------------------------

    def _deliver(self, entry: Entry, stage: Stage, start, end, versions: int):
        submission = Submission.objects.create(project=entry.project, stage=stage)
        fields = list(stage.submission_fields.exclude(kind=FieldKind.FILE))
        times = sorted(
            start + (end - start) * self.rng.random() for _ in range(versions)
        )
        for number, submitted_at in enumerate(times, start=1):
            version = SubmissionVersion.objects.create(
                submission=submission,
                number=number,
                submitted_by=entry.leader,
                submitted_at=submitted_at,
                notes="Versão revisada após a mentoria." if number > 1 else "",
            )
            SubmissionItem.objects.bulk_create(
                self._item(version, f, entry, number) for f in fields
            )
            SubmissionReceipt.objects.create(version=version, generated_at=submitted_at)
        return submission

    def _item(self, version, field_, entry, number) -> SubmissionItem:
        code = entry.team.code.lower()
        if field_.kind == FieldKind.LINK:
            return SubmissionItem(
                version=version,
                field=field_,
                kind=FieldKind.LINK,
                link=f"https://desafiox.local/demo/{code}/{field_.stage_id}/v{number}",
            )
        if field_.kind == FieldKind.CANVAS:
            content = {
                block: f"{block.replace('_', ' ').capitalize()} do projeto "
                f"{entry.project.title}."
                for block in CANVAS_BLOCKS
            }
        else:
            content = {
                quadrant: [f"Ponto {n} de {quadrant}" for n in range(1, 4)]
                for quadrant in SWOT_QUADRANTS
            }
        return SubmissionItem(
            version=version, field=field_, kind=field_.kind, content=content
        )

    def _points(self, quality: float) -> Decimal:
        value = min(10.0, max(0.0, self.rng.gauss(quality, 1.0)))
        return Decimal(round(value * 2) / 2).quantize(Decimal("0.01"))

    def _evaluate(self, entry, stage, teacher, finalized: bool) -> Evaluation:
        when = stage.ends_at + self.rng.uniform(1, 20) * DAY
        evaluation = Evaluation.objects.create(
            project=entry.project,
            stage=stage,
            teacher=teacher,
            comment="Boa evolução; detalhar o modelo de negócio.",
            status=EvaluationStatus.FINALIZED if finalized else EvaluationStatus.DRAFT,
            finalized_at=when if finalized else None,
        )
        EvaluationItem.objects.bulk_create(
            EvaluationItem(
                evaluation=evaluation,
                stage_criterion=link,
                points=self._points(entry.quality),
            )
            for link in stage.criterion_links.all()
        )
        return evaluation

    def _course_teachers(self, entry: Entry) -> list[Teacher]:
        return self.teachers_by_course[entry.project.challenge.course_id]

    # Edição encerrada --------------------------------------------------------

    def _closed_edition(self, year, semester, base) -> None:
        """Ciclo completo, do cadastro à homologação, e depois encerrada."""
        edition, sdgs, categories, criteria = self._edition(year, semester, base)
        challenges = self._challenges(edition, sdgs)
        stages = self._stages(edition, base, criteria)
        entries = self._teams(edition, base, challenges, categories, share=0.75)
        for entry in entries[-2:]:
            self._disqualify(
                entry, base + 40 * DAY, "Plágio comprovado na entrega da ideação."
            )
        active = entries[:-2]
        for entry in active:
            entry.project.status = ProjectStatus.COMPLETED
            entry.project.save(update_fields=["status", "updated_at"])
            for stage in stages[1:4]:
                if self.rng.random() < 0.04:
                    continue  # sem entrega: nota zero abaixo
                self._deliver(
                    entry, stage, stage.starts_at, stage.ends_at, self.rng.randint(1, 2)
                )
                for teacher in self.rng.sample(self._course_teachers(entry), 2):
                    self._evaluate(entry, stage, teacher, finalized=True)
                recalculate_stage_score(project=entry.project, stage=stage)
        for entry in active:
            for stage in stages[1:4]:
                apply_zero_for_missing_submission(project=entry.project, stage=stage)

        calculate_results(actor=self.admin, edition=edition)
        select_finalists(actor=self.admin, edition=edition)
        reviewers = self._reviewer_links(edition, 6)
        form = self._final_form(edition, published=True)
        finalists = ProjectResult.objects.filter(
            project__edition=edition, finalist=True
        ).values_list("project_id", flat=True)
        quality = {e.project.pk: e.quality for e in entries}
        for project_id in finalists:
            for reviewer in self.rng.sample(reviewers, 2):
                self._final_evaluation(
                    project_id, reviewer, form, quality[project_id], stages[4]
                )
        compute_awards(actor=self.admin, edition=edition)
        approve_finalists(actor=self.admin, edition=edition)
        edition.status = EditionStatus.CLOSED
        edition.closed_at = base + 160 * DAY
        edition.save(update_fields=["status", "closed_at", "updated_at"])

        winner = (
            ProjectResult.objects.filter(project__edition=edition, award=1)
            .select_related("project__team")
            .first()
        )
        if winner:
            leader = winner.project.team.members.get(role=MemberRole.LEADER)
            self.accounts[f"Aluno de projeto premiado ({edition})"] = (
                leader.student.user.email
            )
        self.accounts[f"Avaliador externo ({edition}, encerrada)"] = reviewers[
            0
        ].user.email

    def _final_evaluation(self, project_id, reviewer, form, quality, stage) -> None:
        evaluation = FinalEvaluation.objects.create(
            project_id=project_id,
            reviewer=reviewer,
            form=form,
            comment="Projeto consistente e bem apresentado.",
            status=FinalEvaluationStatus.EVALUATED,
            finalized_at=stage.ends_at,
        )
        FinalAnswer.objects.bulk_create(
            FinalAnswer(
                evaluation=evaluation,
                question=question,
                value=self._points(quality)
                if question.kind == QuestionKind.SCORE
                else None,
                text=""
                if question.kind == QuestionKind.SCORE
                else "Recomendo seguir com a validação em campo.",
            )
            for question in form.questions.all()
        )

    # Edição vigente ----------------------------------------------------------

    def _current_edition(self, year, semester, base) -> None:
        """Formação encerrada, ideação em avaliação, protótipo aberto, pitch futuro."""
        edition, sdgs, categories, criteria = self._edition(year, semester, base)
        challenges = self._challenges(edition, sdgs)
        stages = self._stages(edition, base, criteria)
        _formation, ideation, prototype, _pitch, _final = stages
        entries = self._teams(edition, base, challenges, categories, share=0.85)

        disbanded, disqualified = entries[-2:], entries[-5:-2]
        incomplete, regular = entries[-13:-5], entries[:-13]
        for entry in disbanded:
            entry.team.status = TeamStatus.DISBANDED
            entry.team.situation = None
            entry.team.save(update_fields=["status", "situation", "updated_at"])
            entry.team.members.update(active=False, left_at=base + 10 * DAY)
            entry.left, entry.members = entry.members, []
        for entry in disqualified:
            self._disqualify(
                entry,
                self.now - 25 * DAY,
                "Integrantes não compareceram à mentoria obrigatória.",
            )
        for n, entry in enumerate(incomplete):
            # Dois integrantes e projeto sem categoria (metade também sem resumo).
            extra = entry.members[2:]
            entry.team.members.filter(student__in=extra).update(
                active=False, left_at=base + 25 * DAY
            )
            entry.members, entry.left = entry.members[:2], extra
            entry.team.situation = TeamSituation.INCOMPLETE
            entry.team.save(update_fields=["situation", "updated_at"])
            entry.project.category = None
            if n % 2:
                entry.project.summary = ""
            entry.project.save(update_fields=["category", "summary", "updated_at"])

        # Prorrogações: duas na ideação (prazo ainda aberto) e duas no protótipo.
        extended = {e.project.pk for e in regular[:2]}
        for entry, stage, until in (
            (regular[0], ideation, self.now + 3 * DAY),
            (regular[1], ideation, self.now + 3 * DAY),
            (regular[2], prototype, prototype.ends_at + 7 * DAY),
            (regular[3], prototype, prototype.ends_at + 7 * DAY),
        ):
            DeadlineExtension.objects.create(
                project=entry.project,
                stage=stage,
                ends_at=until,
                reason="Integrante hospitalizado durante o prazo.",
                granted_by=self.admin,
            )

        pending_teacher = self.teachers_by_course[self.courses[1].pk][1]
        for i, entry in enumerate(regular):
            if entry.project.pk in extended or self.rng.random() < 0.1:
                continue  # sem entrega na ideação
            versions = self.rng.randint(1, 3)
            submission = self._deliver(
                entry, ideation, ideation.starts_at, ideation.ends_at, versions
            )
            if i % 15 == 0:
                # Versão depois do prazo: não vale, a anterior continua valendo.
                SubmissionVersion.objects.create(
                    submission=submission,
                    number=versions + 1,
                    submitted_by=entry.leader,
                    submitted_at=ideation.ends_at + timedelta(hours=2),
                    notes="Enviada depois do prazo.",
                )
            teachers = [t for t in self._course_teachers(entry) if t != pending_teacher]
            draw = self.rng.random()
            if draw < 0.6:
                chosen = self.rng.sample(teachers, min(2, len(teachers)))
                for teacher in chosen:
                    self._evaluate(entry, ideation, teacher, finalized=True)
            elif draw < 0.8:
                self._evaluate(entry, ideation, teachers[0], finalized=True)
            elif draw < 0.9:
                self._evaluate(entry, ideation, teachers[0], finalized=False)
            if Evaluation.objects.filter(
                project=entry.project, stage=ideation, status=EvaluationStatus.FINALIZED
            ).exists():
                recalculate_stage_score(project=entry.project, stage=ideation)
        for entry in regular + incomplete:
            apply_zero_for_missing_submission(project=entry.project, stage=ideation)

        for entry in regular:
            if self.rng.random() < 0.5:
                self._deliver(
                    entry,
                    prototype,
                    prototype.starts_at,
                    self.now,
                    self.rng.randint(1, 2),
                )

        reviewers = self._reviewer_links(edition, 8, scoped=2)
        self._final_form(edition, published=False)
        self._team_activity(edition, base, entries, regular, incomplete)

        leader, member = regular[5].leader, regular[5].members[1]
        self.accounts["Aluno líder de equipe completa"] = leader.user.email
        self.accounts["Aluno integrante (não líder)"] = member.user.email
        self.accounts["Aluno líder de equipe incompleta"] = incomplete[
            0
        ].leader.user.email
        self.accounts["Aluno de equipe desclassificada"] = disqualified[
            0
        ].leader.user.email
        self.accounts["Aluno com prorrogação na ideação"] = regular[0].leader.user.email
        self.accounts["Avaliador externo da edição vigente"] = reviewers[-1].user.email

    def _team_activity(self, edition, base, entries, regular, incomplete) -> None:
        """Convites, pedidos de entrada e de liderança, saídas e observações."""
        in_team = set(
            TeamMember.objects.filter(edition=edition, active=True).values_list(
                "student_id", flat=True
            )
        )
        free = [s for s in self.students if s.pk not in in_team]
        self.rng.shuffle(free)
        open_teams = [e for e in regular if len(e.members) < edition.max_members]
        formation_end = base + 30 * DAY

        # Quem saiu de uma equipe e hoje está sem equipe (histórico de saída).
        TeamMember.objects.bulk_create(
            TeamMember(
                team=entry.team,
                edition=edition,
                student=student,
                joined_at=base + 2 * DAY,
                left_at=base + 12 * DAY,
                active=False,
            )
            for entry, student in zip(open_teams[:6], free[:6], strict=False)
        )
        invited, requesting = free[6:26], free[26:46]
        invitations = [
            Invitation(team=self.rng.choice(open_teams).team, student=student)
            for student in invited
        ]
        invitations += [
            Invitation(
                team=self.rng.choice(open_teams).team,
                student=student,
                status=InvitationStatus.DECLINED,
                responded_at=base + 8 * DAY,
            )
            for student in free[46:52]
        ]
        Invitation.objects.bulk_create(invitations)
        Notification.objects.bulk_create(
            Notification(
                user=invitation.student.user,
                type=NotificationType.TEAM,
                title="Convite para equipe",
                message=f"A equipe {invitation.team.name} convidou você.",
            )
            for invitation in invitations
            if invitation.status == InvitationStatus.PENDING
        )
        JoinRequest.objects.bulk_create(
            JoinRequest(team=self.rng.choice(open_teams).team, student=student)
            for student in requesting
        )
        if invited:
            self.accounts["Aluno sem equipe com convite pendente"] = invited[
                0
            ].user.email
        if requesting:
            self.accounts["Aluno sem equipe com pedido de entrada"] = requesting[
                0
            ].user.email
        if len(free) > 52:
            self.accounts["Aluno sem equipe e sem pendências"] = free[-1].user.email

        # Pedidos de liderança: três pendentes e dois recusados pelo professor.
        for n, entry in enumerate(regular[10:15]):
            pending = n < 3
            requester = entry.members[-1]
            LeadershipRequest.objects.create(
                team=entry.team,
                requester=requester,
                justification="O líder não responde há três semanas.",
                status=RequestStatus.PENDING if pending else RequestStatus.REJECTED,
                teacher=None if pending else self._course_teachers(entry)[0],
                decision_justification=""
                if pending
                else "O líder voltou a participar.",
                decided_at=None if pending else formation_end + 5 * DAY,
            )
            if n == 0:
                self.accounts["Aluno com pedido de liderança pendente"] = (
                    requester.user.email
                )

        notes = []
        for entry in regular[:30]:
            leader = entry.team.members.get(role=MemberRole.LEADER, active=True)
            for member in entry.team.members.filter(
                active=True, role=MemberRole.MEMBER
            )[:2]:
                notes.append(
                    MemberNote(
                        member=member,
                        author=leader.student,
                        text="Participou de todas as reuniões e entregou sua parte.",
                    )
                )
        MemberNote.objects.bulk_create(notes)

    # Edição em configuração e suporte ----------------------------------------

    def _setup_edition(self, year, semester) -> None:
        """Configuração pela metade: publicar deve recusar e listar o que falta."""
        base = self.now + 90 * DAY
        edition, _sdgs, _categories, criteria = self._edition(
            year, semester, base, status=EditionStatus.SETUP
        )
        Stage.objects.create(
            edition=edition,
            order=1,
            name="Formação de equipes",
            kind=StageKind.FORMATION,
            starts_at=base,
            ends_at=base + 30 * DAY,
            scored=False,
        )
        stage = Stage.objects.create(
            edition=edition,
            order=2,
            name="Ideação",
            kind=StageKind.SUBMISSION,
            starts_at=base + 30 * DAY,
            ends_at=base + 60 * DAY,
            evaluation_ends_at=base + 75 * DAY,
            max_score=Decimal("4.00"),
        )
        StageCriterion.objects.bulk_create(
            StageCriterion(stage=stage, criterion=c, max_score=Decimal(10))
            for c in criteria
        )

    def _support_tickets(self) -> None:
        users = [s.user for s in self.rng.sample(self.students, 30)]
        users += [t.user for ts in self.teachers_by_course.values() for t in ts][:10]
        statuses = [
            SupportTicketStatus.OPEN,
            SupportTicketStatus.IN_PROGRESS,
            SupportTicketStatus.RESOLVED,
            SupportTicketStatus.CLOSED,
        ]
        tickets = []
        for i, user in enumerate(users):
            status = statuses[i % len(statuses)]
            done = status in (SupportTicketStatus.RESOLVED, SupportTicketStatus.CLOSED)
            tickets.append(
                SupportTicket(
                    requester=user,
                    assigned_to=self.admin
                    if status != SupportTicketStatus.OPEN
                    else None,
                    title=TICKET_SUBJECTS[i % len(TICKET_SUBJECTS)],
                    description="Descrevo o problema e os passos que fiz no sistema.",
                    status=status,
                    priority=self.rng.choice(SupportTicketPriority.values),
                    support_response="Ajustado; teste de novo, por favor."
                    if done
                    else None,
                    resolved_at=self.now - self.rng.randint(1, 20) * DAY
                    if done
                    else None,
                )
            )
        SupportTicket.objects.bulk_create(tickets)


def _ascii(text: str) -> str:
    """Sem acento nem espaço, para montar o e-mail."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return plain.replace(" ", "")
