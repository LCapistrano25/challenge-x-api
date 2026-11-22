# Spec de Ação — Sábado, 21/11/2026

**Issue de referência:** #179 (`backend: pendências no código e decisões para fechar a sprint 4`, status `Em andamento`, branch `docs/179-plano-correcao-pendencias`)  
**Marcos:** Fechamento da Sprint 4 (**24/11/2026**) · Entrega final (**30/11/2026**)  
**Fontes:** `docs/spec-correcao-pendencias.md`, `docs/spec-finalizacao.md`, `docs/api/api-pendencias.md` e estado atual das PRs/issues em 20/11/2026.

---

## Objetivo do dia

1. **Destravar a fila de merges** (`main` e `developer`), eliminando conflitos e fechando as PRs já implementadas.
2. **Corrigir os bugs críticos de código** levantados na auditoria antes que novos módulos (`results`, `support`, `editions`) dependam deles.
3. **Fechar as decisões de negócio e infraestrutura da #179** com a equipe/professor para liberar a reta final da Sprint 4 sem retrabalho.

---

## Bloco 1 — Manhã: Destravamento de PRs e sincronização de branches

Ordem de execução baseada nas dependências reais das PRs abertas:

| Ordem | PR | Branch → Base | Estado atual (20/11) | Ação para 21/11 |
|---|---|---|---|---|
| 1 | **#171** | `fix/production-ssl-proxy` → `main` | `MERGEABLE`, CI verde | Revisão de `@ViniciusGGomes` e merge na `main`; depois atualizar `developer` com `main` |
| 2 | **#172** | `feat/97-stage-score-zero` → `developer` | **`CONFLICTING`** | Rebase/merge com `origin/developer` (considerando #173 e #174 já mescladas), rodar suíte e liberar para revisão |
| 3 | **#175** | `feat/49-email-domains` → `developer` | `MERGEABLE`, CI verde | Revisão e merge na `developer` |
| 4 | **#176** | `docs/67-registrar-decisoes-prazo-retificacao` → `developer` | `MERGEABLE`, CI verde | Revisão e merge na `developer` |
| 5 | **#177** | `feat/66-teams-criacao-com-convites` → `developer` | `MERGEABLE`, CI verde | Revisão e merge na `developer` |
| 6 | **#178** | `feat/169-editions-canvas-swot` → `feat/66-...` | `DRAFT` | Após merge da #177, trocar base para `developer`, tirar de `DRAFT`, validar CI e mesclar |
| 7 | **#180** | `feat/170-projects-canvas-swot-entrega` → `feat/169-...` | `DRAFT` | Após merge da #178, trocar base para `developer`, tirar de `DRAFT`, validar CI e mesclar |
| 8 | **#161** | `feat/teams-leadership` → `developer` | **`CONFLICTING`**, `CHANGES_REQUESTED` | Checar com `@theokkkk1` se #177 já cobre ou se precisa resolver conflitos e ajustar; mesclar ou fechar para destravar #117 |

### Higiene de repositório (junto ao Bloco 1)
- [ ] Conferir e fechar os checklists das issues **#100** e **#101** (PRs #173 e #174 já mescladas) e validar pendências de banca (**P-32**).
- [ ] Decidir o destino dos arquivos locais não rastreados no working tree (`docs/spec-finalizacao.md`, `docs/api/mudancas-frontend.md` e `Claude outputs/`), versionando os docs úteis em branch própria ou limpando os temporários.

---

## Bloco 2 — Tarde: Correções críticas de código e robustez da API

Foco nos itens de maior impacto de integridade e segurança de `docs/spec-correcao-pendencias.md` e `#179` (em branches dedicadas a partir de `developer` atualizada):

### Prioridade 1 — Bugs críticos e regra de segurança
- [ ] **BUG-01 — Race condition na versão da entrega** (`apps/projects/use_cases/submit_stage_delivery.py`)  
  Aplicar `select_for_update` no `Submission` (além da trava em `Team`) para impedir colisão de `unique_submission_version_number` em envios concorrentes. Adicionar teste de concorrência/regressão.
- [ ] **BUG-05 — `rectify_score` sem validação de admin** (`apps/evaluations/use_cases/rectify_score.py`)  
  Adicionar `ensure_actor_is_admin(actor)` no início do caso de uso e cobrir com teste de permissão (403 para não-admin).
- [ ] **BUG-02 — Saída de equipe durante janela extra** (`apps/teams/use_cases/leave_team.py`)  
  Rejeitar saída quando `team.formation_extended_until` estiver no futuro, garantindo a regra de negócio da janela extra de 48 h.

### Prioridade 2 — Pendências de código da #179 e integridade
- [ ] **Resposta JSON no erro 400 acima de 2,5 MB (`DATA_UPLOAD_MAX_MEMORY_SIZE`)**  
  Capturar `RequestDataTooBig` / erro de payload no handler padrão da API para retornar o formato `{"error": {"code", "message", "details"}}` em vez de HTML.
- [ ] **Revisão dos comentários `shortcut:` no código**  
  Listar todos os `shortcut:` atuais (prazos de 24 h / 48 h em `teams`, limites de Canvas/SWOT, deleção em massa de `EditionSdg` — **BUG-03**), decidir o que é aceito até 24/11 e abrir issues específicas para o que ficar para depois.
- [ ] **Trava de soma de notas (INT-01 e INT-02)** *(se o Bloco 1 e os bugs acima fecharem cedo)*  
  Validar no `publish_edition` / configuração da etapa que `sum(Stage.max_score) == 10` (nas pontuadas) e `sum(StageCriterion.max_score) == Stage.max_score`.

---

## Bloco 3 — Fim do dia: Decisões da #179, Documentação e Alinhamento

### 1. Reunião rápida / alinhamento assíncrono (decisões que bloqueiam a semana)
- [ ] **Canvas e SWOT (P-47):** confirmar com o professor os nomes dos blocos, os limites (`5000` caracteres / `20` itens por quadrante) e atualizar **RF07** e **RF31** no documento de requisitos.
- [ ] **Escala das notas e cálculo final (P-29, P-30, P-31):** bater o martelo sobre a escala (0 ou 1 a 10), confirmação dos N finalistas automáticos por curso, fórmula de `final_score` e fórmula de `StudentScore` para destravar `#110`, `#111`, `#112` com `@ViniciusGGomes`.
- [ ] **Infraestrutura e Deploy (`#99`, `#102`, P-43, SEC-02):** definir provedor de homologação e produção, storage dos arquivos de entrega, cache compartilhado para rate limit e confirmar registro do app no Azure (`MICROSOFT_TENANT_ID`).
- [ ] **Check de capacidade dos épicos (`#86`–`#89`):** alinhar com `@ViniciusGGomes`, `@theokkkk1`, `@Viniciusgt39` e `@Shueiz` o ritmo das issues `A fazer` (especialmente `editions` `#123–#130`, que bloqueia todo o fluxo fim a fim) e confirmar a ordem de corte caso necessário (`#112` → `#111` → `#135` → `#119` → `#169/#170`).

### 2. Documentação e contrato com o Frontend
- [ ] **Atualizar `docs/api/api-pendencias.md` (Fase 1):** marcar como resolvidas **P-19**, **P-20**, **P-27**, **P-47** (ressalva dos nomes) e os itens já decididos/implementados (**P-01, P-02, P-03, P-05, P-11, P-14, P-15, P-16, P-17, P-24, P-33, P-38, P-39, P-40, P-42, P-43**) na branch `docs/179-plano-correcao-pendencias`.
- [ ] **Sincronizar contrato com o Frontend:** revisar `docs/api/mudancas-frontend.md`, definir estratégia de fonte única do `openapi.yaml` e fechar a decisão sobre rotas exclusivas do frontend (`/api/me/dashboard`, `/api/teacher/dashboard`, etc.).

---

## Critérios de pronto para o fim de 21/11

- [ ] `main` atualizada com a #171 e `developer` com #172, #175, #176 e #177 mescladas (e #178/#180 destravadas ou mescladas).
- [ ] Nenhuma PR aberta em estado `CONFLICTING`.
- [ ] Correções de **BUG-01**, **BUG-05**, **BUG-02** e erro 400 JSON implementadas com testes e CI verde (`ruff`, `pytest`, `makemigrations --check`).
- [ ] Decisões da **#179** registradas em `docs/api/api-pendencias.md` (ou descartadas com justificativa) e issues filhas abertas para itens que ficarem pós-sprint.
