# Contexto do trabalho — Desafio X backend

Atualizado em 24/10/2026. Resume o que foi feito nas tasks de models (issue #37), as decisões tomadas e o que falta, para quem continuar o trabalho.

## Estado das branches

| Branch | Task | Situação |
|---|---|---|
| `bm0` | BM0 (#28) — alinhamento | mesclada na `developer` (PR #51) |
| `feat/core-models-bm1` | BM1 (#29) — `core` | mesclada na `developer` (PR #52) |
| `feat/accounts-models-bm2` | BM2 (#30) — `accounts` | PR aberta, aguardando revisão |
| `feat/editions-models-bm3` | BM3 (#31) — `editions` | publicada; abrir a PR depois do merge da BM2 (criada a partir dela) |
| `docs/openapi-contract` | contrato da API e modelagem | publicada; PR ainda não aberta |

A branch `task3` (código original da Task 3) existe só localmente na máquina do Leonardo; tudo já foi portado.

## O que existe

- **core:** `TimeStampedModel`, `Course` (`name` único, `term_count` 8 ou 10), `Sdg` (1 a 17). Seeds por migração: ODS 1, 2, 3, 9 e 16 e os 15 cursos da UniCatólica (ensalamento 2026/2).
- **accounts:** `User` (login por e-mail, `name` único, `role`: ADMIN, STUDENT, TEACHER, EXTERNAL_REVIEWER), `EmailDomain`, `Student`, `Teacher`, `TeacherCourse`, `ExternalReviewer`. Autenticação por sessão + CSRF (`/api/auth/register`, `confirm-email`, `login`, `logout`, `me`, `csrf`). Caso de uso `register_student`. Comando `seed_users`.
- **editions:** `Edition`, `EditionSdg`, `Category`, `Challenge`, `Stage`, `StageSubmissionField`, `Criterion`, `StageCriterion`, `EditionReviewer`, com as unicidades da issue e do DBML e regras em `rules.py`.
- **projects:** `Project` (vazio), `Submission`, `SubmissionVersion`, `SubmissionItem`, `SubmissionReceipt` — adiantados de outra task, ainda não alinhados ao DBML.
- 97 testes passando no PostgreSQL.

## Decisões tomadas

- O guia vence o OpenAPI; a modelagem em português é a referência do banco.
- Período do aluno = `term`; períodos do curso = `term_count` (não `period`/`period_count`).
- Curso sem `slug`/sigla. ODS com `icon`. Nome do curso único.
- Etapa: `kind` (FORMATION, SUBMISSION, FINAL), `order`, `max_score` (parte da nota 0–10), `min_evaluations`.
- Edição com status SETUP, PUBLISHED, CLOSED (sem IN_PROGRESS, P-16 em aberto); edital como `regulation_url`.
- Sem FK composta: a consistência entre edições é validada em `rules.py` + `clean()`.
- `POST /api/auth/register` recebe `curso` como **id** do curso; o contrato HTTP da Task 3 (chaves em português) foi mantido.
- PostgreSQL (e não SQLite, como dizia a issue BM0); Docker na porta 5433.
- Equipes (para a BM4): unicidade só entre registros **ativos** (`equipe_membro`, no máximo 1 LIDER ativo) e só entre **pendentes** (`convite`, `solicitacao_entrada`, `solicitacao_lideranca`). SQL dos índices parciais no fim do DBML; no Django viram `UniqueConstraint(..., condition=Q(...))`.

## Próximos passos

1. **BM4 (#32) — app `teams`**, a partir da branch da BM3, seguindo o DBML (equipe, equipe_membro, convite, solicitacao_entrada, solicitacao_lideranca, observacao_integrante) e as regras de histórico acima.
2. Abrir as PRs pendentes (BM3 depois da BM2; `docs/openapi-contract` quando quiser).
3. Levar ao `gen_openapi.py` as divergências de nome: `slug` removido, `kind`/`order`/`max_score` da etapa, `rubric`, `EXTERNAL_REVIEWER`, `Submission`.

## Pendências conhecidas

- Auditoria (itens ainda abertos): validar formato do e-mail no cadastro; configurar envio de e-mail em produção; `wsgi.py`/`asgi.py` usam `config.settings.local` por padrão; `local.py`/`production.py` copiam cada setting à mão (usar `from .base import *`); falta teste do rollback quando o e-mail de confirmação falha; `projects` usa CASCADE sem comentário; README cita a porta 5432 e "nome de usuário"; `main.py` e `apps/projects/url.py` não são usados.
- Guia: testes da Task 3 em `TestCase` com nomes em português; `factory_boy` ainda não usado; `apps.py` sem `verbose_name` fora de `editions`.
- DBML em inglês (outro chat) tem ideias ainda não decididas: tabelas `accounts` (SSO Microsoft), `notification`, `support_ticket`, `project_course`; status de projeto e de nota diferentes.
- `seed_users` usa domínios fictícios (`aluno.desafiox.local`, `professor.desafiox.local`).
