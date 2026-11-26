# Decisões do Regulamento — Desafio X (Plano de Issues)

Data-base: 22/11/2026 (revisado no mesmo dia contra o PDF do regulamento); decisões fechadas em 24/11/2026 (seção 0).  
Referência: Regulamento do Projeto Desafio X (3ª Edição — 2026) × branch `developer` (`d97d9e6`, já com as PRs #188 a #198) × issues do GitHub.

**Como este documento entra no fluxo:** ele é a proposta. Cada decisão só vale depois de registrada no `docs/api/api-pendencias.md`. Mudança de rota, campo ou regra da API segue o caminho do projeto: issue de decisão → PR no `gen_openapi.py` → YAML regenerado. O DBML não se edita: muda o model e roda `docs/modelagem/gen_dbml.py`.

Este documento consolida as decisões tomadas após a revisão do Regulamento e serve como roteiro direto para **alterar issues existentes**, **reabrir/retomar entregas incompletas** e **criar novas issues** no repositório.

---

## 0. Decisões fechadas em 24/11/2026 (#217)

**Esta seção vence as seções 1 a 6 onde elas divergem.** As seções seguintes são a proposta de 22/11, mantida como histórico. O andamento de cada correção está em `docs/plano-correcoes.md`.

| # | Decisão final | Situação em 25/11 |
|---|---|---|
| **D-01** | Um pódio só: 1º a 3º **por categoria na edição inteira** (Art. 26), pela média das `FinalEvaluation` `EVALUATED`; desempate por `final_score` e pelos critérios do Art. 24. Finalistas: 3 por curso. Banca da final por curso ou única (recomendação: única). | Finalistas automáticos na `developer` (#221). Falta `compute_awards` por categoria e a homologação depois do pódio (#230). |
| **D-02** | **Opção B.** Cada critério vale 10 por padrão (`StageCriterion.max_score`, o admin pode mudar como peso). Nota da etapa = `(soma dos points / soma dos max_score) × Stage.max_score`, média entre os professores. Sai `ensure_criterion_fits_stage` (INT-02, #183); fica a soma das etapas = 10 (INT-01). Contrato muda só nas descrições. | A implementar (#228). |
| **Desempate (Art. 24)** | Configurável por `Criterion.tiebreak_order` (padrão: Critério 1, depois Critério 4). Por etapa, nota do critério normalizada (`points / max_score × 10`) e média dos professores; soma entre etapas. Empate total divide a posição (1, 1, 3). | Aplicado (#221). |
| **D-03** | 1 ODS principal por desafio; a 2ª ODS vai na `description`. Sem mudança de banco. | Vale para a carga do Apêndice A. |
| **D-04** | **Fora do escopo:** o sistema não calcula pontos do aluno na disciplina (o período não é atualizado). O professor converte a nota final. Psicologia avalia por conceitos, fora do sistema. Substitui a D-04 da seção 1. | Aplicado (#221 removeu `StudentScore`). Fechar a #111. |
| **D-05** | Desclassificar a equipe também põe o projeto em `DISQUALIFIED`, na mesma transação. Art. 18 e Art. 11 IV fora do MVP: o admin resolve. | Na #219 (aberta). |
| **D-06** | Categoria do projeto **obrigatória** no congelamento (`compute_unmet_requirements`) e no envio de entrega (`ensure_project_complete`). | Congelamento na #219; envio de entrega a implementar (#229). |
| **D-07** | Certificados **adiados**. A universidade talvez emita; o sistema pode só listar os elegíveis. | Aguardando a coordenação. |
| **D-09** | (a) Carga do Apêndice A entra, depois das respostas da coordenação. (b) 3 a 5 desafios por curso: **fora**. (c) Só o e-mail real entra; o envio fica a definir. Avisos públicos: **fora**. (d) Aceite do regulamento: **fora**. Substitui as Novas Issues 4, 5 (só o e-mail fica) e 6. | (a) aguarda a coordenação; (c) #234. |
| **D-10** | Sem papel de coordenador. Coordenadores usam ADMIN ou TEACHER. | — |
| **Chamados** | Regras do app `support`: abrem STUDENT e TEACHER; atende só ADMIN ativo (P-10); CLOSED é final; RESOLVED só volta a IN_PROGRESS ou vai a CLOSED (P-06); encerrar exige resposta (P-07); `resolved_at` limpo na reabertura (P-12); notifica o solicitante. `WAITING_USER` fica no contrato, mas a orientação é não usar (P-08). Sem histórico de respostas. | Na #224 (aberta). |
| **Convite** | `InvitationCreate` aceita `student_id` **ou** `email` (`oneOf`). Rota nova `GET /api/teams/{team_id}/invitable-students?search=` (só o líder; `search` ≥ 3 caracteres; devolve id, nome e curso). | A implementar (#231 e #232). |
| **Editar equipe** | `PATCH /api/teams/{team_id}` só com `name`, só pelo líder e só na formação (Art. 15 § 1º). | A implementar (#233). |
| **Ano e limites (#122)** | `year` de 2000 a 2100; limites de equipe de 1 a 20; JSON malformado = `400 parse_error`. | Aplicado (#218). |
| **Branch de emergência** | Fica sem aplicação, como reserva de código. | — |

**Em aberto (decisão do dono):** homologar com nota pendente — recusar ou deixar o projeto de fora?

---

## 1. Resumo das Decisões

| # | Tema / Artigo do Regulamento | Decisão | Ação no GitHub |
|---|---|---|---|
| **D-01** | Premiação e etapa final (Art. 26º, Cap. VIII IV) | **3 finalistas por curso** (etapa acadêmica) e **3 premiados por categoria no geral da edição** (6 premiados no total), ranqueados pela **média das avaliações externas** (`FinalEvaluation` `EVALUATED`). Criar caso de uso `compute_awards`. | Alterar `#110` e `#69`; criar issue para `compute_awards` (ou incorporar à `#110`). |
| **D-02** | Escala da Rubrica do Quadro 1 (Art. 22º) | Professor avalia cada critério de **0 a 10** (faixas do Quadro 1: `0–2,5`, `2,6–5,0`, `5,1–7,4`, `7,5–10`). A nota da etapa é a média dos critérios convertida proporcionalmente para o peso `Stage.max_score` (soma das etapas pontuadas = `10`). **Atenção:** desfaz a regra da #183 (INT-02, `ensure_criterion_fits_stage`) e muda o contrato de `rubric`/`max_score` e `points` (#191). | Alterar `#127`, `#129`, `#130`; registrar a decisão no `api-pendencias.md` (a `#179` já foi fechada); **criar issue nova** para refatorar regras de pontuação em `editions` e `evaluations`, com a mudança de contrato. |
| **D-03** | Desafios com 2 ODS no Apêndice A (p. 17 e 19) | Manter **1 ODS principal** (`Challenge.sdg` FK atual) e citar a 2ª ODS no texto da descrição do desafio, sem alterar o schema agora. | Registrar em `#125` e na nova issue de carga oficial do Apêndice A. |
| **D-04** | Pontuação nas disciplinas, último ano e Psicologia (Art. 20º–21º) | Calcular `StudentScore.points` (`0–1,0` para 1º período; `0–2,0` para 2º+) para todos + criar endpoint de listagem/exportação **CSV** por curso/matrícula sinalizando alunos do último ano (`term > term_count - 2`). Conversão de **Psicologia** para conceitos fica fora do sistema até a coordenação fornecer a tabela de menções. | Alterar `#111` e `#69` (P-31); adicionar exportação CSV na `#111` (ou issue filha). |
| **D-05** | Exclusão consensual (Art. 11º IV) e desistência pós-formação (Art. 18º) | Exclusão consensual pós-formação fica **fora do MVP** (Admin trata exceções). Na `#120`, garantir que desclassificar a equipe também atualize `Project.status = DISQUALIFIED`. | Alterar `#120`; documentar Art. 11º IV / desistência pós-formação como fora do MVP. |
| **D-06** | Categoria obrigatória, Ideia e Entrega Preliminar (Art. 2º, Cap. VIII) | Tornar `Project.category` **obrigatória** em `compute_unmet_requirements` e `ensure_project_complete`. Ideia (cronograma/orçamento) e Vídeos (Protótipo/Pitch) usam etapas `SUBMISSION` configuráveis (`FILE`/`LINK`). Entrega Preliminar (mentoria 07/04) fica apenas como marco informativo, sem entrega digital nem nota. | **Criar issue nova** para obrigatoriedade de `category`; registrar orientação em `#128` e `#104`. |
| **D-07** | Certificados de 20h e 40h (Art. 27º–28º) | **Adiado (decidir depois).** Regras pendentes: exigir todas as etapas entregues para 20h, acúmulo 20h vs. 40h, verificação pública de `verification_code` e inscrição no Portal do Aluno. | Manter `#112` e `#69` (P-34, P-46) marcadas como aguardando definição futura. |
| **D-08** | Entregas fechadas incompletas na `developer` | Retomar endpoints de `editions` (`#122`). Os endpoints de ODS (`#132`) voltaram com a #193 em 22/11. | **Criar issue de retomada** para `#122`. |
| **D-09** | Itens complementares aprovados para o backlog | Incluir novas issues para: (a) carga oficial dos desafios do Apêndice A e metas das 5 ODS; (b) validação/alerta de 3 a 5 desafios por curso (Art. 4º); (c) avisos oficiais, normas complementares e disparo real de e-mails (Cap. XI); (d) aceite/termo de ciência do regulamento (Art. 12º IV). | **Criar 4 novas issues** (rascunhos na Seção 4). |
| **D-10** | Papel de Coordenador de Curso (Art. 4º–6º) | **Fora do escopo do MVP.** Coordenadores atuam pelos papéis existentes (`ADMIN` / `TEACHER`). | Nenhuma issue; registrado na Seção 5. |

---

## 2. Alterações em Issues Existentes

### `#69` — `results: regras de finalistas, nota final, ranking, pontuação e certificados`
- **Atualizar P-29 e P-30:**
  - Finalistas: os **3 melhores `final_score` por curso** (`course_rank` 1..3), desempate pelo Art. 24º (Critério 1, depois Critério 4).
  - Premiação: **3 primeiros lugares por categoria no geral da edição** (Art. 26º — 6 premiados no total), usando a **média das `FinalEvaluation` com status `EVALUATED`**. Corrigir a descrição de `ProjectResult.category_rank` em `apps/results/models.py` (de *"dentro do curso"* para *"no geral da edição"*) e regenerar o DBML com `gen_dbml.py`.
- **Atualizar P-31:**
  - Fórmula confirmada: `final_score / 10 * 1.0` (1º período) ou `* 2.0` (2º+ período), com `term` congelado.
  - Conversão para conceitos de **Psicologia** (Art. 20º § 3º) adiada até a coordenação fornecer a tabela de menções.
- **Manter pendente (D-07):** P-34 e P-46 referentes a certificados (`#112`).

### `#110` — `results: nota final, ranking e finalistas (UC15)`
- Adicionar a regra corrigida da premiação (Art. 26º): `category_rank` e `award` (`1`, `2`, `3`) são calculados **por categoria no geral da edição** (entre os finalistas), a partir da **média das avaliações externas `EVALUATED`**.
- Incluir o caso de uso **`compute_awards`** ou referenciar uma issue filha dedicada. A rota (ex.: `POST /api/admin/editions/{edition_id}/awards/calculate`) não existe no contrato: entra por issue de decisão antes do `gen_openapi.py`.
- Especificar como o desempate do Art. 24º agrega as notas do Critério 1 e Critério 4 entre etapas (ex.: média simples ou soma ponderada das notas do critério nas etapas pontuadas).
- Atualizar o comentário/docstring de `ProjectResult.category_rank` em `apps/results/models.py`.

### `#111` — `results: pontuação dos alunos`
- Confirmar fórmula: `points = final_score / 10 * 1.0` (1º período) ou `* 2.0` (2º+ período).
- Adicionar **endpoint de consulta e exportação CSV** para o Admin (rota nova no contrato: issue de decisão antes do `gen_openapi.py`) (ex.: `GET /api/admin/editions/{edition_id}/student-scores` e `format=csv` ou `.../export`), contendo: matrícula, nome, curso, período congelado, indicador booleano **`is_last_year`** (`term > course.term_count - 2`, Art. 10º II e Art. 21º I), nota final do projeto e pontos calculados.
- Registrar nota explícita de que **Psicologia** recebe a pontuação numérica normalmente até definição da tabela institucional de menções (Art. 20º § 3º).

### `#112` — `results: certificados (UC17)`
- Adicionar nota no topo da issue: **Regras detalhadas de elegibilidade (Art. 27º/28º) pendentes de decisão futura (D-07)**:
  - Se 20h exige todas as etapas entregues (sem `ZERO_NO_SUBMISSION`);
  - Se finalista acumula 20h + 40h ou recebe apenas 40h;
  - Se haverá validação de inscrição no Portal do Aluno;
  - Se será incluído endpoint público de validação do `verification_code`.

### `#120` — `teams: listar e desclassificar equipes (UC13, UC40)`
- Adicionar regra de negócio em `disqualify_team`: ao marcar `Team.status = DISQUALIFIED`, atualizar também `Project.status = ProjectStatus.DISQUALIFIED` (caso a equipe já tenha projeto criado) dentro da mesma transação atômica.
- Registrar que a desclassificação manual pelo Admin cobre os casos dos Arts. 16º, 17º, 18º e 19º (inclusive desistência pós-formação que deixe a equipe com menos de 3 integrantes).

### `#125` — `editions: cadastrar desafios (UC05)`
- Registrar a decisão **D-03**: cada desafio permanece vinculado a **1 ODS principal** (`Challenge.sdg`); para os desafios do Apêndice A que mencionam duas ODS (Enfermagem e Medicina Veterinária), informar a 2ª ODS no campo `description`.

### `#127` — `editions: cadastrar critérios de avaliação (UC06)`
- Alinhar à decisão **D-02**: a rubrica segue as 4 faixas oficiais do Quadro 1 (`Insatisfatório: 0 a 2,5`, `Regular: 2,6 a 5,0`, `Bom: 5,1 a 7,4`, `Excelente: 7,5 a 10`).

### `#128` — `editions: cadastrar etapas e campos de entrega (UC07)`
- Registrar a decisão **D-06**:
  - As etapas **Ideia** (texto/cronograma/orçamento), **Protótipo Parcial** (vídeo 2–5 min) e **Momento Final** (Pitch 3–5 min) são modeladas como etapas `SUBMISSION` configuráveis com campos `FILE`/`LINK`/`CANVAS`/`SWOT`.
  - A **Entrega Preliminar** (mentoria presencial) pode ser registrada como marco informativo (ou etapa não pontuada sem campos obrigatórios), sem exigência de entrega digital.

### `#129` — `editions: critérios e pontuações da etapa (UC08)`
- Alinhar à decisão **D-02**: remover a restrição de que a soma dos `max_score` dos critérios deve igualar `Stage.max_score` (passa a depender da nova issue de refatoração da escala 0–10 por critério).

### `#130` — `editions: encerrar a edição e pré-carga (UC18)`
- Atualizar **P-18**: o texto oficial dos **7 critérios do Quadro 1** (com as 4 faixas) e das **2 categorias do Art. 2º** já está disponível no Regulamento (páginas 5, 9 e 10) e deve compor a pré-carga da edição.
  - Categorias padrão: `A) Protótipos e Artefatos` e `B) Processos, Protocolos, Metodologias e Ferramentas`.
  - Critérios padrão com `tiebreak_order`: item 1 (`tiebreak_order=1` — Observância das regras propostas), item 4 (`tiebreak_order=2` — Clareza e objetividade dos resultados), demais com `tiebreak_order=None`.

### Registro da D-02 (a `#179` foi fechada em 22/11)
- Registrar a **"Escala das notas"** como decidida no `docs/api/api-pendencias.md` (0 a 10 por critério, com conversão proporcional para `Stage.max_score`) e apontar para a Nova Issue 1.

---

## 3. Issues Fechadas para Reabrir ou Criar Retomada

### Retomada da `#122` — `editions: expor endpoints de cadastro, consulta e limites da edição (UC18, UC19)`
- **Motivo:** A `#122` foi fechada, mas na branch `developer` existem apenas os casos de uso (`create_edition`, `configure_team_limits`); `apps/editions/views.py` e `apps/editions/urls.py` só possuem as rotas de `evaluators`.
- **Endpoints pendentes (contrato em `docs/api/openapi.yaml`):**
  - `GET /api/admin/editions`
  - `POST /api/admin/editions`
  - `GET /api/admin/editions/{edition_id}`
  - `PATCH /api/admin/editions/{edition_id}`
- **Pronto quando:** Views, serializers, URLs, testes de contrato/API e CI verde.

### ~~Retomada da `#132`~~ — resolvida
- Os endpoints de ODS (`GET /api/sdgs`, `GET/POST /api/admin/sdgs`, `PATCH/DELETE /api/admin/sdgs/{sdg_id}`) voltaram para a `developer` com a #193 (cherry-pick da #164) em 22/11. Nenhuma issue nova.

*(Obs.: `#117` — `feat/teams-leadership`, PR #161 — está sem conflito com a `developer` desde 22/11 e aguarda aprovação. `#118` — `feat/teams-freeze-formation-period` — tem 4 commits à frente da `developer` e ainda não tem PR.)*

---

## 4. Rascunhos das Novas Issues para Criar

### Nova Issue 1 — `evaluations/editions: avaliar critérios na escala 0–10 do Quadro 1 com conversão proporcional para Stage.max_score`
- **App:** `editions`, `evaluations` · **Origem:** Regulamento Art. 22º (Quadro 1), D-02, `#179`
- **Objetivo:** Permitir que o professor avalie cada critério da etapa na escala **0 a 10** (seguindo as 4 faixas do Quadro 1: Insatisfatório `0–2,5`, Regular `2,6–5,0`, Bom `5,1–7,4`, Excelente `7,5–10`), convertendo a média dos critérios proporcionalmente para o valor da etapa (`Stage.max_score`), cuja soma na edição fecha em `10`.
- **Alterações necessárias:**
  - [ ] **Decisão de contrato antes do código:** `rubric`/`max_score` do critério e `points` do `EvaluationItem` (alinhados ao código na #191) mudam de significado; abrir a issue de decisão e a PR no `gen_openapi.py` primeiro.
  - [ ] Revisar `StageCriterion` e `apps/editions/rules.py`: tirar `ensure_criterion_fits_stage` (INT-02, entregue na #183) e manter `ensure_stage_max_score_fits` (INT-01, soma das etapas ≤ 10); cada critério aceita nota de `0` a `10` (ou `StageCriterion.max_score` padrão `10.00` / peso opcional).
  - [ ] Atualizar `evaluate_submission` e `EvaluationItem` para validar notas dos critérios de `0` a `10`.
  - [ ] Atualizar `recalculate_stage_score`: para cada avaliação finalizada, calcular a média dos critérios (`0..10`) e converter proporcionalmente: `(media_criterios / 10) * stage.max_score`; depois tirar a média entre os professores avaliadores.
  - [ ] Garantir que `StageScore.value` nunca ultrapasse `Stage.max_score`.
  - [ ] Atualizar testes de `editions` e `evaluations` e os testes de contrato (`apps/core/tests/contract.py`).
- **Pronto quando:** Testes unitários e de API cobrindo a conversão proporcional, validação `0..10` e CI verde.

---

### Nova Issue 2 — `teams/projects: tornar categoria obrigatória para equipe completa e envio de entrega`
- **App:** `teams`, `projects` · **Origem:** Regulamento Art. 2º e Art. 26º, D-06, `USO-07`
- **Objetivo:** Garantir que toda equipe escolha a categoria do projeto (`A` ou `B`) antes do encerramento da formação e antes de enviar entregas, pois a categoria é obrigatória para a premiação final.
- **Alterações necessárias:**
  - [ ] `apps/teams/rules.py` (`compute_unmet_requirements`): adicionar verificação `if project is None or not project.category_id: unmet.append("Projeto sem categoria.")`.
  - [ ] `apps/projects/rules.py` (`ensure_project_complete`): incluir `"category": project.category_id` nos campos obrigatórios para envio de entrega.
  - [ ] Atualizar testes em `apps/teams/tests/` e `apps/projects/tests/` (incluindo factories que criam entregas sem categoria).
- **Pronto quando:** Equipe sem categoria é marcada como incompleta no congelamento e bloqueada ao enviar entrega; CI verde.

---

### Nova Issue 3 — `editions/core: comando/seed oficial dos desafios do Apêndice A e metas das 5 ODS (Edição 2026)`
- **App:** `core`, `editions` · **Origem:** Regulamento p. 3–4 e Apêndice A (p. 14–19), D-03, D-09
- **Objetivo:** Disponibilizar carga estruturada (comando de management ou fixture/seed) com as **15 metas das 5 ODS** (p. 3–4) e os **38 desafios oficiais do Apêndice A** (p. 14–19; 47 registros de `Challenge` depois de duplicar os cursos agrupados) para a edição 2026, além dos 7 critérios do Quadro 1 e 2 categorias do Art. 2º.
- **Regras e pontos para confirmar antes de popular:**
  - [ ] **Metas das ODS (p. 3–4):** incorporar Metas 1.1–1.3, 2.1–2.3, 3.1–3.3, 9.1–9.3 e 16.1–16.3 na descrição da `Sdg` (ou campo estruturado, se necessário no painel público).
  - [ ] **Desafios com 2 ODS (D-03):** cadastrar sob 1 ODS principal e citar a 2ª ODS na `description` (Enfermagem: ODS 9 + ODS 3; Medicina Veterinária: ODS 2 + ODS 1).
  - [ ] **Cursos agrupados no Apêndice A:** duplicar o registro de `Challenge` para cada curso individual (`Agronomia` e `Zootecnia`; `Administração` e `Ciências Contábeis`; `Engenharia de Software` e `Inteligência Artificial`; confirmar quais cursos compõem `"Engenharias"`).
  - [ ] **Corrigir erros de digitação do PDF junto à coordenação:** Psicologia lista *"ODS 4 – Indústria, Inovação e Infraestrutura"* e *"ODS 5 – Paz, Justiça e Instituições Eficazes"* — mapear para **ODS 9** e **ODS 16**.
- **Pronto quando:** Comando idempotente testado, sem duplicar registros em reexecuções; CI verde.

---

### Nova Issue 4 — `editions: validar/alertar regra de 3 a 5 desafios por curso ao publicar edição (Art. 4º)`
- **App:** `editions` · **Origem:** Regulamento Cap. II — Art. 4º, D-09 · **Depende de:** `#123`, `#125`
- **Objetivo:** Refletir a regra do Art. 4º (*"elaborar de 3 a 5 desafios relacionados às ODS selecionadas por curso"*) na gestão de desafios e na publicação da edição.
- **Alterações necessárias:**
  - [ ] Regra em `apps/editions/rules.py` verificando, para cada curso ativo, a contagem de desafios ativos na edição (faixa esperada: `3` a `5`).
  - [ ] **Ponto de atenção:** no Apêndice A de 2026, Biomedicina e Farmácia têm apenas 2 desafios. Implementar como **validação configurável ou alerta/warning no retorno** (ou exigir confirmação explícita ao publicar com cursos fora da faixa `3..5`, para não travar a edição de 2026).
  - [ ] Impedir cadastro acima de 5 desafios ativos no mesmo curso/edição (ou avisar), conforme decisão final com a coordenação.
  - [ ] Testes de regra e API. Se a publicação passar a devolver alerta ou pedir confirmação, é mudança de contrato: issue de decisão antes do `gen_openapi.py`.
- **Pronto quando:** Regra coberta por testes e integrada à publicação (`#123`); CI verde.

---

### Nova Issue 5 — `notifications/public: avisos oficiais, normas complementares e disparo real de e-mails (Cap. XI)`
- **App:** `notifications`, `editions`, `public` · **Origem:** Regulamento Cap. XI (p. 13), D-09 · **Depende de:** `#133`, `#136`, `#137`
- **Objetivo:** Permitir que a equipe gestora publique **avisos oficiais e normas complementares** na página pública e envie **e-mails reais** para os participantes sobre avisos oficiais, resultados e eventos críticos.
- **Escopo sugerido:**
  - [ ] Model `EditionAnnouncement` (ou `OfficialNotice`): `edition`, `title`, `body`, `attachment_url` (para normas complementares/retificações), `published_at`, `created_by` (ADMIN).
  - [ ] Endpoints Admin: `POST/GET/PATCH/DELETE /api/admin/editions/{edition_id}/announcements`.
  - [ ] Endpoint Público: `GET /api/public/editions/{edition_id}/announcements` (e incluir na edição vigente).
  - [ ] Configurar backend SMTP real em `config/settings/production.py` (substituindo console backend) e serviço assíncrono/resiliente de envio de e-mail para avisos oficiais e publicação de resultados (falha no envio não pode quebrar a transação; registrar log).
  - [ ] Rotas novas no contrato: issue de decisão antes do `gen_openapi.py`; testes de contrato e de API.
  - [ ] O SMTP entra no `config/settings/production.py` da #99/#102 (envio de e-mail em produção já é pendência do `docs/contexto.md`).
- **Pronto quando:** Admin publica aviso/norma complementar, aparece no painel público e dispara e-mail configurável; CI verde.

---

### Nova Issue 6 — `accounts/teams: aceite de ciência do regulamento no cadastro (Art. 12º IV)`
- **App:** `accounts` e/ou `teams` · **Origem:** Regulamento Art. 12º IV, D-09
- **Objetivo:** Registrar formalmente que o acadêmico/líder tomou ciência e concordou com as normas do Regulamento do Projeto Desafio X.
- **Alterações necessárias:**
  - [ ] Adicionar campos de aceite com data/hora (ex.: `regulation_accepted_at` em `Team` na criação da equipe pelo líder e/ou em `TeamMember` quando o integrante aceita o convite/entra na equipe, ou em `Student` no autocadastro).
  - [ ] Exigir `accept_regulation: true` no payload de entrada correspondente, retornando `400` caso falso/ausente.
  - [ ] O campo `accept_regulation` muda o corpo de rotas existentes: issue de decisão antes do `gen_openapi.py`; depois migração, testes e DBML regenerado.
  - [ ] Observação: o Art. 12º IV dá ao Líder o dever de garantir a ciência do grupo; o aceite no sistema é escolha nossa, não exigência do regulamento.
- **Pronto quando:** Aceite persistido com timestamp, validado na API, contrato atualizado e CI verde.

---

## 5. Itens Explicitamente Fora do Escopo do MVP (e Adiados)

### Fora do escopo do MVP
- **Papel de Coordenador de Curso (`COORDINATOR`) / NDE / Colegiado (Art. 4º–6º):** coordenadores utilizam os papéis existentes (`ADMIN` ou `TEACHER`).
- **Exclusão consensual de integrante "a qualquer momento" (Art. 11º IV) e fluxo próprio de desistência pós-formação (Art. 18º):** casos excepcionais após o prazo de formação são tratados pelo Administrador (desclassificação pela `#120` ou ajuste administrativo).
- **Etapa de Entrega Preliminar com registro digital de mentoria (Quadro 2 — 07/04):** mantida apenas como marco informativo no cronograma, sem novo `StageKind` nem fluxo de feedback sem entrega.
- **Multi-ODS em `Challenge` (Apêndice A, p. 17 e 19):** mantida 1 ODS principal por desafio (`ForeignKey`), com a 2ª ODS citada na descrição.
- **Conversão automática para conceitos em Psicologia (Art. 20º § 3º):** adiada até a coordenação fornecer a tabela institucional de menções.

### Adiado para decisão futura
- **Regras detalhadas de Certificados (D-07 — Art. 27º, Art. 28º, `#112`):**
  - Critério de "todas as fases finalizadas" para 20h (`ZERO_NO_SUBMISSION` desqualifica para certificado?);
  - Acúmulo 20h + 40h vs. apenas 40h para finalistas;
  - Controle de inscrição no evento no Portal do Aluno;
  - Endpoint público de verificação de autenticidade por `verification_code`.

---

## 6. Pendências para Validar com a Coordenação (Inconsistências no PDF do Regulamento)

Antes de cadastrar os dados oficiais de 2026 (Nova Issue 3), confirmar com a coordenação:
1. **Psicologia (p. 18):** o PDF cita *"ODS 4 – Indústria, Inovação e Infraestrutura"* e *"ODS 5 – Paz, Justiça e Instituições Eficazes"* — confirmar correção para **ODS 9** e **ODS 16**.
2. **Psicologia (Art. 20º § 3º):** qual é a tabela oficial de conversão de pontos para menções/conceitos (para futura implementação).
3. **Biomedicina e Farmácia (p. 15):** possuem apenas 2 desafios no Apêndice A (contra 3 a 5 no Art. 4º) — confirmar se haverá mais desafios ou se 2 é aceito.
4. **Engenharias (p. 14):** os **3 desafios de Engenharias são idênticos aos 3 de Administração e Ciências Contábeis** (p. 15–16), inclusive o 1º, que cita *"ferramentas de Administração e Ciências Contábeis"*. Confirmar se foi colagem por engano e quais cursos de Engenharia estão ativos.
5. **Vídeos (Protótipo 2–5 min e Pitch — Cap. VIII II e III):** confirmar se serão entregues via **link externo** (YouTube/OneDrive/Drive, tipo `LINK`) ou upload de arquivo (`FILE`). **Recomendação: `LINK`.** A homologação e a produção (#99, #102) guardam as entregas no disco da instância (60 GB) com teto de 50 MB por arquivo (`DELIVERY_MAX_FILE_MB`); vídeos como `FILE` lotam o disco.
6. **Duração do Pitch:** o regulamento dá três números: Art. 9º II (*2 a 5 minutos*), Cap. VIII II, Parágrafo Primeiro (*até cinco minutos*) e Cap. VIII III (*3–5 minutos*). Confirmar qual vale; só importa se o sistema validar duração.
7. **Etapa Ideia × inscrição:** o Quadro 2 junta *"Ideia e Inscrição"* em 16/03, mesmo dia do fim das inscrições (Art. 13º). Confirmar se a Ideia é uma etapa `SUBMISSION` própria ou se o resumo do projeto (`title`/`summary`, RF30) já cumpre essa entrega.
