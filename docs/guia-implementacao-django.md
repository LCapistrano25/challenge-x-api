# Guia de implementação — backend Django

Convenções obrigatórias para o backend da Plataforma Desafio X. Vale para todo mundo, desde o primeiro commit. Em caso de dúvida que este guia não resolve, decide-se no PR e o guia é atualizado no mesmo PR.

**Stack:** Python 3.12, Django 5, Django REST Framework, PostgreSQL, uv.

---

## 1. Idioma

**Código em inglês. Documentação e interface em português.**

| Onde | Idioma | Exemplo |
| :- | :- | :- |
| Nome de app, model, campo, função, variável, branch | inglês | `teams`, `TeamMember`, `joined_at`, `transfer_leadership()` |
| `verbose_name`, `help_text`, mensagens de erro, labels | português | `verbose_name = "integrante da equipe"` |
| Docstring e comentário | português | `"""Registra a saída do integrante (RF26)."""` |
| Commit e descrição de PR | português | `feat(teams): adiciona model TeamMember` |
| Dado no banco | como o usuário digitou | — |

A razão de misturar é prática: o código é lido por quem programa e segue a convenção universal da linguagem; a mensagem é lida pelo acadêmico e pelo professor, que não falam inglês.

Quem traduzir termo do domínio por conta própria cria sinônimo: `Avaliacao`, `Review`, `Assessment` e `Grade` para a mesma coisa. **O glossário da seção 7 é a única fonte** — nome que não estiver lá, discute-se antes de escrever.

---

## 2. Ambiente e pacotes com uv

### Primeira vez

```bash
git clone <repo> && cd desafiox-backend
uv sync                    # cria .venv e instala tudo a partir do uv.lock
cp .env.example .env       # preencher os valores locais
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

### Regras

- **Nunca usar `pip install`.** Dependência entra com `uv add <pacote>`, dependência de desenvolvimento com `uv add --dev <pacote>`.
- **`uv.lock` é versionado** e vai junto no PR que adiciona a dependência. É ele que garante que todo mundo roda a mesma versão.
- **Nunca ativar a venv na mão.** Todo comando passa por `uv run` — `uv run python manage.py ...`, `uv run pytest`, `uv run ruff check .`.
- **`.python-version` versionado**, criado com `uv python pin 3.12`.
- Dependência nova em PR separado quando não for óbvia, com uma linha dizendo por que ela é necessária.

### pyproject.toml

```toml
[project]
name = "desafiox-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "django>=5.1",
    "djangorestframework>=3.15",
    "django-environ>=0.11",
    "psycopg[binary]>=3.2",
]

[dependency-groups]
dev = [
    "ruff>=0.6",
    "pytest>=8.3",
    "pytest-django>=4.9",
    "factory-boy>=3.3",
    "pre-commit>=3.8",
]
```

---

## 3. Credenciais e configuração

**Nenhum segredo no código, nenhum segredo no Git.** Vale para `SECRET_KEY`, senha de banco, senha de SMTP e qualquer chave de serviço.

- `.env` fica no `.gitignore` e **nunca** é commitado.
- `.env.example` é versionado, com todas as chaves e valores falsos. Quem adiciona uma variável nova atualiza o exemplo no mesmo PR, senão o próximo que clonar o repositório não sobe o projeto.
- Leitura por `django-environ`, uma vez só, em `config/settings/base.py`.
- **Falha cedo:** variável obrigatória sem valor derruba o processo na inicialização. É melhor não subir do que subir com `DEBUG=True` em produção por engano.

```python
# config/settings/base.py
import environ

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")          # sem default: obrigatório
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])
DATABASES = {"default": env.db("DATABASE_URL")}

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Araguaina"
USE_TZ = True
USE_I18N = True

AUTH_USER_MODEL = "accounts.User"
```

### .env.example

```dotenv
DJANGO_SECRET_KEY=troque-este-valor
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgres://desafiox:desafiox@localhost:5432/desafiox
EMAIL_HOST=
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
```

Se um segredo real for commitado por engano: **trocar o segredo**, não apagar o commit. O histórico do Git já saiu da máquina de quem fez o push.

---

## 4. Estrutura de pastas

```
desafiox-backend/
├── pyproject.toml
├── uv.lock
├── .python-version
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── manage.py
├── README.md
├── docs/
│   └── guia-de-implementacao.md        ← este arquivo
├── config/                             ← o projeto Django, não um app
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py                     ← tudo que é comum
│   │   ├── local.py                    ← from .base import *
│   │   └── production.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
└── apps/
    ├── __init__.py
    ├── core/
    ├── accounts/
    ├── editions/
    ├── teams/
    ├── projects/
    ├── evaluations/
    └── results/
```

Os apps ficam dentro de `apps/`, e cada um declara o próprio label:

```python
# apps/teams/apps.py
class TeamsConfig(AppConfig):
    name = "apps.teams"
    label = "teams"            # sem isso, as FKs viram "apps_teams.Team"
    verbose_name = "Equipes"
```

### Dentro de um app

```
apps/teams/
├── __init__.py
├── apps.py
├── enums.py          ← TextChoices
├── models.py         ← vira pacote models/ quando passar de 5 models
├── use_cases/        ← escrita: um arquivo por caso de uso do documento
│   ├── __init__.py
│   ├── leave_team.py
│   └── transfer_leadership.py
├── rules.py          ← validações que mais de um caso de uso usa
├── selectors.py      ← leitura: consultas que mais de uma view usa
├── serializers.py    ← DRF: entrada e saída, sem regra de negócio
├── views.py
├── urls.py
├── admin.py
├── factories.py      ← factory_boy, usado por teste e por seed
├── migrations/
└── tests/
    ├── __init__.py
    ├── test_models.py      ← constraints
    ├── test_use_cases.py   ← regras
    └── test_api.py         ← contrato HTTP
```

**Por que `use_cases/` existe:** a regra de negócio precisa de um lugar só. Se ela mora na view, o comando de terminal e o admin não a executam; se mora no `save()` do model, não dá para passar quem é o autor da ação nem exigir justificativa. Com o caso de uso explícito, a mesma função vale para a API, para o admin e para o teste.

Regra prática: **view não sabe regra, serializer não sabe regra, model não sabe regra.** A view recebe e responde, o serializer valida formato, o model guarda e garante integridade, o caso de uso decide.

As seis regras da pasta:

1. **A pasta fica dentro do app**, nunca na raiz. Uma pasta global de casos de uso quebraria a linha de dependência entre apps.
2. **Um arquivo, um caso de uso, uma função pública.** Nome do arquivo igual ao da função, em inglês, verbo no infinitivo.
3. **Cabeçalho obrigatório** citando o UC, o RF e as RNs implementadas.
4. **Assinatura padrão:** argumentos nomeados, `actor` sempre presente, `@transaction.atomic`.
5. **Leitura não vira caso de uso.** Consulta e listagem ficam em `selectors.py`.
6. **Validação usada por mais de um caso de uso vai para `rules.py`.** Sem isso, "o prazo de formação está aberto?" aparece copiado em oito arquivos e um dia muda em sete.

Dos 51 casos de uso do documento, 12 são consulta (UC01, UC16, UC23, UC35, UC37, UC38, UC42, UC44, UC47, UC49, UC50, UC51) e 3 são autenticação (UC22, UC41, UC46), que o Django já resolve. Os 36 restantes viram arquivo.

---

## 5. Convenções de código

### Nomes

| Coisa | Padrão | Exemplo |
| :- | :- | :- |
| App | plural, minúsculo | `teams`, `editions` |
| Model | singular, PascalCase | `TeamMember` |
| Campo | snake_case | `joined_at`, `max_members` |
| Booleano | sem `is_` quando for estado óbvio | `active`, `scored` |
| Data/hora | sufixo `_at` | `created_at`, `submitted_at` |
| FK | nome da entidade, singular | `team`, `edition` |
| `related_name` | plural do model que aponta | `related_name="members"` |
| Enum | `TextChoices`, nome singular | `class TeamStatus(models.TextChoices)` |
| Serviço | verbo no infinitivo | `transfer_leadership()`, `submit_stage()` |
| Selector | `get_` ou `list_` | `list_pending_evaluations()` |

### Model

```python
class TeamMember(TimeStampedModel):
    """Integrante de uma equipe (RF22 a RF27)."""

    team = models.ForeignKey("teams.Team", on_delete=models.PROTECT, related_name="members")
    edition = models.ForeignKey("editions.Edition", on_delete=models.PROTECT, related_name="team_members")
    student = models.ForeignKey("accounts.Student", on_delete=models.PROTECT, related_name="memberships")
    role = models.CharField(max_length=20, choices=MemberRole, default=MemberRole.MEMBER)
    joined_at = models.DateTimeField()
    left_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "integrante da equipe"
        verbose_name_plural = "integrantes da equipe"
        constraints = [
            models.UniqueConstraint(fields=["team", "student"], name="unique_student_per_team"),
            models.UniqueConstraint(fields=["edition", "student"], name="unique_team_per_edition"),
            models.UniqueConstraint(
                fields=["team"],
                condition=models.Q(role="LEADER", active=True),
                name="single_active_leader_per_team",
            ),
        ]
```

Obrigatório em todo model:

1. Docstring de uma linha com o RF ou a RN de origem.
2. FK entre apps **sempre por string** (`"editions.Edition"`), nunca import direto — senão dá ciclo de importação.
3. `on_delete=models.PROTECT` por padrão. `CASCADE` só quando o filho não faz sentido sozinho (item dentro de uma versão de entrega) e com comentário dizendo por quê.
4. `related_name` explícito em toda FK.
5. `verbose_name` e `verbose_name_plural` em português.
6. Constraints no `Meta`, com `name` em inglês e descritivo.

### Caso de uso

```python
# apps/teams/use_cases/leave_team.py
"""UC29 — Sair da equipe. RF26. Regras: RN04, RN08, RN09, RN14, RN38."""


@transaction.atomic
def leave_team(*, membership: TeamMember, actor: User) -> None:
    ensure_formation_period_is_open(membership.team.edition)
    ensure_is_self_or_admin(membership, actor)
    if membership.role == MemberRole.LEADER:
        raise LeaderMustTransferFirst()
    membership.active = False
    membership.left_at = timezone.now()
    membership.save(update_fields=["active", "left_at"])
```

- **Argumentos sempre nomeados** (`*` no começo). Impede trocar a ordem de dois parâmetros do mesmo tipo.
- **`@transaction.atomic`** em todo caso de uso que escreve em mais de uma tabela.
- **Type hints** na assinatura.
- **`actor` explícito.** Nenhum caso de uso descobre quem fez a ação sozinho — quem chama informa. É com ele que as regras de permissão funcionam, e é o que vai permitir ligar a auditoria na fase 2 sem reescrever assinatura.
- Justificativa obrigatória vira parâmetro sem valor padrão (RF13).
- Ação disparada pelo sistema recebe `actor=None`.

### Regra de negócio: função ou classe

**Função por padrão.** Classe sem estado com um método `execute()` é uma função com etapas a mais, e o teste de uma função não precisa de setup.

O prefixo do nome diz o que a função faz com o resultado:

| Prefixo | Retorna | Quando falha | Exemplo |
| :- | :- | :- | :- |
| `ensure_` | nada | levanta exceção | `ensure_formation_period_is_open(edition)` |
| `is_` / `can_` / `has_` | `bool` | não falha | `can_submit(team, stage)` |
| `compute_` | valor | não falha | `compute_student_points(score, term)` |

As versões `is_` e `ensure_` costumam andar em par: a primeira responde para a tela ("mostro o botão?"), a segunda protege o caso de uso ("ele burlou a tela?"), e a segunda usa a primeira.

Classe se paga em três casos, e só:

1. **Resultado composto de um cálculo** — `@dataclass(frozen=True)` sem comportamento, para não devolver tupla de três itens que alguém vai trocar de ordem.
2. **Variação real de comportamento com três ou mais casos.** A conversão de nota em pontos tem duas regras e meia hoje (1º período, demais períodos, Psicologia): `if` resolve. Só vira objeto por variante se crescer.
3. **`TextChoices`**, que já é classe por obrigação do Django.

Não fazer: classe com um `execute()` (é função), classe só com `@staticmethod` (é módulo — `rules.py` já faz esse papel).

### Regra no model: cuidado com o clean()

**`save()` não chama `full_clean()`.** Um `objects.create()` ou um `bulk_create` passam por cima da validação, e a regra que parecia garantida não rodou. A divisão correta:

| Tipo de regra | Onde |
| :- | :- |
| Integridade (unicidade, limite de valor) | `Meta.constraints` — quem recusa é o banco |
| Regra que depende de outra entidade ou do relógio | função em `rules.py`, chamada pelo caso de uso |
| Cálculo | função `compute_` em módulo próprio |

### Mapa de casos de uso por app

| App | Arquivos em `use_cases/` |
| :- | :- |
| `core` | `create_course` (UC03), `create_sdg` (UC04 — cadastrar ODS) |
| `accounts` | `configure_email_domains` (UC02), `register_student` (UC21), `register_teacher` (UC10), `register_external_reviewer` (UC11) |
| `editions` | `create_edition` (UC18), `close_edition` (UC18), `publish_regulation` (UC09), `create_challenge` (UC05), `create_criterion` (UC06), `create_stage` (UC07), `configure_stage_criteria` (UC08), `configure_team_limits` (UC19), `create_category` (UC20), `extend_deadline` (UC14) |
| `teams` | `create_team` (UC24), `invite_member` (UC25), `respond_invitation` (UC26), `request_to_join` (UC27), `respond_join_request` (UC28), `leave_team` (UC29), `transfer_leadership` (UC30), `request_leadership` (UC31), `review_leadership_request` (UC45), `add_member_note` (UC36), `disqualify_team` (UC13), `flag_team_status` (UC40) |
| `projects` | `select_challenge` (UC32), `save_project_details` (UC33), `select_category` (UC39), `submit_stage_delivery` (UC34) |
| `evaluations` | `configure_final_form` (UC12), `evaluate_submission` (UC43), `evaluate_finalist` (UC48), `adjust_score` (UC14) |
| `results` | `approve_finalists` (UC15), `issue_certificates` (UC17) |

O UC18 e o UC14 viram dois arquivos cada: são ações diferentes, com regras diferentes, que o documento juntou em um caso de uso só.

Três casos de uso que o sistema precisa e o documento ainda não tem: `compute_stage_score`, `apply_zero_for_missing_submission` (RN24) e `freeze_formation_period`. São disparados pelo sistema e devem entrar no documento como casos de uso novos.

### Factories

Factory é uma receita que cria um registro válido do model com dados plausíveis, preenchendo sozinha tudo
que o teste não se importa. É o que permite cinco pessoas trabalharem em paralelo: quem implementa
`projects` precisa de uma equipe válida no banco de teste, não do código de quem faz `teams`.

**O dono do app escreve a factory dos seus models, no mesmo PR do model.** Só ele sabe o que é um registro
válido. Fica em `apps/<app>/factories.py` e todo mundo importa. **Model sem factory bloqueia os outros.**

```python
# apps/accounts/factories.py
class StudentFactory(DjangoModelFactory):
    class Meta:
        model = Student

    user = factory.SubFactory(UserFactory)
    course = factory.SubFactory(CourseFactory)
    registration = factory.Sequence(lambda n: f"2026{n:05d}")
    term = 3
```

**`Sequence` em todo campo único.** O modelo tem muitos: `registration`, `Team.code`, `Sdg.number`,
`User.email`, `Edition` em (year, semester). Valor fixo quebra no segundo teste.

**Objeto que não existe sozinho nasce completo.** Uma `Team` sem líder não serve para quase nenhuma regra:

```python
# apps/teams/factories.py
class TeamFactory(DjangoModelFactory):
    class Meta:
        model = Team

    edition = factory.SubFactory(EditionFactory)
    name = factory.Sequence(lambda n: f"Equipe {n}")
    code = factory.Sequence(lambda n: f"EQ{n:04d}")

    @factory.post_generation
    def leader(self, create, extracted, **kwargs):
        if create:
            TeamMemberFactory(team=self, edition=self.edition, role=MemberRole.LEADER)
```

**A armadilha da edição compartilhada.** `edition` aparece em `Team`, `TeamMember`, `Project`, `Challenge`,
`Stage` e `Criterion`. Se você não passar a mesma edição explicitamente, cada `SubFactory` cria a sua, e o
cenário fica incoerente — equipe na edição A, desafio na edição B. O teste passa por acidente ou falha por
um motivo que não é o que você queria testar.

```python
team = TeamFactory()
challenge = ChallengeFactory(edition=team.edition)      # ← sempre explícito
project = ProjectFactory(team=team, challenge=challenge)
```

**Variações com `trait`**, para o teste ficar legível: `TeamFactory(incomplete=True)`,
`TeamFactory(disqualified=True)`.

O seed reusa as mesmas factories, com dados reais no lugar dos sequenciais — em vez de 200 linhas de
`objects.create()`, 30 linhas chamando factories.

### Quando o seu app precisa de outro

A regra cabe em uma frase: **você lê de qualquer app abaixo do seu na cadeia de dependência, e escreve só
no seu.**

A cadeia é `core ← accounts ← editions ← teams ← projects ← evaluations ← results`. Importar de um app
acima do seu fecha um ciclo e quebra o `import` de todo mundo.

| Situação | O que fazer |
| :- | :- |
| Preciso **ler** dado de um app abaixo | Importe o model ou o selector dele direto. É permitido e esperado |
| Preciso de um **selector que não existe** lá | Abra um PR pequeno no app do outro, com o dono como revisor. Dono é responsabilidade, não cadeado |
| Preciso de uma **regra de negócio** do outro app | Abra issue para o dono. Enquanto isso, função provisória no seu app com `# TODO mover para <app>` |
| Preciso **escrever** em um model de outro app | Não escreva direto. Ou o caso de uso é seu e o model está no app errado, ou a ação pertence ao outro app |
| A ação **cruza dois apps** | Ela mora no app que **escreve**, lê do que está abaixo, e é disparada por um comando |

O último caso é o do congelamento no fim do prazo de formação: ele **escreve** em `teams` e **lê** a
`Stage` de `editions`. Então `freeze_formation_period` fica em `teams/use_cases/`, lê a etapa, e é
disparado por `manage.py freeze_formation`. `editions` nunca importa `teams`. O mesmo vale para o zero
automático por falta de entrega.

**Mudança de model que afeta dois apps** é mudança de schema: passa pelo dono do modelo de dados, atualiza
o DBML e o diagrama, e vai num PR só.

#### Como importar, na prática

```python
# ✓ FK para model de outro app: SEMPRE por string, nunca import direto
team = models.ForeignKey("teams.Team", on_delete=models.PROTECT, related_name="projects")

# ✓ selector de um app abaixo: import normal, no topo do arquivo
from apps.teams.selectors import get_active_leader

# ✓ enum e regra de um app abaixo
from apps.editions.enums import StageKind
from apps.editions.rules import ensure_edition_is_published

# ✗ import de um app ACIMA do seu: fecha ciclo, quebra o projeto inteiro
# em apps/editions/use_cases/close_stage.py
from apps.teams.use_cases.freeze_formation import freeze_formation_period

# ✗ import do model em vez de string na FK: ciclo em tempo de carga
from apps.editions.models import Edition
edition = models.ForeignKey(Edition, ...)
```

**Por que a FK vai por string.** `"teams.Team"` é resolvido pelo Django depois que todos os apps
carregaram. O import direto é resolvido na hora, então dois models que se referenciam travam a
inicialização. Com string, isso nunca acontece — e é por isso que a regra vale mesmo quando o app está
abaixo do seu e o import direto funcionaria.

**Import dentro da função** (`def f(): from apps.x import y`) resolve ciclo e é um cheiro: significa que a
dependência está na direção errada. Se aparecer, o certo é mover o código, não esconder o import. A única
exceção aceitável é um comando de terminal, onde o custo de carregar tudo no topo não compensa.

O ruff cuida da ordem e do agrupamento dos imports (regra `I`) — ninguém discute isso em PR.

### Proibido

- `signal` para regra de negócio. Serve para efeito colateral técnico, e só.
- `import` de um app que está acima do seu na cadeia de dependência.
- `print` para depuração. Use `logging`.
- Query dentro de laço. Use `select_related` e `prefetch_related`.
- `objects.get()` sem tratar `DoesNotExist`.
- Texto em português fora de `verbose_name`, `help_text` e mensagem de erro.
- Migração editada à mão depois de ter ido para o `main`.

---

## 6. Apps e seus models

Sete apps, na ordem de dependência. Nenhuma seta aponta para trás.

| # | App | Models |
| :- | :- | :- |
| 1 | `core` | TimeStampedModel (abstrato), Course, Sdg (= ODS) |
| 2 | `accounts` | User, EmailDomain, Student, Teacher, TeacherCourse, ExternalReviewer |
| 3 | `editions` | Edition, EditionSdg (= ODS da edição), Category, Challenge, Stage, StageSubmissionField, Criterion, StageCriterion, EditionReviewer |
| 4 | `teams` | Team, TeamMember, Invitation, JoinRequest, LeadershipRequest, MemberNote |
| 5 | `projects` | Project, Submission, SubmissionVersion, SubmissionItem, SubmissionReceipt |
| 6 | `evaluations` | Evaluation, EvaluationItem, StageScore, FinalForm, FinalQuestion, FinalEvaluation, FinalAnswer |
| 7 | `results` | ProjectResult, StudentScore, CertificateTemplate, Certificate |

São os 40 models do `banco-desafio-x.dbml`.

---

## 7. Glossário — português do documento para inglês do código

Esta é a tabela que evita sinônimo. Termo que não estiver aqui não é traduzido por conta própria.

### Entidades

| Documento | Código | Documento | Código |
| :- | :- | :- | :- |
| Curso | `Course` | Entrega | `Submission` |
| ODS | `Sdg` *(Sustainable Development Goal)* | Versão da entrega | `SubmissionVersion` |
| Edição | `Edition` | Item da entrega | `SubmissionItem` |
| Categoria | `Category` | Comprovante | `SubmissionReceipt` |
| Desafio | `Challenge` | Avaliação | `Evaluation` |
| Etapa | `Stage` | Item da avaliação | `EvaluationItem` |
| Critério | `Criterion` | Nota da etapa | `StageScore` |
| Rubrica | `rubric` | Formulário final | `FinalForm` |
| Equipe | `Team` | Avaliação final | `FinalEvaluation` |
| Integrante | `TeamMember` | Resultado do projeto | `ProjectResult` |
| Convite | `Invitation` | Pontuação do aluno | `StudentScore` |
| Solicitação de entrada | `JoinRequest` | Certificado | `Certificate` |
| Solicitação de liderança | `LeadershipRequest` | Log de auditoria | `AuditLog` (fase 2) |
| Observação sobre integrante | `MemberNote` | Domínio de e-mail | `EmailDomain` |
| Projeto | `Project` | | |

### Atores

| Documento | Código |
| :- | :- |
| Administrador | `admin` |
| Acadêmico / aluno | `Student` |
| Professor | `Teacher` |
| Avaliador Externo | `ExternalReviewer` |
| Líder | `leader` |

### Termos do domínio

| Documento | Código | Observação |
| :- | :- | :- |
| Prazo de formação de equipes | `formation period` | `Stage` com `kind = FORMATION` |
| Nota (0 a 10) | `score` | nunca `grade` nem `note` |
| Pontos na disciplina | `points` | `StudentScore.points` |
| Desempate | `tiebreak` | `Criterion.tiebreak_order` |
| Finalista | `finalist` | |
| Homologar | `approve` | `ProjectResult.approved_at` |
| Premiação | `award` | |
| Desclassificar | `disqualify` | |
| Edital | `regulation` | `Edition.regulation_file` |
| Período do aluno | `term` | 1 a 8 ou 1 a 10 |
| Semestre da edição | `semester` | 1 ou 2 |
| Congelar | `freeze` | fim do prazo de formação |

Dois pares que confundem e precisam de atenção: **`term` é o período do aluno**, `semester` é o semestre da edição; **`score` é nota de 0 a 10**, `points` é o que vira ponto na disciplina.

**`Sdg` é ODS.** É a sigla oficial da ONU, *Sustainable Development Goals* — ODS 9 é SDG 9. Como a equipe e a interface falam "ODS" o tempo todo, o model carrega a tradução em dois lugares, para ninguém precisar adivinhar:

```python
class Sdg(TimeStampedModel):
    """ODS — Objetivo de Desenvolvimento Sustentável (Sustainable Development Goal). RF04."""

    number = models.PositiveSmallIntegerField(unique=True)   # ODS 1, 2, 3, 9, 16
    title = models.CharField(max_length=200)

    class Meta:
        verbose_name = "ODS"
        verbose_name_plural = "ODS"
```

A mesma regra vale para `EditionSdg` (as ODS aceitas na edição) e para `Challenge.sdg`.

---

## 8. Qualidade

### Ferramentas

- **ruff** faz lint e formatação. Uma ferramenta só, sem discussão de estilo no PR.
- **pytest + pytest-django** para teste. Nada de `unittest` da biblioteca padrão.
- **factory_boy** para dados de teste. Nada de fixture em JSON.
- **pre-commit** roda ruff e checagem de migração pendente antes do commit.

```toml
# pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "DJ", "B", "C4"]

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings.local"
python_files = ["test_*.py"]
```

### O que precisa de teste

| Tipo | Exigência |
| :- | :- |
| Constraint do banco | um teste por constraint, tentando violar e esperando `IntegrityError` |
| Serviço | caminho feliz e cada regra que bloqueia a ação |
| Prazo | antes do prazo, dentro do prazo e depois do prazo |
| Auditoria | o registro foi criado, com o autor certo |
| Endpoint | status de sucesso, de erro de validação e de permissão negada |

Teste de `__str__` e de campo que só guarda valor não conta e não é exigido.

### CI

O pipeline roda em todo PR: `uv sync`, `ruff check`, `ruff format --check`, `python manage.py makemigrations --check --dry-run` e `pytest`. Os cinco precisam passar. O terceiro é o que pega o caso mais comum — alguém mudou o model e esqueceu de gerar a migração.

---

## 9. Git

- **Branch:** `tipo/app-descricao-curta`, em inglês. `feat/teams-member-model`, `fix/editions-stage-order`.
- **Commit:** `tipo(escopo): descrição` em português. `feat(teams): adiciona constraint de líder único`.
- Tipos: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`.
- **PR pequeno**, de um app só, com descrição dizendo o que muda e qual RF atende.
- **Um dono por app** durante a fase de models. Migração só conflita quando duas pessoas mexem no mesmo app.
- Ninguém commita direto no `main`.

### Checklist do PR

- [ ] Nomes seguem o glossário
- [ ] Nenhum segredo no diff; `.env.example` atualizado se houve variável nova
- [ ] Migração gerada e aplicada em banco limpo
- [ ] Constraints do DBML presentes no `Meta`
- [ ] Teste por constraint e por regra nova
- [ ] Regra de negócio no caso de uso, não na view nem no serializer
- [ ] Caso de uso com cabeçalho citando UC, RF e RNs
- [ ] Caso de uso recebe `actor`, mesmo quando ainda não usa
- [ ] `uv.lock` incluído se houve dependência nova

---

## 10. Começando do zero

Sequência do dia 1, feita por uma pessoa e revisada pelas outras no mesmo dia:

```bash
uv init desafiox-backend && cd desafiox-backend
uv python pin 3.12
uv add django djangorestframework django-environ "psycopg[binary]"
uv add --dev ruff pytest pytest-django factory-boy pre-commit

uv run django-admin startproject config .
mkdir apps && touch apps/__init__.py

# settings dividido em base/local/production, .env.example criado
# AUTH_USER_MODEL = "accounts.User" ANTES da primeira migração

uv run python manage.py startapp accounts apps/accounts
# ... ajustar apps.py com name e label

uv run python manage.py makemigrations
uv run python manage.py migrate
```

**A ordem importa em um ponto:** `AUTH_USER_MODEL` precisa apontar para o model customizado antes de rodar `migrate` pela primeira vez. Depois da primeira migração, trocar o model de usuário exige apagar o banco e recriar todas as migrações.
