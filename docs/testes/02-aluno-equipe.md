# Roteiro 02 — Aluno: equipe

| | |
|---|---|
| **Responsável** | |
| **Data / commit testado** | |
| **Perfis** | STUDENT (vários alunos); TEACHER só nos casos de 403 |
| **Pré-requisitos** | Ambiente do README com `seed_users` e `cenario.py` **padrão**: edição publicada com a formação aberta, a "Equipe Seed" (aluno seed líder + `membro1` e `membro2`), convite pendente para `livre4`, pedido de entrada pendente de `livre3`, equipes B e C sem líder e os alunos `livre1` a `livre6` sem equipe. |
| **Login** | Alunos do seed com a senha do `seed_users`; alunos do cenário com `TesteForte!2026x`. Um `.jar` por aluno, por exemplo `login l1.jar livre1@aluno.desafiox.local 'TesteForte!2026x'`. |

Cole aqui a saída do cenário (os passos usam `{TEAM_A}`, `{LIVRE2_STUDENT_ID}` etc.):

```
```

Coluna **Resultado**: `ok`, `falhou #N` ou `bloqueado`. Siga a ordem: os passos mudam a composição das equipes.

## 2.1 Sessão e autocadastro

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | novoaluno | `GET /api/auth/me` | — | **200**, `role: STUDENT` | |
| 2 | novoaluno | `POST /api/auth/students` | `{"course_id":{COURSE_ES},"registration_number":"SEED001","term":3}` | **409** `registration_number_taken` | |
| 3 | novoaluno | `POST /api/auth/students` | `{"course_id":{COURSE_ES},"registration_number":"N0001","term":99}` | **400** `validation_error` em `term` | |
| 4 | novoaluno | `POST /api/auth/students` | `{"course_id":{COURSE_ES},"registration_number":"N0001","term":3}` | **201**, `{"student": {"user_id": ...}}` | |
| 5 | novoaluno | repetir o passo 4 | o mesmo | **409** `student_profile_exists` | |
| 6 | professor | `POST /api/auth/students` | o do passo 4 | **403** | |

## 2.2 Criar equipe (livre1)

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | livre1 | `GET /api/teams` | — | **200** paginado; "Equipe Seed" com `available_slots: 2` | |
| 2 | livre1 | `GET /api/teams?page=99` | — | **404** `not_found` ("Página inválida.") | |
| 3 | livre1 | `POST /api/teams` | `{"name":"Equipe Nova","invitations":[{"student_id":{LIVRE2_STUDENT_ID}}]}` | **400** `team_invitations_required` (mínimo 2 convites com `min_members` = 3) | |
| 4 | livre1 | `POST /api/teams` | `{"name":"Equipe Nova","invitations":[{"student_id":{LIVRE2_STUDENT_ID},"email":"livre2@aluno.desafiox.local"},{"student_id":{LIVRE5_STUDENT_ID}}]}` | **400** `validation_error` ("student_id ou email, nunca os dois") | |
| 5 | livre1 | `POST /api/teams` | `{"name":"equipe seed","invitations":[{"student_id":{LIVRE2_STUDENT_ID}},{"student_id":{LIVRE5_STUDENT_ID}}]}` | **409** `team_name_taken` | |
| 6 | livre1 | `POST /api/teams` | `{"name":"Equipe Z","invitations":[{"email":"inativo@aluno.desafiox.local"},{"student_id":{LIVRE5_STUDENT_ID}}]}` | **404** `not_found` (aluno inativo); nenhuma equipe criada | |
| 7 | livre1 | `POST /api/teams` | `{"name":"Equipe Nova","invitations":[{"student_id":{LIVRE2_STUDENT_ID}},{"email":"livre5@aluno.desafiox.local"}]}` | **201**, livre1 como `LEADER`, `code` gerado, sem `qualification`, com `situation`, `disqualified_at` e `disqualified_by`. Anote `{TEAM_N}`. | |
| 8 | livre1 | repetir o passo 7 com outro nome | — | **409** `student_already_in_team` | |
| 9 | professor | `POST /api/teams` | o do passo 7 | **403** | |
| 10 | livre1 | `GET /api/teams/{TEAM_N}/invitations?status=PENDING` | — | **200**, convites de livre2 e livre5, sem o campo `invited_email` | |

## 2.3 Responder convites e notificações (livre2, livre5)

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | livre2 | `GET /api/notifications?unread=true` | — | **200** paginado, com notificação de convite (`type: TEAM`). Anote o `id` como `{NOTIF}`. | |
| 2 | livre2 | `GET /api/notifications?unread=abc` | — | **400** `validation_error` | |
| 3 | livre2 | `GET /api/notifications?page=99` | — | **404** | |
| 4 | aluno | `POST /api/notifications/{NOTIF}/read` | — | **404** (notificação de outro usuário) | |
| 5 | livre2 | `POST /api/notifications/{NOTIF}/read` | — | **200**, `read_at` preenchido | |
| 6 | livre2 | `GET /api/me/invitations?status=PENDING` | — | **200**, convite da "Equipe Nova". Anote `{INV_L2}`. | |
| 7 | livre2 | `GET /api/me/invitations?status=FOO` | — | **400** `validation_error` | |
| 8 | livre5 | `POST /api/invitations/{INV_L2}/respond` | `{"status":"ACCEPTED"}` | **403** ou **404** (só o convidado responde; anote qual veio) | |
| 9 | livre2 | `POST /api/invitations/{INV_L2}/respond` | `{"status":"TALVEZ"}` | **400** `validation_error` | |
| 10 | livre2 | `POST /api/invitations/{INV_L2}/respond` | `{"status":"ACCEPTED"}` | **200**, `status: ACCEPTED`, `responded_at` preenchido | |
| 11 | livre2 | repetir o passo 10 | — | **409** `invitation_not_pending` | |
| 12 | livre5 | `GET /api/me/invitations?status=PENDING` e responder `{"status":"DECLINED"}` | — | **200**, `status: DECLINED` | |
| 13 | livre1 | `GET /api/notifications?unread=true` | — | **200**, avisos de convite aceito e recusado | |

## 2.4 Convidar para a Equipe Seed (aluno seed, líder)

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | aluno | `GET /api/teams/{TEAM_A}/invitable-students?search=li` | — | **400** `validation_error` (mínimo 3 caracteres) | |
| 2 | aluno | `GET /api/teams/{TEAM_A}/invitable-students?search=livre` | — | **200** paginado, itens `{id, name, course}`; não traz quem tem equipe nem livre4 (convite pendente) | |
| 3 | aluno | `GET /api/teams/{TEAM_A}/invitable-students?search=livre&page=99` | — | **404** | |
| 4 | membro1 | `GET /api/teams/{TEAM_A}/invitable-students?search=livre` | — | **403** `not_team_leader` | |
| 5 | aluno | `POST /api/teams/{TEAM_A}/invitations` | `{"email":"livre6@aluno.desafiox.local"}` | **201**, `status: PENDING` | |
| 6 | aluno | repetir o passo 5 | — | **409** `invitation_pending_exists` | |
| 7 | aluno | `POST /api/teams/{TEAM_A}/invitations` | `{"email":"inativo@aluno.desafiox.local"}` | **404** `not_found` | |
| 8 | aluno | `POST /api/teams/{TEAM_A}/invitations` | `{"student_id":{LIVRE2_STUDENT_ID}}` | **409** `student_already_in_team` | |
| 9 | aluno | `POST /api/teams/{TEAM_A}/invitations` | `{}` | **400** `validation_error` | |
| 10 | aluno | `POST /api/teams/{TEAM_B}/invitations` | `{"email":"livre5@aluno.desafiox.local"}` | **403** `not_team_leader` (não é líder da equipe B) | |
| 11 | aluno | `GET /api/teams/{TEAM_A}/invitations` | — | **200**, convites de livre4 e livre6 | |
| 12 | livre4 | `POST /api/invitations/{INVITATION_LIVRE4}/respond` | `{"status":"ACCEPTED"}` | **200**; a equipe passa a ter 4 integrantes | |

## 2.5 Pedidos de entrada

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | aluno | `GET /api/teams/{TEAM_A}/join-requests?status=PENDING` | — | **200**, pedido de livre3 | |
| 2 | aluno | `GET /api/teams/{TEAM_A}/join-requests?status=FOO` | — | **400** | |
| 3 | membro1 | `GET /api/teams/{TEAM_A}/join-requests` | — | **403** ou **404** (o contrato lista os dois; em 27/11 veio 404) | |
| 4 | aluno | `POST /api/join-requests/{JOIN_REQUEST_LIVRE3}/respond` | `{"status":"APPROVED"}` | **200**; a equipe fica com 5 (cheia) | |
| 5 | aluno | repetir o passo 4 | — | **409** `join_request_not_pending` | |
| 6 | aluno | `POST /api/teams/{TEAM_A}/invitations` | `{"student_id":{LIVRE5_STUDENT_ID}}` | **409** `team_full` | |
| 7 | livre6 | aceitar o convite do passo 2.4.5 (`GET /api/me/invitations` para achar o id) | `{"status":"ACCEPTED"}` | **409** `team_full` | |
| 8 | livre5 | `POST /api/teams/{TEAM_A}/join-requests` | — | **409** `team_full` | |
| 9 | livre5 | `POST /api/teams/{TEAM_N}/join-requests` | — | **201**, `status: PENDING`. Anote `{JR_L5}`. | |
| 10 | livre5 | repetir o passo 9 | — | **409** `join_request_pending_exists` | |
| 11 | livre5 | `GET /api/me/join-requests?status=PENDING` | — | **200**, o pedido do passo 9 | |
| 12 | livre5 | `GET /api/me/join-requests?status=FOO` | — | **400** | |
| 13 | livre1 | `POST /api/join-requests/{JR_L5}/respond` | `{"status":"REJECTED"}` | **200**, `status: REJECTED` | |
| 14 | livre2 | `POST /api/teams/{TEAM_N}/join-requests` | — | **409** `student_already_in_team` | |
| 15 | livre5 | `POST /api/teams/999999/join-requests` | — | **404** | |

## 2.6 Consultar e renomear a equipe

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | aluno | `GET /api/teams/{TEAM_A}` | — | **200**, cinco integrantes com `role` | |
| 2 | aluno | `GET /api/teams/{TEAM_B}` | — | **404** (não é integrante) | |
| 3 | aluno | `GET /api/teams/999999` | — | **404** | |
| 4 | aluno | `PATCH /api/teams/{TEAM_A}` | `{"name":"Equipe Seed Renomeada"}` | **200**, novo nome | |
| 5 | aluno | `PATCH /api/teams/{TEAM_A}` | `{"name":"Equipe Seed","description":"x"}` | **400** `validation_error` em `description` | |
| 6 | aluno | `PATCH /api/teams/{TEAM_A}` | `{"name":"Equipe Sem Lider B"}` | **409** `team_name_taken` | |
| 7 | membro1 | `PATCH /api/teams/{TEAM_A}` | `{"name":"Outro"}` | **403** `not_team_leader` | |

## 2.7 Observação sobre integrante e liderança

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | aluno | `POST /api/teams/{TEAM_A}/member-notes` | `{"member_id":{MEMBRO1_MEMBER_ID},"text":"Faltou à reunião."}` | **201**, só `{id, created_at}` (o texto não volta) | |
| 2 | membro1 | `POST /api/teams/{TEAM_A}/member-notes` | o mesmo | **403** `not_team_leader` | |
| 3 | aluno | `POST /api/teams/{TEAM_A}/member-notes` | `{"member_id":999999,"text":"x"}` | **404** `not_found` (integrante de fora da equipe) | |
| 4 | aluno | `POST /api/teams/{TEAM_A}/leadership-requests` | `{"justification":"x"}` | **409** `team_has_leader` | |
| 5 | semliderc1 | `POST /api/teams/{TEAM_C}/leadership-requests` | `{}` | **400** `validation_error` em `justification` | |
| 6 | semliderc1 | `POST /api/teams/{TEAM_C}/leadership-requests` | `{"justification":"O líder saiu da instituição."}` | **201**, `status: PENDING`, `teacher: null` | |
| 7 | semliderc2 | repetir o passo 6 | — | **409** `leadership_request_pending_exists` | |
| 8 | semliderc2 | `GET /api/teams/{TEAM_C}/leadership-requests` | — | **200**, o pedido do passo 6 | |
| 9 | aluno | `GET /api/teams/{TEAM_C}/leadership-requests` | — | **403** ou **404** (não é integrante; anote qual veio) | |
| 10 | aluno | `POST /api/teams/{TEAM_A}/leadership-transfer` | `{"member_id":999999}` | **400** `validation_error` | |
| 11 | aluno | `POST /api/teams/{TEAM_A}/leadership-transfer` | `{"member_id":{MEMBRO1_MEMBER_ID}}` | **200** com a `Team`; membro1 vira `LEADER` e o aluno seed vira `MEMBER`. `member_id` é o `id` do integrante em `members` (não o `user_id`). | |
| 12 | aluno | `PATCH /api/teams/{TEAM_A}` | `{"name":"Tentativa"}` | **403** `not_team_leader` | |

## 2.8 Sair da equipe

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | membro1 | `POST /api/teams/{TEAM_A}/leave` | `{}` | **409** `leader_must_transfer` | |
| 2 | membro2 | `POST /api/teams/{TEAM_A}/leave` | `{}` | **204**; a equipe fica com 4 | |
| 3 | livre2 | `POST /api/teams/{TEAM_N}/leave` | `{}` | **409** `leave_below_minimum` (sobraria 1 de 3) | |
| 4 | livre2 | `POST /api/teams/{TEAM_N}/leave` | `{"confirm":true}` | **204** | |
| 5 | livre1 | `POST /api/teams/{TEAM_N}/leave` | `{"confirm":true}` | **204**; sozinho, a equipe fica `DISBANDED` | |
| 6 | livre1 | `POST /api/teams/{TEAM_A}/leave` | `{}` | **403** ou **404** (não é integrante; anote qual veio) | |

## 2.9 Painel do aluno

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | aluno | `GET /api/me/dashboard` | — | **200**, `edition` (status `PUBLISHED`) e `team` = Equipe Seed | |
| 2 | livre1 | `GET /api/me/dashboard` | — | **200**, sem equipe ativa | |
| 3 | professor | `GET /api/me/dashboard` | — | **403** | |

## 2.10 Fim da formação (opcional, depende do relógio)

Encerre a formação pelo shell, trocando `{STAGE_FORMACAO}` pelo id impresso:

```bash
uv run python manage.py shell -c "from django.utils import timezone; from apps.editions.models import Stage; Stage.objects.filter(pk={STAGE_FORMACAO}).update(ends_at=timezone.now())"
```

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | membro1 | `PATCH /api/teams/{TEAM_A}` | `{"name":"Depois do prazo"}` | **409** `formation_closed` | |
| 2 | livre5 | `POST /api/teams` | corpo de 2.2.7 com outro nome | **409** `formation_closed` | |
| 3 | semliderc1 | `GET /api/teams/{TEAM_C}/leadership-requests` | — | **200** (liderança continua valendo após a formação) | |

## Casos obrigatórios (resumo)

| Caso | Onde |
|---|---|
| Perfil errado (403) | 2.1.6, 2.2.9, 2.4.4, 2.6.7, 2.9.3 |
| Outra equipe / inexistente (403/404) | 2.3.4, 2.4.10, 2.5.15, 2.6.2–3, 2.7.9, 2.8.6 |
| Corpo inválido (400) | 2.1.3, 2.2.3–4, 2.3.9, 2.4.1, 2.4.9, 2.6.5, 2.7.5 |
| Regra de negócio (409) | 2.1.2, 2.1.5, 2.2.5, 2.2.8, 2.3.11, 2.4.6, 2.4.8, 2.5.5–8, 2.5.10, 2.5.14, 2.7.4, 2.7.7, 2.8.1, 2.8.3, 2.10 |
| Filtro inválido (400) | 2.3.2, 2.3.7, 2.5.2, 2.5.12 |
| Página inexistente (404) | 2.2.2, 2.3.3, 2.4.3 |

## Observações do testador

