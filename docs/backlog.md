# Backlog — tasks curtas, três trilhas

Reorganização do trabalho para funcionar com disponibilidade irregular e prazo curto. A ideia central:
**ninguém espera ninguém.** Quem senta para trabalhar às 22h de domingo pega uma task da fila e começa.

## As seis regras

1. **Nenhuma task maior que uma sessão.** De 2 a 4 horas, mergeável sozinha. Se não cabe, quebra em duas.
   Task de dois dias vira branch aberta por uma semana, que vira conflito, que vira bloqueio.
2. **O esqueleto vem antes de tudo.** Com as 39 classes vazias criadas e migradas, a dependência entre
   apps desaparece: cada um preenche a sua.
3. **Quem tem disponibilidade irregular não fica no caminho crítico.** As duas pessoas mais constantes
   ficam na trilha crítica; as outras três nas trilhas paralela e independente.
4. **Task que bloqueia duas ou mais pessoas não é atribuída — é feita hoje**, por você ou em dupla.
5. **A fila nunca fica vazia.** Seu trabalho de coordenação é garantir cinco tasks sem dependência
   disponíveis o tempo todo.
6. **Ritual assíncrono.** Três frases no canal quando a pessoa senta: peguei X / terminei X, PR aberto /
   travei em X porque Y. Uma reunião por semana, com quem puder.

## As três trilhas

| Trilha | O que é | Horas | Bloqueia alguém? |
| :- | :- | :- | :- |
| **Crítica** | alinhamento, esqueleto, models | ~62h | sim |
| **Paralela** | factories, admin, seed, testes, CI | ~58h | não (precisa só do esqueleto) |
| **Independente** | casos de uso, contrato da API, protótipo, documentação | ~92h | não, nunca |

A coluna **Agora?** marca o que pode ser pego neste momento, sem depender de nada.

---

## Trilha crítica

Só as duas pessoas mais constantes. Tudo aqui bloqueia alguém.

| ID | Task | Horas | Depende de | Agora? |
| :- | :- | :- | :- | :- |
| C1 | Trocar a `SECRET_KEY` e mover para `.env` com `.env.example` | 1 | — | **sim** |
| C2 | `requirements.txt` → `pyproject.toml` + `uv.lock`; `.python-version` | 2 | — | **sim** |
| C3 | `config/settings.py` → `settings/{base,local,production}.py`; fuso e idioma | 2 | C2 | |
| C4 | Apps da raiz para `apps/`, com `name` e `label` no `apps.py` | 2 | C3 | |
| C5 | Renomear ao glossário: `config_edicao` → `editions`, `Perfil` → `UserRole`, campos em inglês | 3 | C4 | |
| **C6** | **Esqueleto: as 39 classes vazias (`id`, `Meta`, `__str__`) e a migração inicial** | **2** | **C5** | |
| C7 | `accounts/services.py` → `rules.py` + `use_cases/register_student.py`; views chamam o caso de uso | 3 | C5 | |

**A C6 é o ponto de virada do projeto.** Antes dela, a fila é serial. Depois dela, as 22 tasks de models
abaixo ficam todas disponíveis ao mesmo tempo. Ela leva duas horas. Faça-a no primeiro dia possível.

### Models — todas liberadas pela C6

| ID | App | Models | Horas |
| :- | :- | :- | :- |
| M01 | core | TimeStampedModel, Course | 2 |
| M02 | core | Sdg (= ODS) | 1 |
| M03 | accounts | Student (tirando matrícula, curso e período do `User`) | 2 |
| M04 | accounts | Teacher, TeacherCourse | 2 |
| M05 | accounts | ExternalReviewer, ajuste do EmailDomain | 2 |
| M06 | editions | Edition, EditionSdg | 3 |
| M07 | editions | Category | 1 |
| M08 | editions | Challenge | 2 |
| M09 | editions | Stage, StageSubmissionField | 3 |
| M10 | editions | Criterion, StageCriterion | 3 |
| M11 | editions | EditionReviewer | 1 |
| M12 | teams | Team, TeamMember — as três constraints difíceis | 4 |
| M13 | teams | Invitation, JoinRequest | 3 |
| M15 | projects | Project | 3 |
| M16 | projects | Submission, SubmissionVersion, SubmissionItem | 4 |
| M18 | evaluations | Evaluation, EvaluationItem | 3 |
| M19 | evaluations | StageScore | 2 |
| M21 | results | ProjectResult, StudentScore | 3 |
| M14 | teams | LeadershipRequest, MemberNote — *fase 2* | 2 |
| M17 | projects | SubmissionReceipt — *fase 2* | 1 |
| M20 | evaluations | FinalForm, FinalQuestion, FinalEvaluation, FinalAnswer — *fase 2* | 3 |
| M22 | results | CertificateTemplate, Certificate — *fase 2* | 2 |

Dentro de um app a ordem ainda importa um pouco (M06 antes de M07 a M11, M12 antes de M13), mas entre apps
não há mais espera. A regra de um dono por app continua, só que agora cada dono tem de duas a seis tasks
curtas em vez de uma grande.

---

## Trilha paralela

Libera junto com a C6. Não bloqueia ninguém: se uma dessas atrasar, nada para.

| ID | Task | Horas | Depende de |
| :- | :- | :- | :- |
| P01 | `pre-commit` com ruff e checagem de migração pendente | 2 | C2 |
| P02 | CI: `uv sync`, `ruff check`, `format --check`, `makemigrations --check`, `pytest` | 3 | P01 |
| P03 | Quebrar `accounts/tests.py` (845 linhas) em `test_models`, `test_use_cases`, `test_api` | 3 | C5 |
| P04 | Factories de core e accounts | 3 | M01–M05 |
| P05 | Factories de editions | 3 | M06–M11 |
| P06 | Factories de teams e projects | 3 | M12–M16 |
| P07 | Factories de evaluations e results | 2 | M18–M21 |
| P08 | Admin de core e accounts, com `list_display` e `search_fields` | 2 | M01–M05 |
| P09 | Admin de editions | 3 | M06–M11 |
| P10 | Admin de teams e projects | 3 | M12–M16 |
| P11 | Admin de evaluations e results | 2 | M18–M21 |
| P12 | Testes de constraint: core e accounts | 3 | P04 |
| P13 | Testes de constraint: editions | 4 | P05 |
| P14 | Testes de constraint: teams | 4 | P06 |
| P15 | Testes de constraint: projects | 3 | P06 |
| P16 | Testes de constraint: evaluations e results | 3 | P07 |
| P17 | Seed: uma edição fictícia completa, com cursos, ODS, desafios, etapas curtas e um usuário por perfil | 4 | P04–P07 |
| P18 | `get_valid_version()` em `projects/selectors.py`, com os três casos de teste | 3 | M16 |

O **P17 é o mais valioso da trilha**. Com o seed e o admin prontos, dá para percorrer o fluxo inteiro
clicando no admin do Django antes de existir qualquer tela — é a demonstração da sexta-feira e é onde os
erros de modelagem aparecem enquanto ainda são baratos.

---

## Trilha independente

**Tudo aqui pode ser pego agora.** Nenhuma task desta trilha depende de código, de ambiente ou de outra
pessoa. É daqui que saem as horas de quem aparece fora do horário combinado.

| ID | Task | Horas | Agora? |
| :- | :- | :- | :- |
| I01 | Corrigir o RF03: tirar "código/sigla" e ajustar o critério de aceitação | 1 | **sim** |
| I02 | Escrever os três casos de uso que faltam: cálculo da nota da etapa, zero automático por falta de entrega, congelamento do prazo de formação | 3 | **sim** |
| I03 | Especificar os casos de uso do Administrador (10 UCs): entradas, saídas, validações | 4 | **sim** |
| I04 | Especificar os casos de uso do Acadêmico, parte 1 — equipe (7 UCs) | 4 | **sim** |
| I05 | Especificar os casos de uso do Acadêmico, parte 2 — projeto e entrega (4 UCs) | 3 | **sim** |
| I06 | Especificar os casos de uso do Professor (3 UCs) | 2 | **sim** |
| I07 | Especificar os casos de uso do Painel Público (3 UCs) | 2 | **sim** |
| I08 | Contrato da API: autenticação e cadastros | 4 | **sim** |
| I09 | Contrato da API: configuração da edição | 4 | **sim** |
| I10 | Contrato da API: equipes, projeto e entregas | 4 | **sim** |
| I11 | Contrato da API: avaliação e resultado | 3 | **sim** |
| I12 | Inventário de telas e mapa de navegação por ator | 4 | **sim** |
| I13 | Padrão visual: paleta, tipografia, grid e componentes base | 4 | **sim** |
| I14 | Protótipo: telas do Acadêmico | 6 | depende de I12, I13 |
| I15 | Protótipo: telas do Professor | 4 | depende de I12, I13 |
| I16 | Protótipo: telas do Administrador | 6 | depende de I12, I13 |
| I17 | Protótipo: telas públicas | 3 | depende de I12, I13 |
| I18 | Matriz de rastreabilidade RF → UC → RN | 3 | **sim** |
| I19 | Roteiro de testes de aceitação a partir dos critérios dos RFs | 4 | **sim** |
| I20 | README do repositório: como subir o projeto em três comandos | 2 | **sim** |
| I21 | Roteiro da apresentação final e dados da demonstração | 3 | **sim** |

São **16 tasks disponíveis agora mesmo**, somando cerca de 50 horas. Ninguém precisa esperar o backend
para começar a cumprir carga horária.

---

## Alocação sugerida

| Papel | Quem | Trilha |
| :- | :- | :- |
| Caminho crítico | as 2 pessoas mais constantes | C1 a C7, depois os models |
| Apoio ao código | 1 pessoa | paralela: factories, admin, testes, seed |
| Documentação e contrato | 1 pessoa | independente: I01 a I11, I18, I19 |
| Protótipo | 1 pessoa | independente: I12 a I17 |
| Coordenação | você | manter cinco tasks livres na fila e desbloquear |

Não é uma divisão igualitária, e é de propósito: a trilha crítica precisa de presença constante, as outras
duas toleram trabalho em blocos irregulares.

## Sobre as 100 horas

Este backlog soma cerca de **210 horas**, de um total de 500. O restante vem da fase seguinte — os 36 casos
de uso implementados e a API — que é o grosso do projeto e só começa depois dos models.

Vale dizer uma coisa em voz alta com a equipe: se o critério de avaliação for hora e não entrega, quem
ficar sem trabalho disponível vai inflar as horas das tasks pequenas. A defesa não é cobrar mais, é manter
a fila cheia. Por isso a trilha independente importa tanto — ela é trabalho real, necessário, e não depende
de ninguém.
