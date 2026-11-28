# Roteiro 05 — Admin: usuários, equipes, suporte e resultados

| | |
|---|---|
| **Responsável** | |
| **Data / commit testado** | |
| **Perfis** | ADMIN; STUDENT e TEACHER (chamados, 403); EXTERNAL_REVIEWER (avaliação final e conta desativada) |
| **Pré-requisitos** | Ambiente do README com `seed_users` e o cenário **em modo resultados**: `CENARIO=resultados uv run python manage.py shell -c "exec(open('docs/testes/cenario.py').read())"`. Nesse modo, as duas etapas de entrega já estão encerradas e o projeto da "Equipe Seed" tem nota definitiva nas duas. A "Equipe Sem Lider B" não entregou nada. |
| **Login** | `admin.jar`, `aluno.jar`, `prof.jar` e `aval.jar` com a senha do `seed_users`; `l1.jar` = `livre1@aluno.desafiox.local` com `TesteForte!2026x`. |

Cole aqui a saída do cenário:

```
```

Coluna **Resultado**: `ok`, `falhou #N` ou `bloqueado`. Faça as seções na ordem: a 5.8 encerra a edição.

## 5.1 Sessão

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | sem login | `GET /api/auth/csrf` | — | **200**, `{"csrfToken": ...}` e cookie `csrftoken` | |
| 2 | sem login | `POST /api/auth/sessions/password` **sem** `X-CSRFToken` (`curl` direto, sem `api`) | `{"email":"admin@desafiox.local","password":"..."}` | **403** `permission_denied` ("CSRF Failed") | |
| 3 | sem login | `POST /api/auth/sessions/password` | `{"email":"admin@desafiox.local","password":"errada"}` | **401** `invalid_credentials` | |
| 4 | sem login | o mesmo | `{"email":"naoexiste@x.com","password":"errada"}` | **401** `invalid_credentials` (mesma mensagem do passo 3) | |
| 5 | sem login | o mesmo | `{"email":"admin@desafiox.local"}` | **400** `validation_error` em `password` | |
| 6 | sem login | o mesmo | `{"email": ` (JSON quebrado) | **400** `parse_error` | |
| 7 | sem login | `POST /api/auth/sessions/microsoft` | `{"code":"codigo-falso"}` | **401** `invalid_credentials`; sem as variáveis `MICROSOFT_*` no `.env`, **503** `external_service_error` | |
| 8 | admin | `GET /api/auth/me` | — | **200**, `role: ADMIN` | |
| 9 | aluno | `POST /api/auth/logout` | — | **204** | |
| 10 | aluno | `GET /api/auth/me` | — | **401** `not_authenticated`. Faça login de novo com `aluno.jar`. | |

## 5.2 Alunos

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | admin | `GET /api/admin/students?search=livre&active=true&course_id={COURSE_ES}` | — | **200** paginado, livre1 a livre6 com `registration_number`, `course` e `term` | |
| 2 | admin | `GET /api/admin/students?course_id=abc` | — | **400** | |
| 3 | admin | `GET /api/admin/students?page=99` | — | **404** | |
| 4 | aluno | `GET /api/admin/students` | — | **403** | |
| 5 | admin | `GET /api/admin/students/{LIVRE1_STUDENT_ID}` | — | **200** | |
| 6 | admin | `GET /api/admin/students/999999` | — | **404** | |
| 7 | admin | `PATCH /api/admin/students/{LIVRE1_STUDENT_ID}` | `{"name":"Livre Um","term":4}` | **200**, dados novos | |
| 8 | admin | o mesmo | `{"registration_number":"SEED001"}` | **409** `registration_number_taken` | |
| 9 | admin | o mesmo | `{"term":99}` | **400** | |
| 10 | admin | o mesmo | `{"email":"outro@aluno.desafiox.local"}` | **400** (e-mail não é editável) | |
| 11 | livre1 | `GET /api/auth/me` (com `l1.jar` já logado) | — | **200** | |
| 12 | admin | `PATCH /api/admin/students/{LIVRE1_STUDENT_ID}/status` | `{"active":false}` | **200**, `{"user_id": ..., "active": false}` | |
| 13 | livre1 | `GET /api/auth/me` (o mesmo `l1.jar`) | — | **401** (a sessão aberta caiu) | |
| 14 | livre1 | `login l1.jar livre1@aluno.desafiox.local 'TesteForte!2026x'` | — | **401** `invalid_credentials` | |
| 15 | admin | `PATCH .../{LIVRE1_STUDENT_ID}/status` | `{"active":"sim"}` | **400** | |
| 16 | admin | `PATCH .../{LIVRE1_STUDENT_ID}/status` | `{"active":true}` | **200**; o login do passo 14 volta a dar **200** | |
| 17 | admin | `PATCH /api/admin/students/1/status` (o id do admin) | `{"active":false}` | **404** (conta ADMIN não é alterada) | |

## 5.3 Professores

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | admin | `GET /api/admin/teachers?search=professor&active=true` | — | **200** paginado; anote o `user_id` do professor seed como `{PROF}` | |
| 2 | admin | `GET /api/admin/teachers?active=abc` | — | **400** | |
| 3 | admin | `GET /api/admin/teachers?page=99` | — | **404** | |
| 4 | admin | `GET /api/admin/teachers/{PROF}` | — | **200**, `courses` com Engenharia de Software | |
| 5 | admin | `PATCH /api/admin/teachers/{PROF}` | `{"courses":[{"course_id":{COURSE_ES},"active":true},{"course_id":{COURSE_ES},"active":false}]}` | **400** (curso repetido) | |
| 6 | admin | o mesmo | `{"courses":[{"course_id":{COURSE_ES},"active":true},{"course_id":{OTHER_COURSE},"active":true}]}` | **200**, dois cursos | |
| 7 | admin | `PATCH /api/admin/teachers/{PROF}/status` | `{"active":false}` | **200**; o login do professor dá **401** | |
| 8 | admin | o mesmo | `{"active":true}` | **200** | |
| 9 | admin | `GET /api/admin/teachers/999999` | — | **404** | |
| 10 | professor | `GET /api/admin/teachers` | — | **403** | |

## 5.4 Avaliadores externos

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | admin | `GET /api/admin/external-evaluators?search=avaliador` | — | **200** paginado, com `institution` e `editions`; anote `{AVAL}` | |
| 2 | admin | `GET /api/admin/external-evaluators?active=abc` | — | **400** | |
| 3 | admin | `GET /api/admin/external-evaluators?page=99` | — | **404** | |
| 4 | admin | `GET /api/admin/external-evaluators/{AVAL}` | — | **200** | |
| 5 | admin | `PATCH /api/admin/external-evaluators/{AVAL}` | `{"institution":"Empresa Nova"}` | **200** | |
| 6 | admin | `PATCH /api/admin/external-evaluators/{AVAL}/status` | `{"active":false}` | **200**; o login do avaliador dá **401** `invalid_credentials` | |
| 7 | admin | o mesmo | `{"active":true}` | **200**; faça login de novo com `aval.jar` | |
| 8 | admin | `GET /api/admin/external-evaluators/999999` | — | **404** | |
| 9 | aluno | `GET /api/admin/external-evaluators` | — | **403** | |

## 5.5 Equipes e desclassificação

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | admin | `GET /api/admin/teams?edition_id={EDITION}&status=ACTIVE` | — | **200** paginado: Equipe Seed, Sem Lider B e Sem Lider C, com `situation`, `member_count` e `project` | |
| 2 | admin | `GET /api/admin/teams?search=seed` | — | **200**, só a Equipe Seed | |
| 3 | admin | `GET /api/admin/teams?status=FOO` | — | **400** | |
| 4 | admin | `GET /api/admin/teams?page=99` | — | **404** | |
| 5 | admin | `GET /api/teams/{TEAM_A}` | — | **200** (admin vê qualquer equipe) | |
| 6 | admin | `POST /api/admin/teams/{TEAM_C}/disqualify` | `{}` | **400** `validation_error` em `reason` | |
| 7 | admin | o mesmo | `{"reason":"Plágio comprovado."}` | **200**, `status: DISQUALIFIED`, `disqualified_at` e `disqualified_by` preenchidos | |
| 8 | admin | repetir o passo 7 | — | **409** `team_already_disqualified` | |
| 9 | admin | `POST /api/admin/teams/999999/disqualify` | o do passo 7 | **404** | |
| 10 | aluno | `POST /api/admin/teams/{TEAM_B}/disqualify` | o do passo 7 | **403** | |

## 5.6 Chamados de suporte

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | aluno | `POST /api/support/tickets` | `{"title":"Nome errado","description":"Meu nome está sem acento."}` | **201**, `status: OPEN`, `priority: MEDIUM`. Anote `{TK}`. | |
| 2 | aluno | o mesmo | `{"title":"Sem descrição"}` | **400** | |
| 3 | avaliador | o mesmo | o do passo 1 | **403** (só aluno e professor abrem chamado) | |
| 4 | aluno | `GET /api/support/tickets?status=OPEN` | — | **200** paginado, só os chamados do aluno | |
| 5 | aluno | `GET /api/support/tickets?status=FOO` | — | **400** | |
| 6 | aluno | `GET /api/support/tickets?page=99` | — | **404** | |
| 7 | aluno | `GET /api/support/tickets/{TK}` | — | **200** | |
| 8 | admin | `GET /api/admin/support/tickets?search=professor` | — | **200**; anote o id do "Chamado do professor" como `{TK_PROF}` | |
| 9 | aluno | `GET /api/support/tickets/{TK_PROF}` | — | **404** (chamado de outro usuário) | |
| 10 | admin | `GET /api/admin/support/tickets?status=OPEN&priority=MEDIUM` | — | **200** | |
| 11 | admin | `GET /api/admin/support/tickets?priority=FOO` | — | **400** | |
| 12 | admin | `GET /api/admin/support/tickets?page=99` | — | **404** | |
| 13 | admin | `GET /api/admin/support/tickets/{TK}` | — | **200** | |
| 14 | admin | `GET /api/admin/support/tickets/00000000-0000-0000-0000-000000000000` | — | **404** | |
| 15 | aluno | `GET /api/admin/support/tickets` | — | **403** | |
| 16 | admin | `PATCH /api/admin/support/tickets/{TK}` | `{"status":"IN_PROGRESS","priority":"HIGH","assigned_to":1}` | **200** | |
| 17 | admin | o mesmo | `{"status":"CLOSED"}` | **400** `validation_error` em `support_response` | |
| 18 | admin | o mesmo | `{"status":"RESOLVED","support_response":"Nome corrigido."}` | **200**, `resolved_at` preenchido | |
| 19 | admin | o mesmo | `{"status":"OPEN"}` | **409** `invalid_status_transition` | |
| 20 | aluno | `GET /api/notifications?unread=true` | — | **200**, notificação `SYSTEM` da mudança no chamado | |

## 5.7 Fechamento: resultado, finalistas, pódio e homologação

Ordem da API: **calcular → finalistas → avaliação externa → pódio → homologar**. Rotas em `/api/admin/editions/{EDITION}/...`.

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | professor | `POST .../results/calculate` | — | **403** | |
| 2 | admin | `POST .../results/homologate` | — | **409** `results_not_calculated` | |
| 3 | admin | `POST .../finalists` | `{}` | **409** `results_not_calculated` | |
| 4 | admin | `POST .../results/calculate` | — | **200**: Projeto Seed com `final_score: "4.80"` e `course_rank: 1`; Projeto B em `excluded` com `PENDING_SCORE`; a Equipe C (desclassificada) não aparece | |
| 5 | admin | `POST .../results/homologate` | — | **409** `no_finalists` | |
| 6 | admin | `POST .../finalists` | `{"project_ids":[]}` | **400** `validation_error` | |
| 7 | admin | `POST .../finalists` | `{"project_ids":[999999]}` | **400** (fora do ranking) | |
| 8 | admin | `POST .../finalists` | `{}` | **200**, Projeto Seed com `finalist: true` | |
| 9 | admin | `POST .../results/homologate` | — | **409** `results_pending_scores` (o Projeto B ainda sem nota) | |
| 10 | terminal | `uv run python manage.py apply_zero_scores` | — | "Notas zero aplicadas: N." (N ≥ 2, as etapas do Projeto B) | |
| 11 | admin | `POST .../results/calculate` | — | **200**, Projeto B com `final_score: "0.00"`; o Projeto Seed continua finalista | |
| 12 | admin | `POST .../awards/calculate` | — | **200**, mas `award: null` (ainda sem avaliação externa) | |
| 13 | admin | `POST .../results/homologate` | — | **409** `awards_not_calculated` | |
| 14 | admin | `PUT .../final-form` e depois `POST .../final-form/publish` | `{"title":"Final","questions":[{"order":1,"prompt":"Pitch","kind":"SCORE","max_score":"10.00"}]}` | **200** e **200**; anote o id da pergunta `{Q}` | |
| 15 | avaliador | `PUT /api/evaluator/finalists/{PROJECT_A}/final-evaluation` | `{"status":"EVALUATED","answers":[{"question_id":{Q},"value":"8.50","text":null}]}` | **200** | |
| 16 | admin | `POST .../awards/calculate` | — | **200**, Projeto Seed com `category_rank: 1` e `award: 1` | |
| 17 | admin | `POST .../results/homologate` | — | **200**, `approved_at` preenchido | |
| 18 | admin | `POST .../results/calculate` | — | **409** `results_already_approved` | |
| 19 | aluno | `GET /api/notifications?unread=true` | — | **200**, notificação de resultado homologado | |
| 20 | sem login | `GET /api/public/editions/{EDITION}/winners` | — | **404** (a edição ainda não está encerrada) | |

## 5.8 Encerrar a edição

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | admin | `POST /api/admin/editions` e depois `POST /api/admin/editions/{nova}/close` | `{"year":2032,"semester":1}` e `{"confirm":true}` | **201** e **409** `edition_not_published` | |
| 2 | admin | `POST /api/admin/editions/{EDITION}/close` | `{"confirm":false}` | **400** `validation_error` | |
| 3 | admin | o mesmo | `{}` | **400** | |
| 4 | aluno | o mesmo | `{"confirm":true}` | **403** | |
| 5 | admin | o mesmo | `{"confirm":true}` | **200**, `status: CLOSED`, `closed_at` preenchido | |
| 6 | admin | repetir o passo 5 | — | **409** `edition_already_closed` | |
| 7 | admin | `POST /api/admin/editions/{EDITION}/categories` | `{"name":"Depois do fim"}` | **409** `edition_closed` | |
| 8 | admin | `POST /api/admin/teams/{TEAM_B}/disqualify` | `{"reason":"x"}` | **409** `edition_closed` | |
| 9 | sem login | `GET /api/public/editions` | — | **200**, a edição com `closed_at` | |
| 10 | sem login | `GET /api/public/editions/{EDITION}/winners` | — | **200**, Projeto Seed com `award: 1`, agrupável por categoria | |
| 11 | sem login | `GET /api/public/editions/999999/winners` | — | **404** | |
| 12 | sem login | `login aval.jar avaliador@empresa.local '<senha>'` | — | **403** `reviewer_not_in_current_edition` (não há mais edição publicada) | |

## Casos obrigatórios (resumo)

| Caso | Onde |
|---|---|
| Perfil errado (403) | 5.2.4, 5.3.10, 5.4.9, 5.5.10, 5.6.3, 5.6.15, 5.7.1, 5.8.4 |
| Inexistente / de outro usuário (404) | 5.2.6, 5.2.17, 5.3.9, 5.4.8, 5.5.9, 5.6.9, 5.6.14, 5.8.11 |
| Corpo inválido (400) | 5.1.5–6, 5.2.9–10, 5.2.15, 5.3.5, 5.5.6, 5.6.2, 5.6.17, 5.7.6–7, 5.8.2–3 |
| Regra de negócio (409) | 5.2.8, 5.5.8, 5.6.19, 5.7.2–3, 5.7.5, 5.7.9, 5.7.13, 5.7.18, 5.8.1, 5.8.6–8 |
| Filtro inválido (400) | 5.2.2, 5.3.2, 5.4.2, 5.5.3, 5.6.5, 5.6.11 |
| Página inexistente (404) | 5.2.3, 5.3.3, 5.4.3, 5.5.4, 5.6.6, 5.6.12 |

## Observações do testador

