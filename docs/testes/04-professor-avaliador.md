# Roteiro 04 — Professor e avaliador externo

| | |
|---|---|
| **Responsável** | |
| **Data / commit testado** | |
| **Perfis** | TEACHER, EXTERNAL_REVIEWER, ADMIN (retificação, formulário final, avaliadores); STUDENT só nos 403 |
| **Pré-requisitos** | Ambiente do README com `seed_users` e `cenario.py` **padrão**. A "Equipe Seed" tem versão enviada na **etapa encerrada** (envio fechado, avaliação aberta), o projeto dela já é **finalista**, o avaliador seed está vinculado à edição e a "Equipe Sem Lider B" tem pedido de liderança pendente. O professor seed é do curso Engenharia de Software. |
| **Login** | `prof.jar` (professor seed), `aval.jar` (avaliador seed), `admin.jar`, `aluno.jar` com a senha do `seed_users`; `np.jar` = `novoprof@professor.desafiox.local` com `TesteForte!2026x`. |

Cole aqui a saída do cenário:

```
```

Coluna **Resultado**: `ok`, `falhou #N` ou `bloqueado`.

## 4.1 Autocadastro do professor

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | novoprof | `POST /api/auth/teachers` | `{"course_ids":[999999]}` | **400** (curso inexistente) | |
| 2 | novoprof | `POST /api/auth/teachers` | `{"course_ids":[{OTHER_COURSE}]}` | **201**, `{"teacher": {"user_id": ...}}` | |
| 3 | novoprof | repetir o passo 2 | — | **409** `teacher_profile_exists` | |
| 4 | aluno | `POST /api/auth/teachers` | o do passo 2 | **403** | |
| 5 | novoprof | `GET /api/projects/{PROJECT_A}/stages/{STAGE_ENCERRADA}/evaluation` | — | **403** `teacher_not_in_course` | |

## 4.2 Painel do professor

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | professor | `GET /api/teacher/projects` | — | **200** paginado; uma linha por projeto e etapa pontuada, com `deliverable_status` | |
| 2 | professor | `GET /api/teacher/projects?pending_only=true` | — | **200**; o Projeto Seed na etapa encerrada com `SUBMITTED` | |
| 3 | professor | `GET /api/teacher/projects?stage_id=abc` | — | **400** `validation_error` | |
| 4 | professor | `GET /api/teacher/projects?page=99` | — | **404** | |
| 5 | aluno | `GET /api/teacher/projects` | — | **403** | |

## 4.3 Avaliar a entrega

`/api/projects/{PROJECT_A}/stages/{STAGE_ENCERRADA}/evaluation`, salvo indicação.

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | professor | `GET .../evaluation` | — | **200**, `criteria` com `stage_criterion_id = {STAGE_CRITERION_ENCERRADA}` e `max_score: "10.00"`, `evaluation: null` | |
| 2 | professor | `PUT .../evaluation` | `{"status":"DRAFT","comment":"Rascunho","items":[{"stage_criterion_id":{STAGE_CRITERION_ENCERRADA},"points":"7.00"}]}` | **200**, `status: DRAFT`. Anote o `id` como `{EVAL}`. | |
| 3 | admin | `POST /api/admin/evaluations/{EVAL}/rectifications` | `{"stage_criterion_id":{STAGE_CRITERION_ENCERRADA},"new_points":"9.00","reason":"x"}` | **400** (só avaliação finalizada) | |
| 4 | professor | `PUT .../evaluation` | itens com `"points":"11.00"` | **400** `points_out_of_range` | |
| 5 | professor | `PUT .../evaluation` | itens com `"stage_criterion_id":{STAGE_CRITERION_ABERTA}` | **400** (critério de outra etapa) | |
| 6 | professor | `PUT .../evaluation` | `{"status":"FINALIZED","items":[]}` | **400** (finalizar exige todos os critérios) | |
| 7 | professor | `PUT /api/projects/{PROJECT_A}/stages/{STAGE_ABERTA}/evaluation` | `{"status":"FINALIZED","items":[{"stage_criterion_id":{STAGE_CRITERION_ABERTA},"points":"8.00"}]}` | **400** `validation_error` (prazo de entrega da equipe ainda aberto) | |
| 8 | professor | `PUT /api/projects/{PROJECT_B}/stages/{STAGE_ENCERRADA}/evaluation` | passo 2 com `FINALIZED` | **400** (sem entrega válida) | |
| 9 | aluno | `PUT .../evaluation` | passo 2 | **403** | |
| 10 | professor | `PUT .../evaluation` | `{"status":"FINALIZED","comment":"Bem estruturado.","items":[{"stage_criterion_id":{STAGE_CRITERION_ENCERRADA},"points":"8.00","comment":"Boa base."}]}` | **200**, `status: FINALIZED`, `finalized_at` preenchido, `total: "8.00"` | |
| 11 | professor | passo 2 de novo | — | **400** `validation_error` ("A avaliação já foi finalizada.") | |
| 12 | aluno | `GET /api/projects/{PROJECT_A}/scores` | — | **200**; etapa encerrada com `DEFINITIVE` e `value: "2.40"` (8/10 × 3,00) e o feedback | |
| 13 | professor | `GET /api/projects/{PROJECT_A}/scores` | — | **200** | |

## 4.4 Retificação de nota (admin)

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | professor | `POST /api/admin/evaluations/{EVAL}/rectifications` | `{"stage_criterion_id":{STAGE_CRITERION_ENCERRADA},"new_points":"9.00","reason":"Erro de digitação."}` | **403** | |
| 2 | admin | o mesmo | sem `reason` | **400** `validation_error` | |
| 3 | admin | o mesmo | `"new_points":"8.00"` (igual ao atual) | **400** | |
| 4 | admin | o mesmo | `"new_points":"11.00"` | **400** | |
| 5 | admin | o mesmo | `"stage_criterion_id":{STAGE_CRITERION_ABERTA}` | **400** (critério não pontuado nesta avaliação) | |
| 6 | admin | `POST /api/admin/evaluations/999999/rectifications` | o do passo 1 | **404** | |
| 7 | admin | `POST /api/admin/evaluations/{EVAL}/rectifications` | o do passo 1 | **201**, `previous_points: "8.00"`, `new_points: "9.00"`, `stage_score.value: "2.70"` | |
| 8 | aluno | `GET /api/projects/{PROJECT_A}/scores` | — | **200**, a etapa com `2.70` | |

## 4.5 Solicitações de liderança

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | professor | `GET /api/teacher/leadership-requests?status=PENDING` | — | **200** **paginado** (`count`, `results`), com o pedido da Equipe Sem Lider B | |
| 2 | professor | `GET /api/teacher/leadership-requests?status=FOO` | — | **400** | |
| 3 | professor | `GET /api/teacher/leadership-requests?page=99` | — | **404** | |
| 4 | aluno | `GET /api/teacher/leadership-requests` | — | **403** | |
| 5 | novoprof | `GET /api/teacher/leadership-requests` | — | **200**, sem o pedido (curso diferente) | |
| 6 | novoprof | `POST /api/leadership-requests/{LEADERSHIP_REQUEST_B}/decide` | `{"status":"APPROVED","decision_justification":"ok"}` | **403** ou **404** (curso diferente; anote qual veio) | |
| 7 | professor | `POST /api/leadership-requests/{LEADERSHIP_REQUEST_B}/decide` | `{"status":"APPROVED"}` | **400** `validation_error` em `decision_justification` | |
| 8 | professor | o mesmo | `{"status":"APPROVED","decision_justification":"Integrante ativo."}` | **200**, `status: APPROVED`, `teacher` preenchido | |
| 9 | professor | repetir o passo 8 | — | **409** `leadership_request_not_pending` | |
| 10 | professor | `POST /api/leadership-requests/999999/decide` | o do passo 8 | **404** | |

## 4.6 Observações sobre integrantes

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | professor | `GET /api/teams/{TEAM_A}/member-notes` | — | **200**, observação sobre Membro1 com `text` e `author` | |
| 2 | admin | `GET /api/teams/{TEAM_A}/member-notes` | — | **200** | |
| 3 | aluno | `GET /api/teams/{TEAM_A}/member-notes` | — | **403** (o líder não consulta) | |
| 4 | novoprof | `GET /api/teams/{TEAM_A}/member-notes` | — | **403** ou **404** (anote qual veio) | |

## 4.7 Avaliadores externos (admin)

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | aluno | `POST /api/auth/external-evaluators` | `{"name":"Ana Ribeiro","email":"ana@parceira.com","password":"SenhaInicial#2026","institution":"Parceira"}` | **403** | |
| 2 | admin | o mesmo | sem `password` | **400** `validation_error` | |
| 3 | admin | o mesmo | o do passo 1 | **201**, `{"external_evaluator": {"user_id", "email"}}`, sem senha. Anote `{EXT}`. | |
| 4 | admin | repetir o passo 3 | — | **409** `email_taken` | |
| 5 | sem login | `login ext.jar ana@parceira.com 'SenhaInicial#2026'` | — | **403** `reviewer_not_in_current_edition` (ainda sem vínculo) | |
| 6 | admin | `GET /api/admin/editions/{EDITION}/evaluators` | — | **200**, com o avaliador seed | |
| 7 | admin | `POST /api/admin/editions/{EDITION}/evaluators` | `{"evaluator_id":{EXT},"course_id":{COURSE_ES}}` | **201**, `course` preenchido | |
| 8 | admin | repetir o passo 7 | — | **409** `evaluator_already_linked` | |
| 9 | admin | `POST /api/admin/editions/999999/evaluators` | o do passo 7 | **404** | |
| 10 | admin | `PATCH /api/admin/editions/{EDITION}/evaluators/{EXT}` | `{"course_id":null}` | **200**, `course: null` (todos os cursos) | |
| 11 | sem login | refazer o login do passo 5 | — | **200**, `role: EXTERNAL_REVIEWER` | |

## 4.8 Formulário da etapa final (admin)

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | admin | `GET /api/admin/editions/{EDITION}/final-form` | — | **404** (ainda não existe) | |
| 2 | avaliador | `GET /api/evaluator/finalists` | — | **409** `final_form_not_published` | |
| 3 | admin | `PUT /api/admin/editions/{EDITION}/final-form` | `{"title":"Apresentação Final","questions":[]}` | **200**, sem perguntas | |
| 4 | admin | `POST /api/admin/editions/{EDITION}/final-form/publish` | — | **409** `final_form_empty` | |
| 5 | admin | `PUT .../final-form` | `{"questions":[{"order":1,"prompt":"Pitch","kind":"SCORE"}]}` | **400** (SCORE exige `max_score`) | |
| 6 | admin | `PUT .../final-form` | `{"questions":[{"order":1,"prompt":"Conceito","kind":"CONCEPT","max_score":"10.00"}]}` | **400** (CONCEPT exige `max_score` nulo) | |
| 7 | admin | `PUT .../final-form` | duas perguntas com `"order":1` | **400** | |
| 8 | admin | `PUT .../final-form` | `{"title":"Apresentação Final","questions":[{"order":1,"prompt":"Clareza do pitch","kind":"SCORE","max_score":"10.00"},{"order":2,"prompt":"Comentário da banca","kind":"TEXT","max_score":null}]}` | **200**, `published: false`, perguntas com `id`. Anote `{Q_SCORE}` e `{Q_TEXT}`. | |
| 9 | aluno | `PUT .../final-form` | o do passo 8 | **403** | |
| 10 | admin | `POST .../final-form/publish` | — | **200**, `published: true` | |
| 11 | admin | repetir o passo 10 | — | **409** `final_form_already_published` | |
| 12 | admin | `GET /api/admin/editions/{EDITION}/final-form` | — | **200** | |

## 4.9 Avaliação final (avaliador externo)

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | avaliador | `GET /api/evaluator/finalists` | — | **200** paginado, com o Projeto Seed e **sem** notas das etapas | |
| 2 | avaliador | `GET /api/evaluator/finalists?category_id=abc` | — | **400** | |
| 3 | avaliador | `GET /api/evaluator/finalists?page=99` | — | **404** | |
| 4 | professor | `GET /api/evaluator/finalists` | — | **403** | |
| 5 | avaliador | `GET /api/evaluator/finalists/{PROJECT_A}/final-evaluation` | — | **200**, o formulário e a avaliação ainda vazia | |
| 6 | avaliador | `GET /api/evaluator/finalists/{PROJECT_B}/final-evaluation` | — | **404** (não é finalista) | |
| 7 | avaliador | `PUT /api/evaluator/finalists/{PROJECT_A}/final-evaluation` | `{"status":"PENDING","answers":[{"question_id":{Q_SCORE},"value":"8.50","text":null}]}` | **200**, `status: PENDING` | |
| 8 | avaliador | o mesmo | `"value":"11.00"` | **400** | |
| 9 | avaliador | o mesmo | `{"status":"EVALUATED","answers":[{"question_id":{Q_SCORE},"value":"8.50","text":null}]}` | **400** (falta a resposta TEXT) | |
| 10 | avaliador | o mesmo | `{"status":"EVALUATED","comment":"Objetiva.","answers":[{"question_id":{Q_SCORE},"value":"8.50","text":null},{"question_id":{Q_TEXT},"value":null,"text":"Boa apresentação."}]}` | **200**, `status: EVALUATED`, `finalized_at` preenchido | |
| 11 | avaliador | repetir o passo 10 | — | **409** `final_evaluation_already_finalized` | |
| 12 | admin | `PUT /api/admin/editions/{EDITION}/final-form` | o do passo 4.8.8 | **409** `final_form_has_answers` | |
| 13 | Ana (`ext.jar`) | `GET /api/evaluator/finalists` | — | **200**, também vê o Projeto Seed | |

## Casos obrigatórios (resumo)

| Caso | Onde |
|---|---|
| Perfil errado (403) | 4.1.4, 4.2.5, 4.3.9, 4.4.1, 4.5.4, 4.6.3, 4.7.1, 4.8.9, 4.9.4 |
| Outra equipe / inexistente (403/404) | 4.1.5, 4.4.6, 4.5.6, 4.5.10, 4.6.4, 4.7.9, 4.8.1, 4.9.6 |
| Corpo inválido (400) | 4.1.1, 4.3.4–6, 4.4.2–5, 4.5.7, 4.7.2, 4.8.5–7, 4.9.8–9 |
| Regra de negócio (409, ou 400 pelo contrato) | 4.1.3, 4.3.3, 4.3.7–8, 4.3.11, 4.5.9, 4.7.4–5, 4.7.8, 4.8.2, 4.8.4, 4.8.11, 4.9.11–12 |
| Filtro inválido (400) | 4.2.3, 4.5.2, 4.9.2 |
| Página inexistente (404) | 4.2.4, 4.5.3, 4.9.3 |

## Observações do testador

