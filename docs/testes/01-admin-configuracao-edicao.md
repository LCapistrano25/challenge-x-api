# Roteiro 01 — Admin: configuração da edição

| | |
|---|---|
| **Responsável** | |
| **Data / commit testado** | |
| **Perfis** | ADMIN; STUDENT só nos casos de 403 |
| **Pré-requisitos** | Ambiente do README com `seed_users`. **Não rode o `cenario.py`**: este roteiro cria e publica a própria edição (ver divergência 1 do README). |
| **Login** | `login admin.jar admin@desafiox.local '<senha do seed>'` e `login aluno.jar aluno@aluno.desafiox.local '<senha do seed>'` |

Anote os IDs que as respostas devolverem; os passos seguintes usam `{CURSO_ES}`, `{ED}`, `{ST_IDEIA}` etc.

Coluna **Resultado**: `ok`, `falhou #N` ou `bloqueado`.

## 1.1 Catálogos públicos e cursos

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | sem login | `GET /api/courses` | — | **200**, lista `{id, name}` só de cursos ativos. Anote o id de Engenharia de Software como `{CURSO_ES}`. | |
| 2 | sem login | `GET /api/sdgs` | — | **200**, as ODS ativas com `id, number, title, description, icon` (a base local traz só algumas: 1, 2, 3, 9 e 16) | |
| 3 | sem login | `GET /api/admin/courses` | — | **401** `not_authenticated` | |
| 4 | aluno | `GET /api/admin/courses` | — | **403** `permission_denied` | |
| 5 | admin | `GET /api/admin/courses?search=engenharia&active=true` | — | **200**, lista com `term_count`, `active`, `created_at` | |
| 6 | admin | `GET /api/admin/courses?active=abc` | — | **400** `validation_error`, `details.active` | |
| 7 | admin | `POST /api/admin/courses` | `{"name":"Curso Teste","term_count":8}` | **201**, `active: true`. Anote `{CURSO_T}`. | |
| 8 | admin | `POST /api/admin/courses` | `{"name":"curso teste","term_count":8}` | **409** `course_name_taken` | |
| 9 | admin | `POST /api/admin/courses` | `{"name":"Curso Nove","term_count":9}` | **400** `validation_error` (`term_count` só 8 ou 10) | |
| 10 | admin | `POST /api/admin/courses` | `{"name":"","term_count":8}` | **400** `validation_error` em `name` | |
| 11 | admin | `POST /api/admin/courses` | `{"name": ` (JSON quebrado) | **400** `parse_error` | |
| 12 | admin | `PATCH /api/admin/courses/{CURSO_T}` | `{"term_count":10}` | **200**, `term_count: 10` | |
| 13 | admin | `PATCH /api/admin/courses/999999` | `{"term_count":10}` | **404** `not_found` | |
| 14 | admin | `DELETE /api/admin/courses/{CURSO_ES}` | — | **409** `course_in_use` (o aluno seed é desse curso) | |
| 15 | admin | `POST /api/admin/courses` | `{"name":"Curso Inativo","term_count":8,"active":false}` | **201**. Anote `{CURSO_INATIVO}`. | |
| 16 | admin | `DELETE /api/admin/courses/{CURSO_T}` | — | **204** sem corpo; o curso some de `GET /api/admin/courses` | |

## 1.2 ODS

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | admin | `GET /api/admin/sdgs?active=true` | — | **200**, cada ODS com `created_at` e `updated_at`. Anote o id da ODS 9 como `{ODS9}`. | |
| 2 | admin | `GET /api/admin/sdgs?active=talvez` | — | **400** `validation_error` | |
| 3 | admin | `POST /api/admin/sdgs` | `{"number":9,"title":"Duplicada"}` | **409** `sdg_number_taken` | |
| 4 | admin | `POST /api/admin/sdgs` | `{"number":18,"title":"Fora da faixa"}` | **400** `validation_error` em `number` (1 a 17) | |
| 5 | admin | `POST /api/admin/sdgs` | `{"number":17,"title":"Parcerias e Meios de Implementação","icon":"ods-17.svg"}` | **201**. Anote `{ODS17}`. | |
| 6 | admin | `POST /api/admin/sdgs` e depois `DELETE /api/admin/sdgs/{id criado}` | `{"number":10,"title":"Redução das Desigualdades"}` | **201** e **204** (ODS sem uso) | |
| 7 | admin | `PATCH /api/admin/sdgs/{ODS17}` | `{"active":false}` | **200**, `active: false`; a ODS some de `GET /api/sdgs` | |
| 8 | aluno | `POST /api/admin/sdgs` | `{"number":17,"title":"x"}` | **403** | |

## 1.3 Domínios de e-mail

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | admin | `GET /api/admin/email-domains?role=STUDENT` | — | **200**, inclui `aluno.desafiox.local` | |
| 2 | admin | `GET /api/admin/email-domains?role=ADMIN` | — | **400** `validation_error` | |
| 3 | admin | `POST /api/admin/email-domains` | `{"name":" Teste.EDU.br ","role":"STUDENT"}` | **201**, `name` salvo como `teste.edu.br`. Anote `{DOM}`. | |
| 4 | admin | `POST /api/admin/email-domains` | `{"name":"TESTE.edu.br","role":"TEACHER"}` | **409** `email_domain_taken` | |
| 5 | admin | `POST /api/admin/email-domains` | `{"name":"nao e dominio","role":"STUDENT"}` | **400** `validation_error` em `name` | |
| 6 | admin | `POST /api/admin/email-domains` | `{"name":"adm.edu.br","role":"ADMIN"}` | **400** `validation_error` em `role` | |
| 7 | admin | `PATCH /api/admin/email-domains/{DOM}` | `{"active":false}` | **200**, `active: false` | |

## 1.4 Edição

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | admin | `POST /api/admin/editions` | `{"year":2031,"semester":1,"name":"Desafio X 2031/1"}` | **201**, `status: SETUP`, `min_members: 3`, `max_members: 5`. Anote `{ED}`. | |
| 2 | admin | `POST /api/admin/editions` | `{"year":2031,"semester":1}` | **409** `edition_exists` | |
| 3 | admin | `POST /api/admin/editions` | `{"year":1999,"semester":1}` | **400** `validation_error` (ano de 2000 a 2100) | |
| 4 | admin | `POST /api/admin/editions` | `{"year":2032,"semester":3}` | **400** `validation_error` em `semester` | |
| 5 | admin | `GET /api/admin/editions` | — | **200**, inclui `{ED}` | |
| 6 | admin | `GET /api/admin/editions/{ED}` | — | **200** | |
| 7 | admin | `GET /api/admin/editions/999999` | — | **404** | |
| 8 | admin | `PATCH /api/admin/editions/{ED}` | `{"min_members":2,"max_members":4}` | **200** com os novos limites | |
| 9 | admin | `PATCH /api/admin/editions/{ED}` | `{"min_members":5,"max_members":4}` | **400** `validation_error` | |
| 10 | admin | `PATCH /api/admin/editions/{ED}` | `{"max_members":21}` | **400** `validation_error` (máximo 20) | |
| 11 | aluno | `GET /api/admin/editions` | — | **403** | |

## 1.5 Etapas

Datas no futuro, sempre com fuso. As etapas pontuadas precisam somar 10,00 para publicar.

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | admin | `POST /api/admin/editions/{ED}/stages` | `{"order":1,"name":"Formação","kind":"FORMATION","starts_at":"2031-02-01T00:00:00Z","ends_at":"2031-02-20T23:59:00Z","scored":false}` | **201**, `max_score: null`. Anote `{ST_FORM}`. | |
| 2 | admin | `POST /api/admin/editions/{ED}/stages` | `{"order":2,"name":"Ideia","kind":"SUBMISSION","starts_at":"2031-03-01T00:00:00Z","ends_at":"2031-03-20T23:59:00Z","evaluation_ends_at":"2031-03-27T23:59:00Z","scored":true,"max_score":"4.00","min_evaluations":1,"submission_fields":[{"kind":"LINK","label":"Repositório","required":true}]}` | **201**, `submission_fields` com `id`. Anote `{ST_IDEIA}`. | |
| 3 | admin | `POST /api/admin/editions/{ED}/stages` | `{"order":3,"name":"Protótipo","kind":"SUBMISSION","starts_at":"2031-04-01T00:00:00Z","ends_at":"2031-04-20T23:59:00Z","evaluation_ends_at":"2031-04-27T23:59:00Z","scored":true,"max_score":"6.00","submission_fields":[{"kind":"FILE","label":"Relatório","required":true,"formats":"pdf","max_size_mb":10},{"kind":"CANVAS","label":"Canvas","required":false}]}` | **201**. Anote `{ST_PROT}`. | |
| 4 | admin | `POST /api/admin/editions/{ED}/stages` | o corpo do passo 2 de novo | **409** `stage_position_taken` | |
| 5 | admin | `POST /api/admin/editions/{ED}/stages` | passo 2 com `"order":4` e `"ends_at":"2031-02-01T00:00:00Z"` | **400** `validation_error` (fim antes do início) | |
| 6 | admin | `POST /api/admin/editions/{ED}/stages` | passo 2 com `"order":4` sem `max_score` | **400** `validation_error` (pontuada exige `max_score`) | |
| 7 | admin | `POST /api/admin/editions/{ED}/stages` | passo 2 com `"order":4` e campo `{"kind":"LINK","label":"x","formats":"pdf"}` | **400** (`formats` só vale para FILE) | |
| 8 | admin | `GET /api/admin/editions/{ED}/stages` | — | **200**, três etapas em ordem | |
| 9 | admin | `GET /api/admin/stages/{ST_IDEIA}` | — | **200** com os campos de entrega | |
| 10 | admin | `PATCH /api/admin/stages/{ST_IDEIA}` | `{"ends_at":"2031-03-22T23:59:00Z"}` | **200**, novo `ends_at` | |
| 11 | admin | `GET /api/admin/stages/999999` | — | **404** | |

## 1.6 Critérios e critérios da etapa

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | admin | `POST /api/admin/editions/{ED}/criteria` | `{"name":"Inovação","rubric":"Originalidade","tiebreak_order":1}` | **201**. Anote `{CR_INOV}`. | |
| 2 | admin | `POST /api/admin/editions/{ED}/criteria` | `{"name":"Viabilidade","tiebreak_order":2}` | **201**. Anote `{CR_VIAB}`. | |
| 3 | admin | `POST /api/admin/editions/{ED}/criteria` | `{"name":"inovação"}` | **409** `criterion_name_taken` | |
| 4 | admin | `POST /api/admin/editions/{ED}/criteria` | `{"name":"Impacto","tiebreak_order":1}` | **409** `tiebreak_order_taken` | |
| 5 | admin | `POST /api/admin/editions/{ED}/criteria` | `{"name":"Apagar"}` | **201**. Anote `{CR_APAGAR}`. | |
| 6 | admin | `GET /api/admin/editions/{ED}/criteria` | — | **200**, três critérios | |
| 7 | admin | `PATCH /api/admin/criteria/{CR_VIAB}` | `{"rubric":"Custo e prazo","tiebreak_order":null}` | **200**, `tiebreak_order: null` | |
| 8 | admin | `DELETE /api/admin/criteria/{CR_APAGAR}` | — | **204** | |
| 9 | admin | `PUT /api/admin/stages/{ST_IDEIA}/criteria` | `{"items":[{"criterion_id":{CR_INOV},"max_score":"10.00"},{"criterion_id":{CR_VIAB},"max_score":"10.00"}]}` | **200**, dois itens; a soma **não** precisa bater com o valor da etapa (D-02) | |
| 10 | admin | `PUT /api/admin/stages/{ST_PROT}/criteria` | `{"items":[{"criterion_id":{CR_INOV},"max_score":"10.00"}]}` | **200** | |
| 11 | admin | `PUT /api/admin/stages/{ST_FORM}/criteria` | `{"items":[{"criterion_id":{CR_INOV},"max_score":"10.00"}]}` | **400** `validation_error` (etapa não pontuada) | |
| 12 | admin | `PUT /api/admin/stages/{ST_IDEIA}/criteria` | `{"items":[{"criterion_id":{CR_INOV},"max_score":10}]}` | **400** (`max_score` vai como texto) | |
| 13 | admin | `GET /api/admin/stages/{ST_IDEIA}/criteria` | — | **200**, `{id, criterion: {id, name}, max_score}` | |
| 14 | admin | `DELETE /api/admin/criteria/{CR_INOV}` | — | **409** `criterion_linked_to_stage` | |

Fora deste roteiro: `409 criterion_in_use_by_evaluations` precisa de avaliação de professor, que só existe depois da publicação (o roteiro 4 tem esse dado).

## 1.7 Categorias

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | admin | `POST /api/admin/editions/{ED}/categories` | `{"name":"Protótipos e Artefatos","description":"Categoria A"}` | **201**. Anote `{CAT}`. | |
| 2 | admin | `POST /api/admin/editions/{ED}/categories` | `{"name":"protótipos e artefatos"}` | **409** `category_name_taken` | |
| 3 | admin | `POST /api/admin/editions/{ED}/categories` | `{"name":"Apagar"}` | **201**. Anote `{CAT_APAGAR}`. | |
| 4 | admin | `PATCH /api/admin/categories/{CAT}` | `{"description":"Revisada"}` | **200** | |
| 5 | admin | `DELETE /api/admin/categories/{CAT_APAGAR}` | — | **204** | |
| 6 | admin | `GET /api/admin/editions/{ED}/categories` | — | **200**, só `{CAT}` | |
| 7 | admin | `POST /api/admin/editions/{ED}/categories` | `{"name":"X","extra":1}` | **400** (campo desconhecido) | |

## 1.8 ODS da edição e desafios

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | admin | `GET /api/admin/editions/{ED}/sdgs` | — | **200**, lista vazia | |
| 2 | admin | `PUT /api/admin/editions/{ED}/sdgs` | `{"sdg_ids":[{ODS17}]}` | **400** `validation_error` (ODS inativa, passo 1.2.7) | |
| 3 | admin | `PUT /api/admin/editions/{ED}/sdgs` | `{"sdg_ids":[{ODS9}]}` | **200**, só a ODS 9 | |
| 4 | admin | `POST /api/admin/editions/{ED}/challenges` | `{"course_id":{CURSO_ES},"sdg_id":{ODS9},"description":"Reduzir o desperdício de água no campus."}` | **201**, `course` e `sdg` como objetos. Anote `{CH}`. | |
| 5 | admin | `POST /api/admin/editions/{ED}/challenges` | passo 4 com outra ODS, não habilitada | **400** `validation_error` em `sdg_id` | |
| 6 | admin | `POST /api/admin/editions/{ED}/challenges` | passo 4 com `"course_id":{CURSO_INATIVO}` | **400** `validation_error` em `course_id` | |
| 7 | admin | `GET /api/admin/editions/{ED}/challenges?course_id={CURSO_ES}&active=true` | — | **200**, só `{CH}` | |
| 8 | admin | `GET /api/admin/editions/{ED}/challenges?course_id=abc` | — | **400** `validation_error` | |
| 9 | admin | `PATCH /api/admin/challenges/{CH}` | `{"description":"Texto revisado."}` | **200** | |
| 10 | admin | `PUT /api/admin/editions/{ED}/sdgs` | `{"sdg_ids":[]}` | **409** `sdg_in_use` (a ODS 9 tem desafio) | |
| 11 | admin | `DELETE /api/admin/sdgs/{ODS9}` | — | **409** `sdg_in_use` (em 27/11 voltou **500**: divergência 6 do README) | |

## 1.9 Publicar o edital

Gere um PDF de teste: `printf '%%PDF-1.4\n%%%%EOF\n' > edital.pdf`.

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | admin | `POST /api/admin/editions/{ED}/publish` (multipart, use `upload`) | sem `notice_file` | **400** `validation_error` em `notice_file` | |
| 2 | admin | `PUT /api/admin/stages/{ST_PROT}/criteria`, depois publicar | `{"items":[]}` e depois `-F 'notice_file=@edital.pdf;type=application/pdf'` | **409** `publication_requirements_not_met`, com `details.stage_criteria` | |
| 3 | admin | refazer 1.6.10 e publicar de novo | `-F 'notice_file=@edital.pdf;type=application/pdf'` | **200**, `status: PUBLISHED`, `published_at` e `regulation_url` preenchidos | |
| 4 | admin | `POST /api/admin/editions/{ED}/publish` | o mesmo arquivo | **409** `edition_not_in_setup` | |
| 5 | admin | `PATCH /api/admin/editions/{ED}` | `{"min_members":3}` | **409** `edition_published` | |
| 6 | admin | `PATCH /api/admin/stages/{ST_IDEIA}` | `{"name":"Ideia 2"}` | **409** `edition_published` | |
| 7 | admin | `PUT /api/admin/stages/{ST_IDEIA}/criteria` | o corpo de 1.6.9 | **409** `edition_published` | |
| 8 | admin | `POST /api/admin/editions/{ED}/criteria` | `{"name":"Depois da publicação"}` | **201** (critério continua editável com a edição publicada) | |

## 1.10 Páginas públicas da edição

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | sem login | `GET /api/public/editions/current` | — | **200**, `edition.id = {ED}`, `regulation_url`, `stages` com `phase_status` | |
| 2 | sem login | `GET /api/public/editions/{ED}/regulation/{token}` (o link exato de `regulation_url`) | — | **200**, o PDF enviado | |
| 3 | sem login | `GET /api/public/editions/{ED}/regulation/00000000-0000-0000-0000-000000000000` | — | **404** | |

## Casos obrigatórios (resumo)

| Caso | Onde |
|---|---|
| Perfil errado (403) | 1.1.4, 1.2.8, 1.4.11 |
| Inexistente (404) | 1.1.13, 1.4.7, 1.5.11, 1.10.3 |
| Corpo inválido (400) | 1.1.9–11, 1.4.3–4, 1.5.5–7, 1.7.7 |
| Regra de negócio (409) | 1.1.8, 1.1.14, 1.4.2, 1.5.4, 1.6.3–4, 1.6.14, 1.8.10, 1.9.2, 1.9.4–7 |
| Filtro inválido (400) | 1.1.6, 1.2.2, 1.3.2, 1.8.8 |
| Página inexistente (404) | Não se aplica: nenhuma lista deste fluxo é paginada |

## Observações do testador

