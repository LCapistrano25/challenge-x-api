# Mudanças do contrato da API que exigem ajuste no frontend

Comparação: `docs/api/openapi.yaml` da `main` × branch `feat/49-email-domains` (20/11/2026).
Fonte de verdade: `docs/api/openapi.yaml`. Em caso de dúvida, vale o contrato.

Formato de erro de todas as rotas: `{"error": {"code", "message", "details"}}`.
`details` é `null` ou `{campo: [mensagens]}` (erro sem campo vai em `non_field_errors`).

---

## 0. Mudanças de 24 a 26/11/2026 (decisões da #217)

As mudanças desta seção já estão na `developer` e no contrato, com exceção das subseções das #127 e #128, que ainda não estão na `developer`. As decisões estão na seção 0 do `docs/decisoes-regulamento.md`.

### Equipes

| O quê | Chamada | Para o front |
|---|---|---|
| **Editar o nome** (#233) | `PATCH /api/teams/{team_id}` com `{"name"}` | Só o líder, só na formação. `EditTeamDialog` só com o nome (tirar `description` de `TeamUpdate`). Erros: 403 `not_team_leader`, 409 `formation_closed`, 409 `team_disqualified`, 409 `team_name_taken`, 400 para outro campo no corpo. |
| **Alunos para convidar** (#232) | `GET /api/teams/{team_id}/invitable-students?search=` | Popup de convite. `search` obrigatório, mínimo 3 caracteres (400). Paginado. Cada item: `{id, name, course}`; mande `{"student_id": id}` no convite. Só o líder (403 `not_team_leader`). |
| **Convite por `student_id` ou `email`** (#231) | `POST /api/teams/{team_id}/invitations` e `invitations` do `POST /api/teams` | Um dos dois, nunca os dois. Aluno inexistente, inativo ou sem e-mail confirmado agora dá **404 `not_found`** (antes 409). |
| **`Invitation` sem `invited_email`** (#231) | respostas de convite | O campo saiu (vinha sempre `null`). |
| **Equipe no schema `Team`** (#245) | `GET /api/teams/{team_id}`, `POST /api/teams` | Sai `qualification`; entram `situation`, `disqualified_at` e `disqualified_by`. |
| **Admin: listar e desclassificar** (#219) | `GET /api/admin/teams`, `POST /api/admin/teams/{team_id}/disqualify` | Lista paginada com `edition_id`, `status` e `search`. Desclassificar exige `reason`; também desclassifica o projeto. 409 `team_already_disqualified` e `edition_closed`. |
| **Observações sobre integrantes** (#215) | `POST/GET /api/teams/{team_id}/member-notes` | Corpo `{member_id, text}`, sem `stage_id`. 403 `not_team_leader` no POST. |

### Projeto, painel e entregas

- **Categoria obrigatória (D-06, #238):** sem categoria, o envio de entrega dá `400 validation_error` com `details.category`. Projeto incompleto passa a ser: sem desafio, título, resumo **ou categoria**.
- **Painel do aluno (#227):** `GET /api/me/dashboard`. A falta de categoria aparece como `PROJECT_DATA_MISSING` em `incomplete_requirements` e conta na pendência `PROJECT_DATA_PENDING`.
- **Notificações (#223, #224):** entrega registrada, resultado homologado e mudança de chamado geram notificação no painel. **Não há e-mail** por enquanto (#234 adiada).

### Edição (admin)

- **Escala dos critérios (D-02, #237):** cada critério vale **10** por padrão (`max_score` do critério na etapa funciona como peso). A nota da etapa é `(soma dos points / soma dos max_score) × valor da etapa`. Os critérios **não** precisam somar o valor da etapa: tirar essa validação das telas de critérios da etapa.
- **Publicar edital (#226):** `POST /api/admin/editions/{edition_id}/publish` (multipart, `notice_file`). Pré-condição nova: cada etapa pontuada com pelo menos um critério (`details.stage_criteria`). Falha do armazenamento: **503 `storage_unavailable`**. O `regulation_url` aponta para `GET /api/public/editions/{edition_id}/regulation/{token}` (download público do PDF).
- **ODS da edição (#239):** `GET/PUT /api/admin/editions/{edition_id}/sdgs`. ODS inativa já habilitada pode ficar; incluir inativa dá 400; remover ODS usada por desafio dá 409 `sdg_in_use`.
- **Desafios (#244):** `GET/POST /api/admin/editions/{edition_id}/challenges` (filtros `course_id`, `sdg_id` e `active`) e `PATCH /api/admin/challenges/{challenge_id}`. Uma ODS por desafio (D-03); a 2ª pode ir na descrição. Curso inativo, ODS inativa ou ODS não habilitada na edição dá `400 validation_error` em `course_id` ou `sdg_id`; no PATCH, só quando eles mudam. Sem limite de 3 a 5 desafios por curso (D-09).
- **Cursos (#225):** respostas no schema `Course` completo; filtros `search` e `active`; 409 `course_name_taken` e `course_in_use`.

### Resultado da edição (admin)

Ordem do fluxo: **calcular → finalistas → avaliação externa → pódio → homologar**.

| Passo | Chamada | Observações |
|---|---|---|
| Calcular | `POST /api/admin/editions/{edition_id}/results/calculate` | Nota final e posição no curso. Sem pontos do aluno (D-04). |
| Finalistas | `POST .../finalists` | Sem corpo: os 3 primeiros de cada curso. Com `project_ids`: a lista exata. |
| **Pódio (novo)** | `POST .../awards/calculate` | 1º a 3º **por categoria na edição inteira** (D-01). Botão novo na tela. |
| Homologar | `POST .../results/homologate` | 409 `awards_not_calculated` sem pódio; 409 `results_pending_scores` com nota de etapa pendente. |

- `ResultRow` ganhou `category_rank` e `award` (1 a 3, ou `null`).
- Vencedores públicos (`GET /api/public/editions/{edition_id}/winners`): pódio **por categoria**, ordenado por categoria e colocação. Agrupar a galeria por categoria (não por curso).

### Checklist desta seção

- [ ] Tela de edição da equipe só com o nome (`PATCH /api/teams/{team_id}`)
- [ ] Popup de convite com `invitable-students` e `{student_id}`
- [ ] Convite: tratar 404 e remover `invited_email`
- [ ] Equipe: `situation` e dados da desclassificação no lugar de `qualification`
- [ ] Categoria obrigatória: avisar no projeto e tratar `details.category` no envio de entrega
- [ ] Critérios valendo 10, sem exigir que somem o valor da etapa
- [ ] Publicação do edital: `stage_criteria` e 503
- [ ] Resultado: botão do pódio, `category_rank`, `award` e os dois 409 novos da homologação
- [ ] Vencedores agrupados por categoria

### Edições e JSON malformado (#122 e #71)

- O POST administrativo aceita `year` de **2000 a 2100**. O PATCH aceita
  **1 ≤ min_members ≤ max_members ≤ 20**. Valores fora dessas faixas retornam
  `400 validation_error`. As colunas existentes comportam os valores aceitos.
- JSON malformado retorna `400 parse_error`, com `error.details: null`.
  Trate-o como falha na montagem do corpo da requisição. Dados inválidos
  retornam `validation_error` e corpos acima do limite retornam
  `request_too_large`.

### Critérios de avaliação (#127, ainda fora da `developer`)

| O quê | Chamada | Para o front |
|---|---|---|
| Listar | `GET /api/admin/editions/{edition_id}/criteria` | `200` com array de `Criterion`. |
| Criar | `POST /api/admin/editions/{edition_id}/criteria` | `201` com `Criterion`. Exige `name`. |
| Atualizar | `PATCH /api/admin/criteria/{criterion_id}` | `200` com `Criterion`. Envie pelo menos um campo. `409 criterion_in_use_by_evaluations` quando etapa vinculada já tem avaliação. |
| Excluir | `DELETE /api/admin/criteria/{criterion_id}` | `204` sem corpo. `409 criterion_linked_to_stage` se estiver vinculado a etapa. |

- As quatro rotas são administrativas. `401 not_authenticated` sem login, `403 permission_denied` para outros papéis e `404 not_found` se a edição ou o critério não existir.
- POST e PATCH recebem JSON. Campos desconhecidos, tipos inválidos ou valores fora dos limites dão `400 validation_error`. JSON malformado dá `400 parse_error`.
- `name` aceita de 1 a 150 caracteres após remover espaços das pontas e é único por edição sem diferenciar maiúsculas. Duplicata dá `409 criterion_name_taken`.
- `tiebreak_order` aceita `null` ou inteiro de 1 a 32767. Posição duplicada na edição dá `409 tiebreak_order_taken`. No PATCH, omitir `rubric` ou `tiebreak_order` mantém o valor, e `null` limpa.
- Edição `PUBLISHED` aceita as três operações de escrita, sujeitas às regras de cada rota. Edição encerrada permite leitura. As três operações de escrita devolvem `409 edition_closed`.

### Etapas e campos de entrega (#128, ainda fora da `developer`)

| O quê | Chamada | Para o front |
|---|---|---|
| Listar | `GET /api/admin/editions/{edition_id}/stages` | `200`, array de `Stage` na ordem do cronograma, já com os campos de entrega. |
| Criar | `POST /api/admin/editions/{edition_id}/stages` | `201` com `Stage`. Envie campos novos sem `id`. |
| Consultar | `GET /api/admin/stages/{stage_id}` | `200` com `Stage` e os campos de entrega. |
| Atualizar | `PATCH /api/admin/stages/{stage_id}` | `200` com `Stage`. Se enviar `submission_fields`, a lista substitui o conjunto. Envie `kind` em cada item. Um item com `id` preserva suas propriedades omitidas. |

- As rotas são administrativas. Sem login retorna `401 not_authenticated`, outro papel retorna `403 permission_denied` e recurso inexistente retorna `404 not_found`.
- Só `SETUP` aceita escrita pela API. Edição publicada retorna `409 edition_published`, encerrada retorna `409 edition_closed` e posição duplicada retorna `409 stage_position_taken`.
- Envie datas com fuso e `max_score` como texto decimal de até duas casas (por exemplo, `"3.00"`). `formats` e `max_size_mb` só se aplicam a `FILE`. Valores inválidos retornam `400 validation_error`.
- `name` não pode ficar em branco; espaços nas pontas são removidos.
- `scored` tem padrão `true`: em `FORMATION` e `FINAL`, envie `false`. `FORMATION` é única por edição. Ao desativar a pontuação no PATCH, envie também `max_score: null`.
- Ideia, Protótipo Parcial e Momento Final do Pitch usam `SUBMISSION` com campos configuráveis. Entrega Preliminar é um marco de mentoria, sem nota nem entrega digital obrigatória (D-06).

---

## 1. Projeto: o `PUT /api/teams/{team_id}/project` foi removido

**Fazer:** apagar a chamada antiga e usar 3 chamadas, todas só para o **líder ativo** da equipe (403 `not_team_leader` para os demais) e só **durante a formação** (409 `formation_closed` depois).

| Passo | Chamada | Corpo | Observações |
|---|---|---|---|
| 1. Desafio (RF29) | `PUT /api/teams/{team_id}/project/challenge` | `{"challenge_id": 15}` | **Cria o projeto** se ainda não existe. 400 `challenge_not_eligible` se o desafio for inativo, de outra edição ou de curso sem integrante ativo. |
| 2. Dados (RF30) | `PUT /api/teams/{team_id}/project/details` | `{"title": "...", "summary": "...", "objective": "..."}` | `title` (máx. 200) e `summary` obrigatórios; `objective` opcional. Serve para cadastrar e para editar. 409 `challenge_not_selected` se o passo 1 não foi feito. 409 `project_title_taken` (título único na edição, sem diferenciar maiúsculas e espaços extras). |
| 3. Categoria (RF30/RF49) | `PUT /api/teams/{team_id}/project/category` | `{"category_id": 2}` | 409 `project_not_found` se o passo 1 não foi feito. 400 `category_not_available`. Pode trocar até o fim da formação, mas não pode limpar. |

Todas devolvem 200 com o `Project` atualizado. Os corpos não aceitam campos extras (400).

**Fazer:** a tela deve seguir essa ordem (desafio → dados → categoria). Habilitar "dados" só depois de haver desafio, e "categoria" só depois de existir projeto. As listas de desafios e categorias continuam vindo de `GET /api/teams/{team_id}/project/options`.

### Formato novo do `Project` (`GET /api/teams/{team_id}/project`)

| Campo | Antes | Agora |
|---|---|---|
| `challenge` | sempre objeto | **objeto ou `null`** (null = desafio ainda não escolhido) |
| `category` | objeto ou null | sem mudança (objeto ou `null`) |
| `title`, `summary` | sempre preenchidos | **`""` (string vazia)** até o líder salvar os dados (RF30) |
| `objective` | string ou `null` | **sempre string** (pode ser `""`), nunca `null` |

**Fazer:**
- Remover qualquer `project.challenge.title` / `challenge.course.slug` sem checar `null` antes.
- Considerar "projeto incompleto" quando `challenge === null` **ou** `title === ""` **ou** `summary === ""` **ou** `category === null`. A entrega (item 4) exige desafio, título e resumo, senão volta 400 `validation_error`.
- Não tratar `objective === null`; o teste de "vazio" passa a ser `objective === ""`.

---

## 2. Desafio sem `title`, curso sem `slug`

**`ChallengeSummary`** (dentro de `Project`, `ProjectOptions` etc.) e **`PublicChallenge`** (vitrine pública):

- **Removido:** `title`.
- **Obrigatório agora:** `description`.
- **Fazer:** em todo lugar que mostra o nome do desafio (seleção do desafio na equipe, página do projeto, vitrine e detalhe público, listas de finalistas), exibir `description`. Se o texto for longo, truncar na interface.
- Aviso: o `Challenge` das rotas de **admin** (`/api/admin/editions/{id}/challenges`) ainda traz `title` nos exemplos do contrato. Não remover o título das telas de admin sem confirmar.

**`CourseSummary`** (curso dentro de projeto, desafio, vínculo de avaliador etc.):

- **Removido:** `slug`. Sobram `{id, name}`.
- **Fazer:** buscar `course.slug` / `.slug` no código e trocar por `name` (ou `id` para chave). Isso inclui filtros, `key` de listas e rotas montadas com slug.
- Não mudou ainda: os schemas do **próprio curso** (`/api/admin/courses`, `/api/courses`) e o erro `course_slug_taken` ainda têm `slug`. Isso muda na task de cursos.

---

## 3. Login com Microsoft: sessão por cookie, sem token

`POST /api/auth/sessions/microsoft` com `{"code": ...}` (corpo da requisição inalterado).

**Resposta 200 (antes → agora):**

```json
// antes
{"token": "eyJ...", "role": "...", "profile_completed": false}
// agora (sem token)
{"user_id": 42, "name": "Ana Ribeiro", "email": "ana@a.catolica-to.edu.br", "role": "STUDENT", "profile_completed": false}
```

**Fazer:**
1. Parar de ler/guardar `token` (localStorage, header `Authorization`). A credencial é o **cookie de sessão**.
2. Toda requisição à API com `credentials: 'include'` (fetch) ou `withCredentials: true` (axios).
3. Toda requisição que altera estado (POST/PUT/PATCH/DELETE) envia o header **`X-CSRFToken`**. O valor vem de `GET /api/auth/csrf`. Pedir uma vez ao abrir o app e de novo depois do login, e repetir o header em cada chamada.
4. Guardar `user_id`, `name`, `email`, `role` e `profile_completed` do corpo da resposta para a sessão da interface. Para recarregar a página, usar `GET /api/auth/me`.
5. A sessão **expira com 30 minutos sem requisição** e é renovada a cada requisição. Qualquer 401 em rota autenticada deve limpar o estado local e mandar para o login.
6. Se `profile_completed === false`: aluno vai para o autocadastro (RF19, `POST /api/auth/students`); professor vai para a escolha de cursos (item 7).
7. Tratar os erros novos:
   - 401 `invalid_credentials` (código inválido, expirado, já usado ou de outro tenant)
   - 403 `domain_role_mismatch` (domínio de e-mail não permitido)
   - 403 `inactive_account`
   - 409 `microsoft_identity_mismatch`
   - 503 `external_service_error` (Microsoft fora do ar ou login não configurado)

Atenção: o texto das rotas no contrato ainda diz "Bearer JWT". Está desatualizado; vale a sessão por cookie. E `GET /api/auth/csrf` existe no backend mas **não está listado como rota no contrato** ainda.

---

## 4. Entrega da etapa (`POST /api/projects/{project_id}/stages/{stage_id}/versions`)

Só o **líder**. Agora aceita dois formatos de corpo.

**A) Só links: `application/json`**

```json
{
  "items": [
    {"field_id": 31, "link": "https://github.com/equipe/projeto"},
    {"field_id": 32, "link": "https://youtu.be/abc123"}
  ],
  "notes": "Correção do relatório."
}
```

`items` agora é um **array de objetos** (antes era uma string JSON). Mínimo 1 item, um por campo da etapa, sem repetir `field_id`. Todos os campos obrigatórios devem constar.

**B) Com arquivos: `multipart/form-data`** (use `FormData`)

| Campo do form | Conteúdo |
|---|---|
| `items` | **string** `JSON.stringify([...])`. Item de link: `{"field_id": 31, "link": "..."}`. Item de arquivo: `{"field_id": 32, "file_index": 0}` |
| `files[]` (ou `files`) | os arquivos. O `file_index` é a posição do arquivo na ordem em que foram anexados |
| `notes` | opcional |

Cada item tem **ou** `link` **ou** `file_index`, nunca os dois, e o tipo tem que bater com o do campo (campo LINK recebe link; campo FILE recebe arquivo). Arquivo sobrando ou `file_index` inexistente é 400. Não defina `Content-Type` manualmente no multipart (o navegador coloca o `boundary`).

**Fazer:**
- Se a etapa tiver algum campo FILE, montar `FormData`; senão, pode enviar JSON.
- Validar no cliente (só para ajudar o usuário; o servidor é quem manda): extensão conforme os formatos do campo, tamanho máximo do campo, arquivo não vazio.
- Tratar os erros:
  - 400 `file_format_not_allowed` (extensão fora do permitido; executáveis e scripts nunca entram)
  - 400 `file_too_large`
  - 400 `validation_error` (campo obrigatório faltando, item repetido, projeto sem desafio/título/resumo, tipo do item errado)
  - 409 `stage_not_open` (**novo**: a etapa ainda não abriu)
  - 409 `stage_deadline_closed` (considera a prorrogação da equipe)
  - 409 `team_incomplete`, 409 `team_disqualified`, 409 `edition_closed`
  - 503 (**novo**: armazenamento de arquivos indisponível; mostrar "tente novamente")
- Resposta 201 é a versão registrada (comprovante).

### Download de arquivos da entrega

`DeliverableItem.file_url` **mudou de URL pública para caminho autenticado**:

```json
{"id": 301, "field_id": 32, "type": "FILE", "link": null,
 "file_url": "/api/deliverable-items/301/file", "file_name": "relatorio.pdf", "size_bytes": 1048576}
```

Para item de link, `file_url` é `null`.

**Fazer:**
- Montar o endereço como `<base da API>` + `file_url` (é um caminho relativo, não uma URL completa).
- O arquivo só baixa com sessão ativa. Usar `<a href download>` na mesma origem, ou `fetch(..., {credentials: 'include'})` + `Blob`. **Não** dá para usar em `<img src>`, `<iframe>` ou abrir em outro domínio sem cookie.
- A resposta vem como `attachment` (baixa direto, sem pré-visualização no navegador).
- Erros: 403 `project_access_denied` (aluno fora da equipe, professor sem vínculo com o curso do desafio) e 404 (item inexistente, de link, ou arquivo removido do armazenamento).
- Quem acessa: STUDENT integrante ativo, TEACHER com vínculo ativo no curso do desafio, ADMIN.

---

## 5. Avaliação do professor (`PUT /api/projects/{project_id}/stages/{stage_id}/evaluation`)

**Códigos de erro mudaram. Quebra a lógica que decide mensagem pelo `code`.**

| Situação | Antes | Agora |
|---|---|---|
| Avaliação já finalizada | 409 `evaluation_already_finalized` | **400 `validation_error`** |
| Prazo de avaliação encerrado | 409 `evaluation_period_closed` | **400 `validation_error`** |
| Entrega inválida / critério repetido / critério de outra etapa | (não existia) | **400 `validation_error`** |
| Professor sem vínculo com o curso | 403 genérico | **403 `teacher_not_in_course`** |
| Edição encerrada | 409 `edition_closed` | 409 `edition_closed` (igual) |
| Nota fora da faixa | 400 `points_out_of_range` | igual |

**Fazer:**
- Remover os `case` de `evaluation_already_finalized` e `evaluation_period_closed`.
- Para `validation_error`, mostrar `error.message` (e `error.details` se houver). Não dá mais para diferenciar pelo `code`.

**Regras novas que a tela deve respeitar (para não gerar 400 à toa):**
- Só pode avaliar projeto com **entrega válida** (versão enviada dentro do prazo da equipe, com a prorrogação).
- **Finalizar** (`status: FINALIZED`) só é aceito **depois do prazo de entrega da equipe**. **Rascunho** (`DRAFT`) pode ser salvo antes. Desabilitar o botão "Finalizar" antes do prazo e explicar o motivo.
- Um item por critério da etapa, sem repetir, e só critérios daquela etapa.
- `FINALIZED` exige todos os critérios preenchidos e torna a avaliação imutável.

### Painel do professor (`GET /api/teacher/projects`)

Uma linha por projeto e etapa de entrega pontuada, só de edição publicada.

- `deliverable_status`: `SUBMITTED` (enviou no prazo da equipe), `NOT_SUBMITTED` (sem versão, prazo aberto) ou `NOT_DELIVERED` (sem versão, prazo encerrado). Mapear os 3 valores para rótulo e cor.
- Filtro `pending_only`: devolve só `SUBMITTED` que **este** professor ainda não finalizou.
- Cada linha tem `evaluation_count`, `min_evaluators` e `my_evaluation_status`.

---

## 6. Convites: `Invitation.student`

- Antes: `student` podia ser `null` e tinha o formato de `UserSummary`.
- Agora: `student` **nunca é null** e só tem `{"user_id": 42, "name": "João Lima"}`.
- O campo `invited_email` saiu (#231); o convite por e-mail vai no corpo, não na resposta.

**Fazer:** remover o `student?.` / checagem de null e qualquer uso de outros campos do aluno (e-mail, perfil etc.) nas telas de convites (`/api/me/invitations`, `/api/teams/{id}/invitations`).

---

## 7. Cadastro do professor no primeiro acesso (`POST /api/auth/teachers`)

Deixou de ser "proposto". Corpo inalterado (`TeacherProfileCreate`).

- A escolha dos cursos é **única**: uma nova tentativa recebe **409 `teacher_profile_exists`**. Depois disso só o admin altera os cursos.
- Os vínculos já nascem **ativos** e dão escopo de avaliação imediatamente.
- Erro novo: 400 `registration_rejected` (curso inexistente ou inativo).

**Fazer:** antes de enviar, mostrar uma tela de **confirmação** ("não poderá alterar depois, apenas o administrador"). Em 409, mandar o professor para a tela inicial em vez de reabrir o formulário.

---

## 8. Admin: domínios de e-mail institucionais (RF02), tela nova

Só ADMIN (403 para os demais).

| Ação | Chamada | Corpo |
|---|---|---|
| Listar | `GET /api/admin/email-domains` | — |
| Cadastrar | `POST /api/admin/email-domains` | `{"name": "a.catolica-to.edu.br", "role": "STUDENT", "active": true}` (`active` padrão `true`, `name` máx. 100) |
| Editar / ativar / desativar | `PATCH /api/admin/email-domains/{domain_id}` | qualquer campo de `name`, `role`, `active` (pelo menos um) |

Objeto devolvido: `{"id", "name", "role", "active"}`. `role` só aceita `STUDENT` ou `TEACHER`.

- **Não há DELETE.** Para "remover", enviar `{"active": false}`.
- O servidor normaliza `name` para minúsculas e sem espaços. Mostrar o valor devolvido, não o digitado.
- Erros: 400 (formato de domínio inválido, `role` inválido), 409 `email_domain_taken` (unicidade sem diferenciar maiúsculas), 404 no PATCH.
- Em corpo com campo desconhecido o servidor responde 400.

---

## 9. Ajustes menores

- **Avaliador externo** (`ExternalEvaluatorCreate` e `ExternalEvaluatorAdminUpdate`): `institution` com **máximo 150 caracteres** (antes 200). Ajustar o `maxLength` dos formulários.
- **Exemplos de resposta:** o `slug` do curso saiu de 36 operações. Se o frontend usa mocks baseados nos exemplos, regenerar.

---

## 10. Canvas e SWOT na entrega da etapa (#169 e #170)

O professor pediu que o Business Model Canvas e a matriz SWOT sejam preenchidos no sistema. O admin escolhe, por etapa, se a entrega exige um deles, os dois ou nenhum, como qualquer outro campo de entrega (com `required`). Não há nota própria: o professor avalia pelos critérios que já existem.

**Fazer:**

- `FieldType` (campo `type` de `DeliverableField` e de `DeliverableItem`) ganha dois valores: `CANVAS` e `SWOT`. Hoje o frontend só trata `LINK` e `FILE`; tratar os dois novos, senão a etapa com canvas ou SWOT fica sem tela de preenchimento.
- `DeliverableField` de `CANVAS` e `SWOT` vem com `formats: null` e `max_size_mb: null`. Não mostrar upload nem campo de link para eles.
- `POST /api/projects/{project_id}/stages/{stage_id}/versions` aceita um terceiro tipo de item, com `content`. Em cada item vai **só um** entre `link`, `file_index` e `content` (senão 400). Funciona em JSON e em multipart (`items` em string JSON).
- `GET /api/projects/{project_id}/deliverables` e a resposta do `POST` trazem `content` em cada item: o objeto do canvas ou do SWOT, ou `null` para link e arquivo. Aluno, professor e admin recebem o conteúdo.

**Formato fixo do `content`** (chaves exatas; chave desconhecida é 400):

Canvas (`type: "CANVAS"`): um texto por bloco, **os nove obrigatórios**.

```json
{
  "field_id": 31,
  "content": {
    "customer_segments": "Gestores de condomínios e escolas",
    "value_propositions": "Reduzir o desperdício de água",
    "channels": "Aplicativo e site",
    "customer_relationships": "Suporte por chat",
    "revenue_streams": "Assinatura mensal",
    "key_resources": "Sensores e servidor",
    "key_activities": "Desenvolver e testar o sensor",
    "key_partnerships": "Laboratório do campus",
    "cost_structure": "Hardware e hospedagem"
  }
}
```

SWOT (`type: "SWOT"`): uma lista de textos por quadrante, **ao menos um texto em cada**.

```json
{
  "field_id": 32,
  "content": {
    "strengths": ["Equipe de 5 pessoas"],
    "weaknesses": ["Pouco orçamento"],
    "opportunities": ["Edital do campus"],
    "threats": ["Concorrente com preço menor"]
  }
}
```

**Limites** (a tela deve impor antes de enviar): cada texto não vazio e com no máximo 5000 caracteres; cada quadrante do SWOT com de 1 a 20 textos. Fora disso o envio volta 400 `validation_error`, com a mensagem dizendo qual bloco ou quadrante falhou (`details.items`).

**Regras que a tela deve refletir:**

- Campo obrigatório exige o item completo. Campo opcional pode ficar sem item, mas um item enviado precisa estar completo (todos os blocos, ou todos os quadrantes).
- Cada envio cria uma versão nova e nada muda depois de enviado. Para corrigir, a tela reenvia tudo (todos os campos obrigatórios) como nova versão, como já é com links e arquivos.
- Mostrar o conteúdo como **texto puro**, sem interpretar HTML: o backend guarda o que o aluno digitou.
- Um corpo acima de 2,5 MB volta como 400 em HTML, fora do formato de erro da API. Com o limite de 5000 caracteres na tela isso não deveria acontecer.

**Em aberto:** os nomes e a lista de blocos ainda precisam ser confirmados com o professor (P-47 em `api-pendencias.md`). Se mudarem, o contrato muda junto.

---

## 11. Entregas e comprovante: nomes de campo (#187)

As respostas passam a usar os nomes do contrato. Os antigos deixam de existir, sem período de transição.

| Rota | Onde | Antes | Agora |
|---|---|---|---|
| `GET /api/projects/{project_id}/deliverables` | `stage` | `position` | `order` |
| idem | `stage` | `type` | `kind` |
| idem | `stage` | `points_value` | `max_score` (texto, ex.: `"3.00"`, ou `null`) |
| idem | `stage` | (não vinha) | `evaluation_ends_at` (data e hora ou `null`) |
| idem | `fields[]` | `type` | `kind` |
| idem | `versions[]` | `version_number` | `number` |
| `POST /api/projects/{project_id}/stages/{stage_id}/versions` | resposta 201 | `version_number` | `number` |
| `GET /api/deliverable-versions/{version_id}/receipt` | `stage` | `position` | `order` |

`items[].type` **não** mudou, e o corpo do envio também não.

**Fazer:** trocar os nomes nas telas de entrega e de comprovante.

---

## Checklist rápido

- [ ] Remover `PUT .../project`; criar os 3 passos (desafio, dados, categoria)
- [ ] Tratar `project.challenge = null`, `title = ""`, `summary = ""`, `objective` sempre string
- [ ] Trocar `challenge.title` por `challenge.description` (aluno, professor e vitrine pública)
- [ ] Remover `course.slug` dos objetos aninhados
- [ ] Login Microsoft: cookie + `credentials: 'include'` + `X-CSRFToken`; sem token; 401 → login; erros novos
- [ ] Envio de entrega: `items` array em JSON; multipart com `items` string + `files[]`; erros novos e 503
- [ ] Download de arquivo pelo caminho autenticado de `file_url`
- [ ] Avaliação: sair dos códigos 409 antigos, ler `validation_error`, bloquear "Finalizar" antes do prazo da equipe
- [ ] Painel do professor: 3 valores de `deliverable_status` e `pending_only`
- [ ] Convites: `student` nunca null, só `user_id` e `name`
- [ ] Professor primeiro acesso: tela de confirmação e 409 `teacher_profile_exists`
- [ ] Tela de admin de domínios de e-mail
- [ ] `institution` com máximo de 150 caracteres
- [ ] Entrega: tipos `CANVAS` e `SWOT`, item com `content`, limites de 5000 caracteres e 20 itens, texto puro
- [ ] Trocar os nomes de campo das entregas e do comprovante (item 11)

## Pontos em aberto (confirmar com o backend)

- `GET /api/auth/csrf` existe no código, mas não está documentado como rota no contrato.
- As operações marcadas `x-status: proposed` (12, incluindo envio de entrega e avaliação do professor) ainda podem mudar.
- Admin de desafios ainda mostra `title` no contrato. Confirmar se o título continua existindo para o admin.
