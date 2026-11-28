# Roteiro 03 — Aluno: projeto e entregas

| | |
|---|---|
| **Responsável** | |
| **Data / commit testado** | |
| **Perfis** | STUDENT (líder e membro), ADMIN (prorrogação e desclassificação), TEACHER (leitura e 403) |
| **Pré-requisitos** | Ambiente do README com `seed_users` e `cenario.py` **padrão**. A "Equipe Seed" já tem projeto completo e uma versão na etapa encerrada. Há duas etapas de entrega: **encerrada** (`{STAGE_ENCERRADA}`, campo `{FIELD_LINK_ENCERRADA}`) e **aberta** (`{STAGE_ABERTA}`, campos `{FIELD_LINK_ABERTA}` obrigatório e `{FIELD_FILE_ABERTA}` PDF de até 1 MB, opcional). |
| **Login** | `aluno.jar` (aluno seed, líder), `m1.jar` (membro1), `l1.jar` (livre1), `prof.jar`, `admin.jar`. Senhas como no README. |

Cole aqui a saída do cenário:

```
```

Arquivos de teste (Git Bash):

```bash
printf '%%PDF-1.4\n%%%%EOF\n' > rel.pdf                          # PDF válido
printf 'texto' > nota.txt                                         # extensão não permitida
printf 'MZ executavel' > falso.pdf                                # extensão pdf, conteúdo não
{ printf '%%PDF-1.4\n'; head -c 2000000 /dev/zero; } > grande.pdf  # 2 MB, acima do limite do campo
```

Coluna **Resultado**: `ok`, `falhou #N` ou `bloqueado`.

## 3.1 Consultar o projeto

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | aluno | `GET /api/teams/{TEAM_A}/project` | — | **200**, `challenge` e `category` como objetos, `title: "Projeto Seed"`, `objective` texto (nunca `null`) | |
| 2 | professor | `GET /api/teams/{TEAM_A}/project` | — | **200** (professor do curso do desafio) | |
| 3 | admin | `GET /api/teams/{TEAM_A}/project` | — | **200** | |
| 4 | aluno | `GET /api/teams/{TEAM_B}/project` | — | **403** `project_access_denied` | |
| 5 | aluno | `GET /api/teams/{TEAM_A}/project/options` | — | **200**, `challenges` só do curso dos integrantes e `categories` só as ativas (sem "Categoria Inativa") | |
| 6 | professor | `GET /api/teams/{TEAM_A}/project/options` | — | **403** | |

## 3.2 Editar desafio, dados e categoria (formação aberta)

Antes, ache o id do "Desafio de outro curso": `api admin.jar GET /api/admin/editions/{EDITION}/challenges` → `{CH_OUTRO}`.

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | aluno | `PUT /api/teams/{TEAM_A}/project/challenge` | `{"challenge_id":{CHALLENGE}}` | **200**, `challenge.course` e `challenge.sdg` preenchidos | |
| 2 | aluno | `PUT /api/teams/{TEAM_A}/project/challenge` | `{"challenge_id":{CH_OUTRO}}` | **400** `challenge_not_eligible` (curso sem integrante) | |
| 3 | aluno | `PUT /api/teams/{TEAM_A}/project/details` | `{"title":"Monitoramento de água","summary":"Sensores e painel web.","objective":"Reduzir desperdício."}` | **200**, campos atualizados | |
| 4 | aluno | `PUT /api/teams/{TEAM_A}/project/details` | `{"title":"  projeto   b ","summary":"x"}` | **409** `project_title_taken` (ignora maiúsculas e espaços extras) | |
| 5 | aluno | `PUT /api/teams/{TEAM_A}/project/details` | `{"title":"Sem resumo"}` | **400** `validation_error` em `summary` | |
| 6 | aluno | `PUT /api/teams/{TEAM_A}/project/details` | `{"title":"X","summary":"Y","extra":1}` | **400** (campo extra) | |
| 7 | membro1 | `PUT /api/teams/{TEAM_A}/project/details` | o do passo 3 | **403** `not_team_leader` | |
| 8 | aluno | `PUT /api/teams/{TEAM_A}/project/category` | `{"category_id":{CATEGORY_INATIVA}}` | **400** `category_not_available` | |
| 9 | aluno | `PUT /api/teams/{TEAM_A}/project/category` | `{"category_id":{CATEGORY}}` | **200** | |
| 10 | aluno | `PUT /api/teams/{TEAM_A}/project/category` | `{"category_id":null}` | **400** (não dá para limpar a categoria) | |

### Equipe sem projeto (livre1)

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 11 | livre1 | `POST /api/teams` | `{"name":"Equipe Sem Projeto","invitations":[{"student_id":{LIVRE2_STUDENT_ID}},{"student_id":{LIVRE5_STUDENT_ID}}]}` | **201**. Anote `{TEAM_N}`. | |
| 12 | livre1 | `GET /api/teams/{TEAM_N}/project` | — | **404** (projeto ainda não existe) | |
| 13 | livre1 | `PUT /api/teams/{TEAM_N}/project/details` | o do passo 3 com outro título | **409** `challenge_not_selected` | |
| 14 | livre1 | `PUT /api/teams/{TEAM_N}/project/category` | `{"category_id":{CATEGORY}}` | **409** `project_not_found` | |

## 3.3 Enviar entregas

`POST /api/projects/{PROJECT_A}/stages/{STAGE_ABERTA}/versions`. Envios em JSON usam `api`; os com arquivo usam `upload` (multipart, `items` em texto JSON e `file_index` apontando para `files[]`).

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | aluno | `POST .../stages/{STAGE_ABERTA}/versions` | `{"items":[{"field_id":{FIELD_LINK_ABERTA},"link":"https://github.com/equipe/projeto"}],"notes":"Primeira versão."}` | **201**, `number: 1`, `receipt.verification_code` preenchido. Anote `{VERSION_1}`. | |
| 2 | aluno | repetir o passo 1 | — | **201**, `number: 2` (a versão 1 continua em `deliverables`) | |
| 3 | aluno | `upload aluno.jar POST .../stages/{STAGE_ABERTA}/versions` | `-F 'items=[{"field_id":{FIELD_LINK_ABERTA},"link":"https://github.com/x/y"},{"field_id":{FIELD_FILE_ABERTA},"file_index":0}]' -F 'files[]=@rel.pdf;type=application/pdf'` | **201**; o item FILE tem `file_url` `/api/deliverable-items/{id}/file`. Anote o id como `{ITEM_FILE}`. | |
| 4 | aluno | passo 3 com `files[]=@nota.txt` | — | **400** `file_format_not_allowed` | |
| 5 | aluno | passo 3 com `files[]=@falso.pdf` | — | **400** `file_format_not_allowed` (conteúdo não é PDF) | |
| 6 | aluno | passo 3 com `files[]=@grande.pdf;type=application/pdf` | — | **400** `file_too_large` | |
| 7 | aluno | passo 3 com `"file_index":5` | — | **400** `validation_error` (índice inexistente) | |
| 8 | aluno | `POST .../stages/{STAGE_ABERTA}/versions` | `{"items":[]}` | **400** `validation_error` (campo obrigatório sem resposta) | |
| 9 | aluno | `POST .../stages/{STAGE_ABERTA}/versions` | `{"items":[{"field_id":{FIELD_LINK_ENCERRADA},"link":"https://x.y"}]}` | **400** (campo de outra etapa) | |
| 10 | aluno | `POST .../stages/{STAGE_ENCERRADA}/versions` | `{"items":[{"field_id":{FIELD_LINK_ENCERRADA},"link":"https://x.y"}]}` | **409** `stage_deadline_closed` | |
| 11 | membro1 | o corpo do passo 1 | — | **403** (só o líder envia) | |
| 12 | aluno | `POST /api/projects/{PROJECT_B}/stages/{STAGE_ABERTA}/versions` | o do passo 1 | **403** | |
| 13 | aluno | `GET /api/notifications?unread=true` | — | **200**, notificação `DELIVERABLE` de entrega registrada | |

### Categoria obrigatória (D-06)

Tire a categoria do projeto pelo shell (pela API não dá para limpar):

```bash
uv run python manage.py shell -c "from apps.projects.models import Project; Project.objects.filter(pk={PROJECT_A}).update(category=None)"
```

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 14 | aluno | o corpo do passo 1 | — | **400** `validation_error` com `details.category` | |
| 15 | aluno | `GET /api/me/dashboard` | — | **200**; `incomplete_requirements` inclui `PROJECT_DATA_MISSING` | |
| 16 | aluno | `PUT /api/teams/{TEAM_A}/project/category` | `{"category_id":{CATEGORY}}` | **200**; repita o passo 1 → **201** | |

## 3.4 Consultar entregas, arquivo, comprovante e notas

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | aluno | `GET /api/projects/{PROJECT_A}/deliverables` | — | **200**, uma linha por etapa com as versões | |
| 2 | professor | `GET /api/projects/{PROJECT_A}/deliverables` | — | **200** | |
| 3 | aluno | `GET /api/projects/{PROJECT_B}/deliverables` | — | **403** `project_access_denied` | |
| 4 | aluno | `GET /api/deliverable-items/{ITEM_FILE}/file -o baixado.pdf` | — | **200**; `baixado.pdf` é o arquivo enviado | |
| 5 | professor | `GET /api/deliverable-items/{ITEM_FILE}/file -o p.pdf` | — | **200** | |
| 6 | livre1 | `GET /api/deliverable-items/{ITEM_FILE}/file` | — | **403** `project_access_denied` | |
| 7 | aluno | `GET /api/deliverable-items/{ITEM_A}/file` | — | **404** (item de link não tem arquivo) | |
| 8 | aluno | `GET /api/deliverable-versions/{VERSION_A}/receipt` | — | **200**, `verification_code`, `team`, `project`, `stage` | |
| 9 | professor | `GET /api/deliverable-versions/{VERSION_A}/receipt` | — | **403** (professor não consulta comprovante) | |
| 10 | aluno | `GET /api/deliverable-versions/999999/receipt` | — | **404** | |
| 11 | aluno | `GET /api/projects/{PROJECT_A}/scores` | — | **200**; etapas sem avaliação finalizada aparecem `PENDING`, sem valor nem feedback | |
| 12 | aluno | `GET /api/projects/{PROJECT_B}/scores` | — | **403** | |

## 3.5 Prorrogação de prazo (admin)

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | aluno | `POST /api/admin/teams/{TEAM_A}/deadline-extensions` | `{"stage_id":{STAGE_ENCERRADA},"ends_at":"2030-12-31T23:59:00Z","reason":"Atestado"}` | **403** | |
| 2 | admin | o mesmo | sem `reason` | **400** `validation_error` em `reason` | |
| 3 | admin | o mesmo | `ends_at` no passado (ex.: `2020-01-01T00:00:00Z`) | **400** (precisa ser depois do fim da etapa) | |
| 4 | admin | `POST /api/admin/teams/999999/deadline-extensions` | o do passo 1 | **404** | |
| 5 | admin | `POST /api/admin/teams/{TEAM_N}/deadline-extensions` | o do passo 1 | **404** (equipe sem projeto) | |
| 6 | admin | `POST /api/admin/teams/{TEAM_A}/deadline-extensions` | o do passo 1 | **201**, `granted_by` = id do admin, `granted_at` do servidor | |
| 7 | admin | repetir o passo 6 | — | **409** `deadline_extension_already_granted` | |
| 8 | aluno | `POST .../stages/{STAGE_ENCERRADA}/versions` | `{"items":[{"field_id":{FIELD_LINK_ENCERRADA},"link":"https://x.y"}]}` | **201** (vale o novo prazo da equipe) | |

## 3.6 Vitrine pública e desclassificação

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | sem login | `GET /api/public/projects?edition_id={EDITION}` | — | **200** paginado; o projeto da Equipe Seed aparece sem entregas, notas nem observações | |
| 2 | sem login | `GET /api/public/projects?course_id=abc` | — | **400** `validation_error` | |
| 3 | sem login | `GET /api/public/projects?page=99` | — | **404** | |
| 4 | sem login | `GET /api/public/projects/{PROJECT_A}` | — | **200** | |
| 5 | sem login | `GET /api/public/projects/999999` | — | **404** | |
| 6 | admin | `POST /api/admin/teams/{TEAM_A}/disqualify` | `{"reason":"Teste de desclassificação."}` | **200**, `status: DISQUALIFIED` | |
| 7 | aluno | o corpo do passo 3.3.1 | — | **409** `team_disqualified` | |
| 8 | aluno | `GET /api/deliverable-versions/{VERSION_A}/receipt` | — | **200** (comprovante continua acessível) | |
| 9 | sem login | `GET /api/public/projects/{PROJECT_A}` | — | **404** (equipe desclassificada some da vitrine) | |

## 3.7 Fora do prazo (opcional, depende do relógio)

Rode este bloco **antes do 3.6** (a equipe desclassificada não envia). Encerre a formação e adie o início da etapa aberta pelo shell:

```bash
uv run python manage.py shell -c "from datetime import timedelta; from django.utils import timezone; from apps.editions.models import Stage; Stage.objects.filter(pk={STAGE_FORMACAO}).update(ends_at=timezone.now()); Stage.objects.filter(pk={STAGE_ABERTA}).update(starts_at=timezone.now()+timedelta(days=1))"
```

| # | Perfil | Chamada | Corpo | Esperado | Resultado |
|---|---|---|---|---|---|
| 1 | livre1 | `PUT /api/teams/{TEAM_N}/project/challenge` | `{"challenge_id":{CHALLENGE}}` | **409** `formation_closed` | |
| 2 | aluno | `POST .../stages/{STAGE_ABERTA}/versions` | o do passo 3.3.1 | **409** `stage_not_open` | |

## Casos obrigatórios (resumo)

| Caso | Onde |
|---|---|
| Perfil errado (403) | 3.1.6, 3.3.11, 3.4.9, 3.5.1 |
| Outra equipe / inexistente (403/404) | 3.1.4, 3.2.12, 3.3.12, 3.4.3, 3.4.6–7, 3.4.10, 3.4.12, 3.5.4–5, 3.6.5 |
| Corpo inválido (400) | 3.2.5–6, 3.2.10, 3.3.4–9, 3.3.14, 3.5.2–3 |
| Regra de negócio (409, ou 400 com código próprio) | 3.2.2, 3.2.4, 3.2.8, 3.2.13–14, 3.3.10, 3.5.7, 3.6.7, 3.7 |
| Filtro inválido (400) | 3.6.2 |
| Página inexistente (404) | 3.6.3 |

## Observações do testador

