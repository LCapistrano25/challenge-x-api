# Spec de correção de pendências e auditoria da API

Data-base: 20/11/2026. Referência: `docs/api/api-pendencias.md`, código da branch `feat/170-projects-canvas-swot-entrega`.

---

## Parte 1 — Correção das pendências existentes

### Pendências resolvidas no código mas não marcadas

| ID | Evidência | Ação |
|---|---|---|
| P-19 | `Stage.evaluation_ends_at` com CHECKs `stage_scored_has_evaluation_deadline` e `stage_evaluation_after_submission` | Marcar resolvida |
| P-20 | CHECK `stage_final_not_scored` no banco | Marcar resolvida |
| P-27 | `get_delivery_status` em `projects/selectors.py`; status derivado sem persistir | Marcar resolvida |
| P-47 | `FieldKind.CANVAS`/`SWOT`, validadores em `projects/rules.py`, `SubmissionItem.content`, CHECK `submission_field_canvas_swot_without_file_options` | Marcar resolvida (a confirmação dos nomes dos blocos com o professor continua em aberto) |

### Pendências de alta severidade — plano de resolução

#### P-01 — Campos nativos do Django em `users`

**Situação:** o `User` herda de `AbstractUser` e mantém `last_login`, `is_superuser`, `is_staff`, `groups` e `user_permissions`. O DBML não os lista, mas o código precisa deles (admin, login).

**Decisão proposta:** aceitar os campos nativos como estão. Atualizar o DBML para incluí-los com comentário "campos do framework, não expostos na API". Nenhum endpoint expõe esses campos. Sem impacto no contrato.

**Esforço:** documentação, sem código.

#### P-06 — Status de chamados divergentes

**Situação:** `support_ticket` não existe no código. Os requisitos pedem em análise, atendido, recusado; o DBML tem `OPEN`, `IN_PROGRESS`, `WAITING_USER`, `RESOLVED`, `CLOSED`.

**Decisão proposta:** simplificar para o que os requisitos exigem.

```python
class TicketStatus(models.TextChoices):
    OPEN = "OPEN", "Pendente"            # criado pelo usuário
    IN_PROGRESS = "IN_PROGRESS", "Em análise"  # admin pegou
    RESOLVED = "RESOLVED", "Atendido"
    REFUSED = "REFUSED", "Recusado"      # com justificativa obrigatória
```

Sem `WAITING_USER` (P-08: não há canal de resposta) e sem `CLOSED` (atendido = fechado). Transições permitidas: `OPEN → IN_PROGRESS → RESOLVED|REFUSED`. Campo `response` obrigatório em `RESOLVED` e `REFUSED`.

**Esforço:** 1 model, 1 use case, 1 view, 1 migração, testes.

#### P-29 — Seleção de finalistas

**Situação:** `ProjectResult.finalist` existe, `ProjectResult.course_rank` existe, mas nenhum caso de uso preenche.

**Decisão proposta (Q3a):** finalistas automáticos pela nota. Os N melhores `final_score` por curso (N configurável na edição, default 3) viram `finalist = True`. O admin homologa, não seleciona. Use case `compute_results` calcula `final_score`, ordena e marca.

**Dependência:** P-30 (a fórmula da nota final).

**Esforço:** 1 campo `Edition.finalists_per_course` (default 3), 1 use case `compute_results`, testes.

#### P-30 — Nota final, ranking e premiação

**Situação:** `ProjectResult.final_score`, `course_rank`, `category_rank` e `award` existem sem caso de uso.

**Decisão proposta (Q3b):**
- `final_score` = soma dos `StageScore.value` das etapas pontuadas (`scored = True`, `kind = SUBMISSION`), só com status `DEFINITIVE`. Etapa sem nota definitiva impede o cálculo (projeto fica sem `final_score`).
- Ranking do curso: `course_rank` ordenado por `final_score` DESC dentro do curso do desafio.
- Ranking de premiação: `category_rank` ordenado pela média das `FinalEvaluation` `EVALUATED` dentro de (curso, categoria). Top 3 recebem `award = 1, 2, 3`.
- Desempate (Art. 24): por critério de `tiebreak_order` mais alto entre os `StageCriterion`.

**Esforço:** 1 use case `compute_results` (junto com P-29), 1 use case `compute_awards`, testes.

#### P-31 — Pontuação individual

**Situação:** `StudentScore` com `term`, `points` e `calculated_at` existe sem caso de uso.

**Decisão proposta (Q3c):** `points = final_score / 10 × fator`, onde fator = 1.0 para 1º período e 2.0 para demais. `term` é congelado no cálculo a partir de `Student.term`.

**Esforço:** 1 use case `compute_student_scores`, testes.

#### P-46 — Certificados e endpoints de resultados

**Situação:** `CertificateTemplate`, `Certificate`, `CertificateKind` existem. Faltam tipos (P-34) e use cases.

**Decisão proposta:**
1. Adicionar tipos: `TEACHER = "TEACHER"` e `EVALUATOR = "EVALUATOR"`.
2. Elegibilidade: Participação = todo aluno de equipe ativa; Finalista = `ProjectResult.finalist`; Premiação = `award IS NOT NULL`; Professor = `TeacherCourse.active` na edição; Avaliador = `EditionReviewer`.
3. Endpoints: `POST /api/admin/editions/{id}/results/calculate` (P-29 + P-30 + P-31), `POST /api/admin/editions/{id}/results/homologate`, `POST /api/admin/editions/{id}/certificates/issue`.

**Esforço:** migração para os tipos, 3 use cases, 3 views, testes. É o maior bloco de trabalho pendente.

### Pendências de média severidade — plano de resolução

| ID | Decisão proposta | Esforço |
|---|---|---|
| P-02 | Já resolvida na prática: o código usa `STUDENT`/`TEACHER`/`term`/`registration_number`. Marcar e atualizar o contrato de auth | Doc |
| P-03 | Sessão com CSRF já implementada (#91); expiração por `SESSION_COOKIE_AGE` = 1800s com renovação; sem JWT. Marcar resolvida | Doc |
| P-05 | Manter duas rotas (criação + vínculo) como está implementado em `register_external_reviewer` + `link_reviewer_to_edition`. Marcar resolvida | Doc |
| P-07 | Campo `response` único, sem histórico. O admin justifica a recusa no mesmo campo. Aceitar a limitação | Doc |
| P-08 | Sem `WAITING_USER`. Se necessário no futuro, abre issue nova | Doc |
| P-10 | Só aluno e professor abrem; só ADMIN atende. Validar no use case | 1 regra |
| P-13 | Ao completar autocadastro, associar convites pendentes pelo e-mail e gerar notificação. Ajustar `register_student` | 10 linhas |
| P-16 | Sem `IN_PROGRESS`. A edição fica SETUP → PUBLISHED → CLOSED. Marcar resolvida (já é o `EditionStatus` atual) | Doc |
| P-18 | Critérios e categorias padrão como seed na migração de dados da edição. Texto a confirmar com o professor | 1 migração |
| P-26 | Remover `SUBMITTED`, `UNDER_EVALUATION`, `APPROVED`, `REJECTED` do `ProjectStatus`. Manter `IN_PROGRESS`, `COMPLETED`, `DISQUALIFIED`. Status de avaliação é derivado | 1 migração |
| P-32 | Banca = finalistas dentro da abrangência (`EditionReviewer.course_id`). Sem tabela de alocação extra | Doc |
| P-34 | Adicionar `TEACHER` e `EVALUATOR` ao `CertificateKind`. Remover unicidade `(edition, kind)` e trocar por `(edition, kind, user)` em `Certificate` | 1 migração |
| P-41 | "Edição vigente" = única com status `PUBLISHED`. Se mais de uma, pegar a mais recente. Sem campo extra | 1 selector |
| P-42 | `profile_completed` derivado de `has_role_profile(user)` na resposta do login. Já funciona assim | Doc |
| P-43 | JSON para links, multipart para arquivos. Já implementado em `submit_stage_delivery`. Edital e certificado ficam para a task de produção | Doc |
| P-44 | Feedbacks sem nome do professor (padrão). Serializer de `Evaluation` para aluno omite `teacher` | 1 serializer |

### Pendências de baixa severidade — triagem rápida

| ID | Ação | Esforço |
|---|---|---|
| P-09 | Sem campo de tipo nem prioridade. Fora do escopo da Sprint 4 | — |
| P-11 | API segue o DBML: `title` e `support_response`. Marcar resolvida | Doc |
| P-12 | `resolved_at` preenchido em `RESOLVED` e `REFUSED`, nulo nos demais. CHECK no model | 1 constraint |
| P-14 | Formato do link é rota do frontend (`/equipes/{id}`). Já usado assim nas notificações | Doc |
| P-15 | `PROTECT` em todas as FKs de usuário (já é o padrão). Marcar resolvida | Doc |
| P-17 | Curso sem `slug`. O "código/sigla" do RF03 é o nome do curso. Marcar resolvida | Doc |
| P-24 | O ex-líder que transferiu e não saiu continua como MEMBER ativo. Sem conflito entre RF28 e RF40 | Doc |
| P-28 | Público = edições `CLOSED`, equipe não desclassificada, `ProjectResult` existente. Implementar no selector da vitrine | 1 selector |
| P-33 | `PARTIAL` não existe no `ScoreStatus`. Só `PENDING` e `DEFINITIVE`. Marcar resolvida | Doc |
| P-35 | Notícias e canal de dúvidas fora do escopo. Conteúdo estático no frontend | — |
| P-36 | Referências quebradas nos requisitos: reportar ao dono do documento | — |
| P-38 | Paginação já implementada. Marcar resolvida | Doc |
| P-39 | Decimais como string é o padrão do DRF. Manter | Doc |
| P-40 | 400 para validação, 409 para regra. Sem 422. Marcar resolvida | Doc |
| P-45 | `{"confirm": true}` no encerramento: implementar no use case `close_edition` | 3 linhas |

### Ordem de execução

| Fase | Itens | Dependência |
|---|---|---|
| 1. Doc | Marcar P-01, P-02, P-03, P-05, P-07, P-08, P-11, P-14, P-15, P-16, P-17, P-24, P-27, P-33, P-38, P-39, P-40, P-42, P-43, P-47 como resolvidas | Nenhuma |
| 2. Chamados | P-06 (model + use case + view + testes) | Nenhuma |
| 3. Resultados | P-30 → P-29 → P-31 (compute_results, compute_awards, compute_student_scores) | Etapas com nota definitiva |
| 4. Certificados | P-34 → P-46 (tipos + issue_certificates) | Fase 3 |
| 5. Ajustes | P-10, P-12, P-13, P-26, P-28, P-44, P-45 | Nenhuma entre si |

---

## Parte 2 — Auditoria: falhas, bugs e problemas de usabilidade

### Bugs encontrados

#### BUG-01 — Race condition no número da versão da entrega (Crítico)

**Arquivo:** `apps/projects/use_cases/submit_stage_delivery.py:91`

```python
last = submission.versions.aggregate(last=Max("number"))["last"] or 0
version = SubmissionVersion.objects.create(submission=submission, number=last + 1, ...)
```

O `select_for_update` trava a `Team`, mas o `Submission` é criado por `get_or_create` sem trava. Dois envios simultâneos do mesmo projeto podem ler o mesmo `last` e tentar criar a mesma `number`, causando `IntegrityError` pela constraint `unique_submission_version_number`.

**Correção:** trocar `get_or_create` por `select_for_update` no `Submission` também, ou usar `F('number') + 1` com `UPDATE ... RETURNING`.

#### BUG-02 — `leave_team` não verifica a janela extra antes de permitir saída

**Arquivo:** `apps/teams/use_cases/leave_team.py:72-75`

```python
formation_stage = get_open_formation_stage(team.edition, now)
if formation_stage is None:
    raise LeaveTeamRejected(...)
```

Se a equipe tem `formation_extended_until` no futuro (janela extra), mas a `formation_stage` já acabou, a saída é rejeitada. Porém a regra diz que "ninguém sai durante a janela extra". Atualmente, se a etapa de formação ainda está aberta E a equipe tem janela extra, a saída é permitida — a regra de "ninguém sai durante a janela" não está implementada.

**Correção:** adicionar check: se `team.formation_extended_until` está no futuro, rejeitar a saída.

#### BUG-03 — `EditionSdg.delete()` não protege contra `queryset.delete()`

**Arquivo:** `apps/editions/models/edition.py:64-68`

```python
def delete(self, *args, **kwargs):
    ensure_sdg_not_used_by_challenges(self.edition_id, self.sdg_id)
    return super().delete(*args, **kwargs)
```

O comentário reconhece o problema (`shortcut: queryset.delete() não passa por aqui`), mas se o admin usar um bulk action ou se qualquer código chamar `EditionSdg.objects.filter(...).delete()`, a regra é ignorada e ODS usadas por desafios são apagadas sem erro.

**Correção:** mover a regra para o use case de remoção de ODS. Ou adicionar um `pre_delete` signal (exceção justificada: protege integridade).

#### BUG-04 — `ensure_actor_is_team_leader` compara `student_id` com `actor.pk`

**Arquivo:** `apps/projects/rules.py:88-96`

```python
members.filter(team=team, student_id=actor.pk, role="LEADER", active=True).exists()
```

`actor` é um `User`, mas `student_id` aponta para `Student` (cuja PK é o `user_id` por ser `OneToOneField` com `primary_key=True`). Funciona **por coincidência** porque `Student.pk == User.pk`. Se isso mudar (ex: `Student` ganhar PK auto), a regra quebra silenciosamente.

**Correção:** trocar `actor.pk` por `actor.student.pk` ou `actor.pk` com comentário explícito dizendo que `Student.pk == User.pk` por design.

#### BUG-05 — `rectify_score` não verifica que o actor é admin

**Arquivo:** `apps/evaluations/use_cases/rectify_score.py:14-15`

A docstring diz "Levanta ValidationError se o actor não for admin", mas o código não tem nenhum `ensure_actor_is_admin(actor)`. A constraint `limit_choices_to={"role": UserRole.ADMIN}` em `rectified_by` só funciona no admin Django, não na API.

**Correção:** adicionar `ensure_actor_is_admin(actor)` como primeira linha.

### Falhas de segurança

#### SEC-01 — Falta de rate limiting no login com senha

**Arquivo:** `apps/accounts/rules.py:101-108`

O login com senha (`ensure_password_login_allowed`) não tem throttling além do que o DRF oferece por padrão. Um atacante pode tentar força bruta contra contas de admin e avaliadores externos (os únicos que usam senha).

**Correção:** adicionar `EmailRateThrottle` no `LoginView` (já existe a classe em `apps/accounts/views/`; confirmar que está configurada na view).

#### SEC-02 — `microsoft_id` previsível permite account takeover

**Arquivo:** `apps/accounts/models.py:46`

O `microsoft_id` (OID do Azure) é aceito como verdade absoluta em `authenticate_microsoft_user`. Se um atacante obtiver o OID de outro usuário (são GUIDs, não secretos), não há segunda verificação.

**Mitigação:** o `microsoft_id` só é escrito por `authenticate_microsoft_user`, que valida o token com a Microsoft. O risco é baixo enquanto a validação do token estiver correta. Verificar que o tenant é validado (`MICROSOFT_TENANT_ID`).

#### SEC-03 — Upload de arquivo sem limite total por equipe

**Arquivo:** `apps/projects/rules.py:329-357`

O `ensure_file_matches_field` limita o tamanho por arquivo (`DELIVERY_MAX_FILE_MB` e `field.max_size_mb`), mas não há limite total por equipe. Uma equipe pode enviar versões infinitas, cada uma com arquivos no limite máximo, até encher o disco.

**Correção:** adicionar um limite total por equipe ou por etapa (ex: 500 MB por etapa). Ou limitar o número de versões por etapa.

### Problemas de usabilidade da API

#### USO-01 — Erros genéricos demais no `validation_error`

Quando a avaliação falha (ex: prazo encerrado, avaliação já finalizada, sem entrega válida), tudo sai como `400 validation_error` com a mensagem em `details`. O frontend não consegue diferenciar programaticamente entre "prazo encerrado" e "campo obrigatório faltando" para mostrar UIs diferentes.

**Sugestão:** usar códigos de erro específicos (como `evaluation_deadline_closed`) em vez de `ValidationError` do Django para erros de regra de negócio dentro do `evaluate_submission`. Seguir o padrão que `submit_stage_delivery` já usa (exceções com `code`).

#### USO-02 — Sem endpoint para consultar a edição vigente

A `P-41` define "edição vigente" como a única `PUBLISHED`, mas não existe um `GET /api/editions/current` que devolva os dados dela. O frontend precisa listar todas e filtrar. O painel público (`GET /api/public/editions/current`) existe no contrato mas não no código.

**Sugestão:** criar um selector `get_current_edition()` e um endpoint `GET /api/editions/current` que devolve 404 se não houver.

#### USO-03 — Painel do professor sem paginação

**Arquivo:** `apps/evaluations/selectors.py:14-108`

O `list_teacher_rows` carrega todos os projetos e etapas em memória (`shortcut` comentado). Com centenas de projetos e múltiplas etapas, a resposta pode ficar lenta e pesada.

**Risco:** uma edição com 100 equipes e 3 etapas gera 300 linhas, cada uma com project, team, challenge, course — são ~600 queries sem otimização (apesar do `select_related`, as `sent_at` e `extensions` são consultas separadas). Aceitável para o MVP.

**Sugestão futura:** paginação no banco com `Subquery` para delivery_status.

#### USO-04 — Sem endpoint de histórico de retificações

A `ScoreRectification` guarda o histórico imutável de ajustes (RF14), mas não existe endpoint para o admin ou o aluno consultarem as retificações de uma avaliação. A informação existe no banco mas não é acessível pela API.

**Sugestão:** `GET /api/admin/evaluations/{id}/rectifications` (admin) e incluir um flag `rectified` no `StageScore` que o aluno vê.

#### USO-05 — Sem endpoint de dashboard do aluno

O contrato prevê `GET /api/me/dashboard`, mas não existe no código. O aluno não tem uma visão consolidada de: equipe, projeto, entregas pendentes, notas, situação. Precisa fazer múltiplas chamadas.

**Sugestão:** um selector que agrega equipe + projeto + entregas + notas numa resposta só.

#### USO-06 — Notificação sem link para a ação

As notificações usam `link = "/equipes/{id}"`, que é uma rota do frontend. Se a estrutura de rotas do frontend mudar, todas as notificações antigas ficam com links quebrados.

**Sugestão:** guardar uma referência estruturada (`entity_type` + `entity_id`) e deixar o frontend montar a URL. Ou aceitar o acoplamento e documentar.

#### USO-07 — `compute_unmet_requirements` não verifica categoria

**Arquivo:** `apps/teams/rules.py:42-63`

A função calcula requisitos não atendidos (RF51), mas não verifica se o projeto tem categoria selecionada. O RF51 pode exigir categoria.

**Sugestão:** confirmar com o RF51 se a categoria é requisito para a equipe estar completa. Se sim, adicionar ao check.

#### USO-08 — Sem soft delete de equipe desclassificada

Quando uma equipe é desclassificada, o `Team.status` muda para `DISQUALIFIED`, mas os integrantes continuam `active = True`. Eles não conseguem criar outra equipe (constraint `unique_active_team_per_edition`), ficando presos na edição.

**Sugestão:** decidir se a desclassificação libera os integrantes. Se sim, o use case `disqualify_team` deve desativar os membros.

### Riscos de integridade de dados

#### INT-01 — Soma dos `max_score` das etapas pode não fechar em 10

Não há CHECK nem regra impedindo que a soma dos `Stage.max_score` das etapas pontuadas de uma edição ultrapasse ou fique abaixo de 10. O `final_score` (soma dos `StageScore.value`) pode ultrapassar 10 ou ficar abaixo, violando a constraint `project_result_final_score_0_to_10`.

**Correção:** adicionar validação no use case `create_stage` ou no `publish_edition`: antes de publicar, a soma dos `max_score` das etapas pontuadas deve ser exatamente 10.

#### INT-02 — `recalculate_stage_score` pode dar nota > `max_score` da etapa

**Arquivo:** `apps/evaluations/use_cases/recalculate_stage_score.py:36-38`

A média é calculada a partir da soma dos `EvaluationItem.points`, que são limitados individualmente pelo `max_score` do critério. Mas se a soma dos `max_score` dos critérios for maior que o `max_score` da etapa, a nota média pode ultrapassar o limite da etapa.

**Correção:** adicionar validação na configuração da etapa: a soma dos `StageCriterion.max_score` deve ser igual ao `Stage.max_score`. Ou truncar a nota ao `max_score` da etapa.

#### INT-03 — Zero automático sem caso de uso implementado

O `ScoreStatus.ZERO_NO_SUBMISSION` existe e a constraint `stage_score_value_matches_status` o permite, mas não existe caso de uso `apply_zero_for_missing_submission`. Equipes que não entregam nunca recebem nota zero — o `StageScore` simplesmente não é criado.

**Correção:** implementar o comando `manage.py apply_zero_scores` que, depois do prazo de cada etapa, cria `StageScore(value=0, status=ZERO_NO_SUBMISSION)` para projetos sem entrega válida.

#### INT-04 — `freeze_formation_period` não implementado

Mencionado no guia como caso de uso que o sistema precisa, mas não existe. As equipes nunca têm a `situation` preenchida (`COMPLETE`, `INCOMPLETE`, `REQUIREMENTS_NOT_MET`), o que impede o bloqueio de entregas por `ensure_team_not_incomplete`.

**Correção:** implementar `manage.py freeze_formation` conforme descrito no guia (issue #118).

---

## Parte 3 — Resumo de prioridades

### Crítico (bloqueia funcionalidade ou perde dados)

1. **BUG-01** — Race condition na versão da entrega
2. **BUG-05** — Retificação sem checar admin
3. **INT-03** — Zero automático não implementado
4. **INT-04** — Congelamento de formação não implementado

### Alto (necessário para a entrega da Sprint 4)

5. **P-30 + P-29** — Nota final e finalistas
6. **P-31** — Pontuação individual
7. **P-46 + P-34** — Certificados
8. **P-06** — Chamados
9. **INT-01** — Soma dos max_score deve fechar em 10
10. **INT-02** — Soma dos critérios deve fechar no max_score da etapa

### Médio (melhora a qualidade)

11. **BUG-02** — Saída durante janela extra
12. **BUG-03** — `EditionSdg.delete()` em queryset
13. **BUG-04** — `student_id` vs `actor.pk`
14. **SEC-01** — Rate limiting no login
15. **SEC-03** — Limite total de uploads
16. **USO-01** — Erros genéricos na avaliação
17. **USO-02** — Endpoint de edição vigente
18. **USO-05** — Dashboard do aluno

### Baixo (pode esperar)

19. **USO-03** — Paginação do painel do professor
20. **USO-04** — Endpoint de retificações
21. **USO-06** — Links nas notificações
22. **USO-07** — Categoria no `compute_unmet_requirements`
23. **USO-08** — Desclassificação e liberação de membros
24. As 15+ pendências de documentação da Fase 1
