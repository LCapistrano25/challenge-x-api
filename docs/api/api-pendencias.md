# Pendências da API — Projeto X (Desafio X)

**Referência oficial:** DBML atualizado em 23/10/2026 (nomes em inglês, com `support_ticket` e `notification`).
**Fontes cruzadas:** requisitos funcionais (Administrador, Acadêmico, Professor, Avaliador, Público), documento de arquitetura dos apps e contrato das rotas de autenticação e usuários.
**Especificação relacionada:** `openapi.yaml` (OpenAPI 3.1.0). Cada operação aponta para estas pendências em `x-pendencias`.
**Regra:** nenhum item abaixo altera o modelo. Cada um aguarda decisão. As sugestões são apenas opções para revisão.

**Severidade**
- **Alta**: impede definir ou implementar o endpoint (ou a migration) sem decisão.
- **Média**: o endpoint pode ser definido com uma suposição, que precisa ser confirmada.
- **Baixa**: clareza, nomenclatura ou documentação.

---

## Resumo

| ID | Tema | Severidade | Afeta |
|---|---|---|---|
| P-01 | `users` sem os campos nativos do Django | Alta | `accounts`, 1ª migration |
| P-02 | Contrato de auth com valores e campos fora do DBML | Média | `accounts` |
| P-03 | Expiração por inatividade × JWT de 7 dias | Média | `accounts` |
| P-04 | Professor define o próprio escopo de avaliação | Alta | `accounts`, `evaluations` |
| P-05 | Criação de avaliador externo sem vínculo à edição | Média | `accounts`, `evaluations` |
| P-06 | Status de chamado divergentes | Alta | `support` |
| P-07 | Justificativa de recusa e histórico do chamado | Média | `support` |
| P-08 | `WAITING_USER` sem canal de resposta do usuário | Média | `support` |
| P-09 | Tipo de solicitação e prioridade do chamado | Baixa | `support` |
| P-10 | Quem abre e quem atende chamados | Média | `support` |
| P-11 | Nomes de campos do chamado na API | Baixa | `support` |
| P-12 | Regra de `resolved_at` | Baixa | `support` |
| P-13 | Notificação de convite por e-mail sem usuário | Média | `teams`, notificações |
| P-14 | Formato do `link` da notificação | Baixa | notificações |
| P-15 | Ação de exclusão das FKs novas | Baixa | `support`, notificações |
| P-16 | Transição para `IN_PROGRESS` da edição | Média | `editions` |
| P-17 | "Código/sigla" do curso × `slug` | Baixa | `core` |
| P-18 | Conteúdo da pré-carga da edição | Média | `editions` (seed) |
| P-19 | Prazo de avaliação dos professores | Alta | `editions`, `evaluations` |
| P-20 | Etapa `FINAL` pontuada | Baixa | `editions` |
| P-21 | Ajustes pontuais (RF14) sem persistência | Alta | `editions`, `evaluations` |
| P-22 | Desclassificação sem data e responsável | Média | `teams` |
| P-23 | Equipe incompleta (RF51) × `team_qualification` | Alta | `teams`, `projects` |
| P-24 | RF28 × RF40 sobre o ex-líder | Baixa | `teams` |
| P-25 | `project` com campos NOT NULL × fluxo RF29/RF30 | Alta | `projects` |
| P-26 | Transições de `project_status` | Média | `projects` |
| P-27 | Status de entrega e nota zero automática | Média | `projects`, `evaluations` |
| P-28 | Visibilidade pública do acervo | Baixa | `results` |
| P-29 | Seleção de finalistas sem requisito | Alta | `results`, `evaluations` |
| P-30 | Nota final, ranking e premiação | Alta | `results` |
| P-31 | Fórmula da pontuação individual | Alta | `results` |
| P-32 | Banca do avaliador externo | Média | `evaluations` |
| P-33 | Significado de `PARTIAL` em `stage_score` | Baixa | `evaluations` |
| P-34 | Tipos de certificado incompletos | Média | `results` |
| P-35 | Notícias e canal de dúvidas sem tabela | Baixa | painel público |
| P-36 | Referências quebradas nos requisitos | Baixa | documentação |
| P-37 | Formato padrão de erro | Média | todos |
| P-38 | Paginação das listagens | Baixa | listagens |
| P-39 | Decimais serializados como string | Baixa | notas e pontuações |
| P-40 | 400 × 422 para erros de validação | Baixa | todos |
| P-41 | Definição de "edição vigente" | Média | `public`, `teams`, `auth` |
| P-42 | Campo `profile_completed` na sessão Microsoft | Média | `auth` |
| P-43 | Formato multipart dos uploads | Média | `editions`, `projects`, `results` |
| P-44 | Anonimato do professor nos feedbacks | Média | `evaluations` |
| P-45 | Confirmação explícita no encerramento da edição | Baixa | `editions` |
| P-46 | Emissão de certificados e endpoints de resultados ausentes | Alta | `results` |

---

## 1. Autenticação e usuários

### P-01 — `users` sem os campos nativos do Django · Alta
- **Decisão anterior:** os campos nativos do modelo de usuário do Django podem permanecer (`AbstractBaseUser` + `PermissionsMixin`).
- **DBML:** `users` não tem `last_login`, `is_superuser` e `is_staff`. As tabelas M2M `users_groups` e `users_user_permissions` também não aparecem.
- **Impacto:** a primeira migration de `accounts` vai gerar colunas e tabelas ausentes do DBML, e o `AUTH_USER_MODEL` não pode ser trocado depois.
- **Decidir:** incluir esses campos e tabelas no DBML ou abrir mão dos campos nativos (`last_login = None`, sem `PermissionsMixin`). Também é preciso confirmar o mapeamento `password_hash` ↔ `password` e `active` ↔ `is_active` (via `db_column`/property).

### P-02 — Contrato de autenticação fora do DBML · Média
- O contrato retorna `"profile": "ALUNO"`/`"PROFESSOR"`, mas o enum `user_role` usa `STUDENT`/`TEACHER`.
- `POST /api/auth/students` recebe `enrollment` e `semester`, enquanto o DBML usa `registration_number` e `period`.
- `POST /api/auth/professors` usa `professor`/`course_ids`, mas a tabela é `teacher`/`teacher_course`.
- **Suposição para os endpoints:** a API expõe os nomes e valores do DBML (`role`, `STUDENT`, `registration_number`, `period`, `/teachers`). Confirmar e atualizar o contrato.

### P-03 — Expiração por inatividade × JWT de 7 dias · Média
- O RF01 exige que a sessão expire **por inatividade**, mas o contrato sugere um JWT com validade fixa de 7 dias. Um JWT sem estado não tem como detectar inatividade.
- **Opções:** access token curto com refresh token deslizante, ou revisar o RF01.

### P-04 — Professor define o próprio escopo de avaliação · Alta
- O RF36.1 deixa o professor selecionar os próprios cursos no primeiro acesso, e `teacher_course.active` tem default `true`.
- Pelo RFXX ("Atualizar cadastro de professor"), o vínculo com cursos define quais projetos ele avalia, e somente o Administrador altera esse vínculo.
- **Impacto:** do jeito atual, o professor ganha permissão de avaliação sem validação administrativa. O próprio contrato de auth já sinaliza esse risco.
- **Decidir:** se o vínculo criado no RF36.1 nasce ativo ou pendente de aprovação do Admin (por exemplo, gravado com `active = false`, sem mudar o schema).

### P-05 — Criação de avaliador externo sem vínculo à edição · Média
- O RF11 pede cadastrar o avaliador **e** vinculá-lo à edição com uma abrangência (todos os cursos ou um curso), o que envolve `edition_evaluator`.
- `POST /api/auth/external-evaluators` só cria `users` + `external_evaluator`.
- O RF41 nega login a avaliador sem vínculo com a edição vigente, então um avaliador criado só por essa rota não consegue entrar.
- **Decidir:** uma única rota que cria o avaliador e o vínculo, ou duas rotas (criação e `POST /api/admin/editions/{id}/evaluators`).

---

## 2. Chamados (`support_ticket`)

### P-06 — Status divergentes · Alta
| Fonte | Status |
|---|---|
| RFXX (Admin) | em análise, atendido, recusado |
| Contrato da API | `PENDENTE`, `EM_ANALISE`, `ATENDIDO`, `RECUSADO` |
| DBML | `OPEN`, `IN_PROGRESS`, `WAITING_USER`, `RESOLVED`, `CLOSED` |

- O DBML não tem um estado equivalente a **recusado**.
- **Mapeamento sugerido, para revisão:** PENDENTE→`OPEN`, EM_ANALISE→`IN_PROGRESS`, ATENDIDO→`RESOLVED`, RECUSADO→`CLOSED` com `support_response` obrigatório. Também é preciso definir as **transições permitidas** entre os estados.

### P-07 — Justificativa de recusa e histórico · Média
- O RF exige justificativa na recusa e o contrato pede preservar o "histórico básico do atendimento".
- O DBML tem um único campo, `support_response`, que é sobrescrito a cada atualização. Não há histórico de mudanças de status nem de respostas.
- **Decidir:** se um único campo basta ou se é necessária uma tabela de histórico ou mensagens.

### P-08 — `WAITING_USER` sem canal de resposta do usuário · Média
- O status `WAITING_USER` pressupõe que o solicitante possa responder ou complementar o chamado.
- O contrato proíbe o usuário de alterar o chamado e não existe tabela de mensagens.
- **Decidir:** como o usuário responde (novo campo, tabela de mensagens ou edição da `description`) e quem tira o chamado de `WAITING_USER`.

### P-09 — Tipo de solicitação e prioridade · Baixa
- O RFXX (Aluno/Professor) recebe um "tipo de solicitação", mas não existe campo para isso no DBML.
- `priority` existe no DBML, mas nenhum requisito diz quem define (usuário ou Admin) nem se pode ser alterada.

### P-10 — Quem abre e quem atende · Média
- O RF e o contrato falam em **alunos e professores**, enquanto a nota do DBML fala em "authenticated users". Avaliadores externos e admins também podem abrir chamados?
- `assigned_to` aponta para qualquer `users`, e a nota cita "support/admin roles", mas `user_role` não tem papel de suporte.
- **Suposição:** apenas `ADMIN` pode ser atribuído e atender (validação na aplicação).

### P-11 — Nomes de campos na API · Baixa
- O contrato usa `subject` e `response`, enquanto o DBML usa `title` e `support_response`.
- **Suposição:** a API segue o DBML.

### P-12 — Regra de `resolved_at` · Baixa
- Não há regra nem CHECK dizendo quando `resolved_at` é preenchido (apenas em `RESOLVED`? também em `CLOSED`?) e se volta a nulo em caso de reabertura.

---

## 3. Notificações (`notification`)

### P-13 — Convite por e-mail para aluno sem cadastro · Média
- `invitation` aceita `invited_email` sem `student_id`, mas `notification.user_id` é NOT NULL.
- O RF22 exige notificar o convidado no painel, o que é impossível enquanto ele não tiver usuário.
- **Decidir:** se, ao concluir o autocadastro (RF19), o sistema associa os convites pendentes daquele e-mail ao aluno (preenchendo `student_id` e limpando `invited_email`, conforme o CHECK de exclusividade) e só então gera a notificação.

### P-14 — Formato do `link` · Baixa
- Não está definido se `link` guarda uma rota do frontend ou o caminho de um recurso da API. Também não há referência estruturada à entidade de origem (convite, solicitação etc.).

### P-15 — Ação de exclusão das FKs novas · Baixa
- `notification.user_id`, `support_ticket.user_id` e `support_ticket.assigned_to` não definem `delete`/`update`, enquanto todas as outras referências definem.
- **Suposição:** `RESTRICT`, já que usuários nunca são excluídos fisicamente.

---

## 4. Edições e configuração

### P-16 — Transição para `IN_PROGRESS` · Média
- `edition_status` tem `SETUP → PUBLISHED → IN_PROGRESS → CLOSED`, mas os requisitos só descrevem a publicação (RF09) e o encerramento (RF47).
- **Decidir:** se `IN_PROGRESS` é definido manualmente pelo Admin, automaticamente pela data da primeira etapa, ou se é dispensável.

### P-17 — "Código/sigla" do curso × `slug` · Baixa
- O RF03 pede "código/sigla" e unicidade por nome **ou** sigla. O DBML tem `slug` (único).
- **Confirmar:** `slug` é a sigla informada pelo Admin ou um valor gerado a partir do nome?

### P-18 — Conteúdo da pré-carga da edição · Média
- O RF47/RF06/RF49 manda pré-carregar os 7 critérios do Quadro 1 do regulamento, as categorias padrão (Art. 2) e os limites 3–5.
- O texto dos 7 critérios e de suas faixas não está no material disponível.

### P-19 — Prazo de avaliação dos professores · Alta
- O RF38 diz que a avaliação deve respeitar o "prazo limite de avaliação definido no cronograma da etapa".
- `stage` só tem `starts_at`/`ends_at`, que são o período de submissão das equipes. Não há prazo de avaliação.
- **Decidir:** se o prazo de avaliação é o mesmo `ends_at`, uma janela posterior (o que exige campo novo) ou se não existe limite.

### P-20 — Etapa `FINAL` pontuada · Baixa
- O RF07 diz que a etapa `FINAL` não compõe a nota acadêmica, mas não há CHECK impedindo `type = FINAL` com `scored = true`.
- **Suposição:** validar na aplicação.

### P-21 — Ajustes pontuais (RF14) sem persistência · Alta
- O RF14 exige um histórico **imutável** de cada ajuste (responsável, data/hora, valor anterior, valor novo, justificativa), mas não existe tabela para isso. A arquitetura também proíbe criar auditoria sem decisão.
- A prorrogação de prazo **para uma equipe específica** não tem onde ser gravada, porque `stage` só tem prazo global.
- Não está definido se uma `evaluation` em `FINALIZED` pode ser alterada. A retificação de nota do RF14 pressupõe que sim, mas apenas pelo Admin.

---

## 5. Equipes

### P-22 — Desclassificação sem data e responsável · Média
- O RF13 exige registrar a justificativa **com data e responsável**. `team` só tem `disqualification_reason`.

### P-23 — Equipe incompleta (RF51) × `team_qualification` · Alta
- O RF51 exige registrar a equipe como "incompleta" **e** os requisitos não atendidos (número de integrantes, desafio, dados do projeto).
- `team_qualification` só tem `QUALIFIED`/`NOT_QUALIFIED` e não há campo para os motivos.
- A semântica do campo também é ambígua: `NOT_QUALIFIED` significa "incompleta" ou "não classificada para a final"?
- **Impacto:** bloqueia o painel do RF20 e o bloqueio de entregas do RF31/RF51.

### P-24 — RF28 × RF40 sobre o ex-líder · Baixa
- O RF40 diz que, ao aprovar a solicitação, o ex-líder passa a "Membro". Mas o RF28 só permite a solicitação quando **não existe** líder ativo, ou seja, quando o líder já saiu ou perdeu o acesso.
- **Confirmar:** o ex-líder ainda é membro ativo nesse cenário?

---

## 6. Projetos e entregas

### P-25 — `project` com campos NOT NULL × fluxo RF29/RF30 · Alta
- `challenge_id`, `title` e `summary` são NOT NULL.
- O RF29 seleciona o desafio **antes** do RF30 (título e resumo), então a seleção do desafio não pode ser gravada sozinha.
- O RF26 (regra 5) e o RF29 exigem **invalidar** o desafio quando o curso perde representante, o que é impossível com `challenge_id` NOT NULL.
- **Decidir:** tornar esses campos anuláveis ou adotar um fluxo único (desafio + categoria + título + resumo numa só requisição), com outra forma de marcar a invalidação.

### P-26 — Transições de `project_status` · Média
- `project_status` tem `IN_PROGRESS`, `SUBMITTED`, `UNDER_EVALUATION`, `APPROVED` e `REJECTED`, mas nenhum requisito define quando o projeto é aprovado ou reprovado, nem quem faz cada transição.

### P-27 — Status de entrega e nota zero automática · Média
- O RF31 define os status "Não enviada", "Enviada" e "Não entregue", que não estão persistidos.
- **Suposição:** são derivados (sem versão + prazo aberto = Não enviada; com versão = Enviada; sem versão + prazo encerrado = Não entregue).
- **Decidir:** como aplicar a nota zero (RF31/RF32). O `stage_score` com `value = 0` é gravado por um job ao fim do prazo ou calculado na consulta? Com que `status`?

### P-28 — Visibilidade pública do acervo · Baixa
- O RF35 e o RF46 falam em projetos "homologados para exibição pública". Não há flag de publicação, só `project_result.homologated_at` e o `edition.status`.
- **Suposição:** são públicos os projetos de edições `CLOSED`, não desclassificados e com resultado homologado.

---

## 7. Avaliações e resultados

### P-29 — Seleção de finalistas sem requisito · Alta
- `project_result.finalist` existe e o RF42 depende dele ("homologados pelo Administrador", citando o RF15). Porém **o RF15 foi removido** e nenhum outro requisito define quem marca os finalistas nem com qual critério.

### P-30 — Nota final, ranking e premiação · Alta
- **Nota final (0–10):** não está explícito que `final_score` é a soma dos `stage_score.value` das etapas pontuadas.
- **Ranking da premiação** (3 primeiros por categoria dentro do curso, RF49): ele usa a nota acadêmica ou a nota do formulário final dos avaliadores externos (RF12/RF43)?
- **Agregação das notas externas:** média ou soma das `final_evaluation`? Conta só `FINALIZED`?
- **Desempate (RF06, Art. 24):** os critérios de desempate valem para qual ranking?
- **Homologação:** quem homologa (`homologated_at`) e o que fica bloqueado depois disso.

### P-31 — Fórmula da pontuação individual · Alta
- O RF19 (regra 6) diz que o período do aluno é a base da pontuação individual, e `student_score` congela `considered_period`. A fórmula não está em nenhum requisito.

### P-32 — Banca do avaliador externo · Média
- O RF43 exige avaliar todos os finalistas "alocados para a sua banca", mas não existe tabela de alocação. Só existe a abrangência por curso em `edition_evaluator.course_id`.
- **Suposição:** a banca é todo finalista dentro da abrangência do avaliador. Confirmar.

### P-33 — Significado de `PARTIAL` em `stage_score` · Baixa
- O RF32 só prevê os status "Definitiva" e "Pendente". O DBML tem também `PARTIAL`.
- **Suposição:** `PARTIAL` = há avaliações, mas abaixo de `min_evaluators`. Nesse caso, a API exibe "Pendente" e esconde o valor parcial?

### P-34 — Tipos de certificado incompletos · Média
- O RF17 lista como elegíveis: Participante, Finalista, Premiado, **Professor Avaliador** e **Avaliador Externo**.
- `certificate_type` só tem `PARTICIPATION`, `FINALIST` e `AWARD`. Com a unicidade `(edition_id, type)` em `certificate_template`, não dá para ter modelos distintos para professores e avaliadores.

---

## 8. Painel público

### P-35 — Notícias e canal de dúvidas sem tabela · Baixa
- O RF44 cita notícias e um canal de dúvidas na página pública, mas não há tabelas para isso.
- **Decidir:** se ficam fora do escopo, se viram conteúdo estático no frontend ou se precisam de modelagem.

---

## 9. Documentação dos requisitos

### P-36 — Referências quebradas · Baixa
- O RF20 referencia o RF51 nas regras, mas o **RF50** no critério de aceitação. O correto é RF51.
- O RF37 cita "RF10 e RF12" para o vínculo professor–curso. O RF10 foi removido e o RF12 é o formulário final.
- O RF42 cita o **RF15**, que foi removido (ver P-29).
- Os critérios de aceitação do RF19 são cópia dos do RF18.
- O texto do RF50 está duplicado e truncado.
- Há requisitos com código **RFXX** sem numeração, e o requisito de chamado aparece duplicado em Acadêmico e Professor.
- O RF30 diz que o projeto é cadastrado "com base nas ODS previamente selecionadas" (plural), mas o projeto tem um único desafio e, portanto, uma única ODS.

---

## 10. Decisões tomadas na especificação (`openapi.yaml`)

Estas são convenções que a especificação adota para ficar completa. Cada uma é uma **proposta** e pode ser trocada sem afetar o modelo.

### P-37 — Formato padrão de erro · Média
- Nenhuma fonte define o corpo dos erros.
- **Proposta:** `{"error": {"code": "<snake_case>", "message": "<texto>", "details": <objeto|null>}}` (schema `Error`). Em erros de validação, `details` é um mapa campo → lista de mensagens. Os conflitos de negócio (409) têm um `code` estável por regra (ex.: `formation_closed`, `team_full`).
- **Impacto na implementação:** exige um `EXCEPTION_HANDLER` customizado no DRF, porque o formato padrão do DRF é diferente.

### P-38 — Paginação · Baixa
- **Proposta:** `page` e `page_size` (padrão 20, máximo 100), resposta `{count, next, previous, results}`, que é o `PageNumberPagination` do DRF. Só as listagens que podem crescer são paginadas. Listas curtas e de configuração (cursos, etapas, critérios) retornam um array simples.

### P-39 — Decimais como string · Baixa
- Campos `decimal(4,2)` (notas, pontos, `points_value`, `max_score`) são serializados como string (`"2.50"`), que é o padrão do `DecimalField` do DRF e evita erro de ponto flutuante. Confirmar com o frontend.

### P-40 — 400 × 422 · Baixa
- A especificação usa **400** para validação de dados e **409** para conflito com regra de negócio. O código 422 não é usado. Se o time preferir 422 para validação semântica, a mudança é mecânica.

### P-41 — Definição de "edição vigente" · Média
- RF20, RF21, RF24, RF41 e RF44 dependem da "edição vigente", mas nenhum requisito a define.
- **Suposição:** a única edição com status `PUBLISHED` ou `IN_PROGRESS`. Também é preciso decidir se pode haver mais de uma ao mesmo tempo (o modelo não impede) e o que a API retorna quando não há nenhuma (a especificação usa 404 no painel público e 409 `no_current_edition` na criação de equipe).

### P-42 — `profile_completed` na sessão Microsoft · Média
- O contrato de auth exige que o aluno conclua o autocadastro (RF19) e que o professor configure seus cursos (RF36.1) no primeiro acesso, mas não diz como o frontend descobre que isso ainda falta.
- **Proposta:** a resposta de `POST /api/auth/sessions/microsoft` inclui `role` e `profile_completed` (se o registro `student`/`teacher` já existe). O campo não é persistido, porque é derivado.
- O contrato também não define **expiração, refresh token, logout nem endpoint de callback**. A especificação não presume nada disso (ver P-03).

### P-43 — Uploads em multipart · Média
- **Entrega de etapa:** `items` vai como string JSON com `field_id` e `link` ou `file_index`, e os arquivos vão em `files[]`. Isso é necessário porque a etapa tem um número variável de campos LINK e FILE.
- **Edital (RF09)** e **modelo de certificado (RF17):** um campo de arquivo único.
- Também é preciso definir onde os arquivos são armazenados (ex.: Azure Blob) e se as URLs devolvidas (`notice_url`, `file_url`, `template_url`) são públicas ou assinadas e com validade. Entregas e certificados não devem ficar com URL pública permanente.

### P-44 — Anonimato do professor nos feedbacks · Média
- O RF32 exibe ao aluno os feedbacks dos professores, mas não diz se o professor é identificado.
- **Suposição:** os feedbacks são exibidos **sem** o nome do professor. Confirmar.

### P-45 — Confirmação no encerramento da edição · Baixa
- O encerramento (RF47) é irreversível. A especificação exige `{"confirm": true}` no corpo para evitar disparo acidental. Isso é uma proposta e não está nos requisitos.

### P-46 — Emissão de certificados e endpoints de resultados ausentes · Alta
- **Não foram incluídos** na especificação, porque dependem de regras não definidas:
  - Emissão de certificados pelo Admin (RF17): a elegibilidade de Finalista e Premiado depende de P-29/P-30, e não existem tipos para professor e avaliador (P-34).
  - Seleção e homologação de finalistas, cálculo da nota final, ranking, premiação e pontuação individual (P-29, P-30, P-31).
  - Ajustes pontuais (RF14), sem persistência no modelo (P-21).
- **Rotas candidatas, ainda não especificadas:** `POST /api/admin/editions/{id}/results/calculate`, `POST /api/admin/editions/{id}/finalists`, `POST /api/admin/editions/{id}/results/homologate`, `POST /api/admin/editions/{id}/certificates/issue`, `POST /api/admin/teams/{id}/deadline-extensions` e `POST /api/admin/evaluations/{id}/rectifications`. Elas entram na especificação quando as regras forem aprovadas.

---

## 11. Endpoints confirmados e propostos

A especificação tem **109 operações em 79 caminhos**:
- **95 confirmadas** (`x-status: confirmed`): podem ter pendências de severidade média ou baixa, com uma suposição registrada que não muda o contrato de forma estrutural.
- **14 propostas** (`x-status: proposed`): dependem de uma pendência de severidade alta e podem mudar.

| Método | Caminho | Depende de |
|---|---|---|
| POST | `/api/auth/sessions/password` | P-01 (campos nativos de `users`) |
| POST | `/api/auth/teachers` | P-04 (escopo do professor) |
| POST | `/api/admin/editions/{edition_id}/stages` | P-19 (prazo de avaliação) |
| PATCH | `/api/admin/stages/{stage_id}` | P-21 (prorrogação individual) |
| GET | `/api/me/dashboard` | P-23 (equipe incompleta) |
| POST | `/api/projects/{project_id}/stages/{stage_id}/versions` | P-23 |
| PUT | `/api/teams/{team_id}/project` | P-25 (fluxo desafio → dados) |
| POST | `/api/teams/{team_id}/leave` | P-25 (invalidação do desafio) |
| PUT | `/api/projects/{project_id}/stages/{stage_id}/evaluation` | P-19, P-21 |
| GET | `/api/evaluator/finalists` | P-29 (seleção de finalistas) |
| PUT | `/api/evaluator/finalists/{project_id}/final-evaluation` | P-30 |
| GET | `/api/public/editions/{edition_id}/winners` | P-30 |
| POST | `/api/support/tickets` | P-06 (status do chamado) |
| PATCH | `/api/admin/support/tickets/{ticket_id}` | P-06 |

Duas decisões de desenho merecem atenção:
- **`PUT /api/teams/{team_id}/project`** junta RF29 e RF30 numa operação, porque o modelo exige desafio, título e resumo juntos. Se P-25 tornar esses campos anuláveis, ela pode ser dividida.
- **Avaliador externo:** a criação (`POST /api/auth/external-evaluators`, do contrato) e o vínculo com a edição (`POST /api/admin/editions/{edition_id}/evaluators`) ficaram separados (P-05).

Dois desvios do contrato de auth, ambos pela regra "DBML como referência":
- `POST /api/auth/professors` virou `POST /api/auth/teachers`.
- Os valores de perfil seguem `user_role` (`STUDENT`, `TEACHER`, `EXTERNAL_EVALUATOR`, `ADMIN`), não `ALUNO`/`PROFESSOR` (P-02).

---

## 12. Cobertura dos requisitos

| Requisito | Situação | Endpoints principais |
|---|---|---|
| RF01 | Coberto | `POST /api/auth/sessions/password` |
| RF02, RF10, RF15, RF16 | Removidos no documento de requisitos | — |
| RF03, RF04 | Coberto | `/api/admin/courses`, `/api/admin/sdgs`, `/api/admin/editions/{id}/sdgs` |
| RF05, RF06, RF07, RF08, RF49 | Coberto | `/api/admin/editions/{id}/challenges`, `/criteria`, `/stages`, `/categories`, `/api/admin/stages/{id}/criteria` |
| RF09 | Coberto | `POST /api/admin/editions/{id}/publish` |
| RF11 | Coberto | `POST /api/auth/external-evaluators` + `/api/admin/editions/{id}/evaluators` |
| RF12 | Coberto | `/api/admin/editions/{id}/final-form` |
| RF13 | Coberto (data e responsável não persistidos, P-22) | `POST /api/admin/teams/{id}/disqualify` |
| **RF14** | **Sem cobertura** | Sem tabela de histórico nem de prazo por equipe (P-21, P-46) |
| **RF17** | **Parcial** | Modelos e consulta dos próprios certificados; a emissão depende de P-29, P-30, P-34 e P-46 |
| RF18, RF36 | Coberto | `POST /api/auth/sessions/microsoft` |
| RF19 | Coberto | `POST /api/auth/students` |
| RF20 | Coberto (proposto) | `GET /api/me/dashboard` |
| RF21–RF28 | Coberto | `/api/teams`, convites, solicitações, saída, liderança |
| RF29, RF30, RF50 | Coberto (proposto) | `PUT /api/teams/{id}/project`, `/project/options` |
| RF31 | Coberto | entregas, versões e comprovante |
| RF32 | Coberto | `GET /api/projects/{id}/scores` |
| RF33, RF39 | Coberto | `/api/teams/{id}/member-notes` |
| RF34, RF35, RF45, RF46 | Coberto | `/api/public/projects`, `/api/public/editions`, `/winners` |
| RF36.1 | Coberto (proposto) | `POST /api/auth/teachers` |
| RF37, RF38 | Coberto | `/api/teacher/projects`, `/api/projects/{id}/stages/{id}/evaluation` |
| RF40 | Coberto | `/api/teacher/leadership-requests`, `/decide` |
| RF41 | Coberto | `POST /api/auth/sessions/password` (regra de vínculo à edição) |
| RF42, RF43 | Coberto (proposto) | `/api/evaluator/finalists` |
| RF44 | Parcial | `GET /api/public/editions/current`; notícias e canal de dúvidas sem modelo (P-35) |
| RF47, RF48 | Coberto | `/api/admin/editions`, `/close` |
| RF51 | Parcial | Reflexo no painel e bloqueio de entregas; a verificação é um processo agendado, sem endpoint (P-23) |
| RFXX (atualizar aluno, professor e avaliador; desativar usuário) | Coberto | `/api/admin/students`, `/teachers`, `/external-evaluators` e `/status` |
| RFXX (chamados) | Coberto (proposto) | `/api/support/tickets`, `/api/admin/support/tickets` |
| Notificações (RF22–RF28) | Coberto | `GET /api/notifications`, `POST /api/notifications/{id}/read` |

O processamento agendado (cancelar convites ao fim da formação, aplicar RF51 e gravar nota zero) não aparece como endpoint, porque não é uma operação HTTP.

---

## 13. Validação executada

O validador oficial (`openapi-spec-validator`) **não pôde ser instalado**, porque o acesso ao PyPI e ao npm estava bloqueado neste ambiente. A especificação **não** passou por esse validador nem por uma importação de teste no Apidog. Em vez disso, foi executado um script de validação próprio (`jsonschema` 4.26 local), com estas verificações:

| Verificação | Resultado |
|---|---|
| YAML sintaticamente válido (`yaml.safe_load`) | OK |
| `openapi: 3.1.0`, `info.title`, `info.version`, campos de topo e de operação permitidos | OK |
| 109 `operationId` únicos | OK |
| 201 `$ref` distintos, nenhum quebrado; nenhum componente sem uso | OK |
| Parâmetros de rota declarados e `required: true` em todas as rotas | OK |
| Nenhuma rota duplicada (mesmo método e caminho equivalente) | OK |
| Sem `requestBody` em GET ou DELETE | OK |
| Cada um dos 162 schemas é JSON Schema 2020-12 válido (meta-schema oficial) | OK |
| 572 exemplos de request e response validados contra os respectivos schemas | OK |
| Toda operação tem tag, summary, description e `x-requirements` | OK |

**Recomendação antes de considerar o arquivo definitivo:** rodar `npx @redocly/cli lint openapi.yaml` ou `openapi-spec-validator openapi.yaml` numa máquina com acesso à internet e fazer uma importação de teste no Apidog.

---

## 14. O que impede considerar a especificação definitiva

1. **Pendências altas que mudam contratos:** P-01, P-04, P-06, P-19, P-21, P-23, P-25, P-29, P-30 e P-31 (afetam as 14 operações propostas e a ausência de RF14 e de parte do RF17).
2. **Convenções transversais ainda não aprovadas:** formato de erro (P-37), paginação (P-38), decimais (P-39) e multipart (P-43).
3. **Contrato de auth:** nomes e valores alinhados ao DBML (P-02) e a ausência de definição para expiração, refresh e logout (P-03, P-42).
4. **Validação oficial e importação no Apidog** ainda não executadas (seção 13).

---

## Notas de implementação (não são inconsistências)

- `edition_sdg`, `teacher_course` e `project_course` têm PK composta, o que exige `CompositePrimaryKey` (Django 5.2 ou superior). `challenge → edition_sdg` usa a `CompositeForeignKey` customizada.
- O índice parcial `ux_invitation_pending_email` usa `lower(invited_email)` e precisa de um `UniqueConstraint` com expressão (`Lower("invited_email")`) e `condition`.
- `student.term ≤ course.term_count` envolve duas tabelas e, portanto, deve ser validado na aplicação.

---

## Histórico de alterações do contrato

| Data | Alteração | Motivo |
| :- | :- | :- |
| 24/10/2026 | `Course.period_count` → `term_count`; campo `period` do aluno → `term` (cadastro, perfil e atualização de aluno). | Glossário do guia de implementação: período do aluno é `term`. Alinha com `User.term` e `Course.term_count` no código. |
