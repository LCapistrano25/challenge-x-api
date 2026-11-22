# Contexto do trabalho — Desafio X backend

Atualizado em 21/11/2026. Resume as decisões tomadas e o que existe, para quem continuar o trabalho. O andamento das tasks está nas issues e PRs do GitHub; as pendências do contrato, em `docs/api/api-pendencias.md`.

## O que existe

- **core:** `TimeStampedModel`, `Course` (`name` único, `term_count` 8 ou 10), `Sdg` (1 a 17). Seeds por migração: ODS 1, 2, 3, 9 e 16 e os 15 cursos da UniCatólica (ensalamento 2026/2).
- **accounts:** `User` (login por e-mail, `name` único, `role`: ADMIN, STUDENT, TEACHER, EXTERNAL_REVIEWER), `EmailDomain`, `Student`, `Teacher`, `TeacherCourse`, `ExternalReviewer`. Autenticação por sessão + CSRF (`/api/auth/sessions/password`, `logout`, `me`, `csrf`): senha só para ADMIN e EXTERNAL_REVIEWER (este, vinculado à edição publicada); aluno e professor entram pela Microsoft (#93). Autocadastro do aluno logado em `/api/auth/students` (caso de uso `register_student`). Comando `seed_users`.
- **editions:** `Edition`, `EditionSdg`, `Category`, `Challenge`, `Stage`, `StageSubmissionField`, `Criterion`, `StageCriterion`, `EditionReviewer`, com as unicidades da issue e do DBML e regras em `rules.py`.
- **projects:** `Project`, `DeadlineExtension`, `Submission`, `SubmissionVersion`, `SubmissionItem`, `SubmissionReceipt`.
- O DBML (`docs/modelagem/desafio-x.dbml`) é gerado das models por `docs/modelagem/gen_dbml.py`; não se edita à mão.

## Decisões tomadas

- O contrato da API (OpenAPI) é a autoridade da interface: define os campos, enums e erros que vão para o frontend; o código se ajusta a ele (21/11/2026, D1 da auditoria de 18/11). O guia vale para padrões de código; a modelagem em português, para nomes do banco.
- Período do aluno = `term`; períodos do curso = `term_count` (não `period`/`period_count`).
- Curso sem `slug`/sigla. ODS com `icon`. Nome do curso único.
- Etapa: `kind` (FORMATION, SUBMISSION, FINAL), `order`, `max_score` (parte da nota 0–10), `min_evaluations`.
- Edição com status SETUP, PUBLISHED, CLOSED (sem IN_PROGRESS, P-16 em aberto); edital como `regulation_url`.
- Sem FK composta: a consistência entre edições é validada em `rules.py` + `clean()`.
- As rotas de `accounts` seguem o contrato OpenAPI (campos em inglês); o cadastro com senha e a confirmação de e-mail da Task 3 saíram (#92). Ids de usuário são inteiros.
- PostgreSQL (e não SQLite, como dizia a issue BM0); Docker na porta 5433.
- Equipes (para a BM4): unicidade só entre registros **ativos** (`equipe_membro`, no máximo 1 LIDER ativo) e só entre **pendentes** (`convite`, `solicitacao_entrada`, `solicitacao_lideranca`). SQL dos índices parciais no fim do DBML; no Django viram `UniqueConstraint(..., condition=Q(...))`.

## Próximos passos

Ver as issues abertas da sprint e a #179 (pendências). Divergência entre código e contrato se resolve no código; se o contrato estiver errado, abre-se issue de decisão antes de mudar o `gen_openapi.py`.

## Pendências conhecidas

- Auditoria (itens ainda abertos): validar formato do e-mail no cadastro; configurar envio de e-mail em produção; `wsgi.py`/`asgi.py` usam `config.settings.local` por padrão; `local.py`/`production.py` copiam cada setting à mão (usar `from .base import *`); falta teste do rollback quando o e-mail de confirmação falha; `apps/projects/url.py` não é usado.
- Guia: testes da Task 3 em `TestCase` com nomes em português; `apps.py` sem `verbose_name` fora de `editions`.
- DBML em inglês (outro chat) tem ideias ainda não decididas: tabelas `accounts` (SSO Microsoft), `notification`, `support_ticket`, `project_course`; status de projeto e de nota diferentes.
- `seed_users` usa domínios fictícios (`aluno.desafiox.local`, `professor.desafiox.local`).
