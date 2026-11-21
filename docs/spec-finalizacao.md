# Spec de finalização — Desafio X (backend + frontend)

Data-base: 20/11/2026. Prazo: **30/11/2026** (fim da Sprint 4). Rascunho para revisão: nada aqui foi aplicado nem fechado no GitHub.

Regras acordadas:
- O contrato (`docs/api/gen_openapi.py`) vence o frontend. Rota só do frontend sai do frontend, ou entra no gerador com aprovação do dono.
- Issue aberta cuja entrega já existe em código só é **listada** (seção 3). Quem fecha é o dono.
- Cada item vai para o dono do épico: #85 LCapistrano25, #86 ViniciusGGomes, #87 theokkkk1, #88 Viniciusgt39, #89 Shueiz.

Limites desta análise: o Google Doc de requisitos não foi lido (RF/UC vêm das issues, do guia e do `api-pendencias.md`), e as rotas "implementadas" foram medidas na branch `feat/100-final-form`, que está dessincronizada da `developer` (ver Q1).

---

## 1. Estado atual

### Backend — o que está feito
| Épico | Entregue |
|---|---|
| #85 | #90 padrões da API, #91 login com senha, #92 autocadastro aluno, #93 login Microsoft, #94 perfil professor, #95 avaliador externo, #96 avaliação do professor, #97 nota da etapa/zero automático, #98 retificação |
| #86 | #103 projeto, #105 categoria, #106 entrega com links, #107 upload |
| #88 | #143 (PR) edição e limites da equipe |
| #89 | #131 cursos, #132 ODS |
| #87 | código em branches (convites, solicitações, sair, liderança, congelamento) — issues ainda abertas |

### Backend — o que falta (por épico)
| Épico | Issues |
|---|---|
| #85 | #100 formulário final (em andamento), #101 avaliação do finalista, #99 homologação, #102 produção (PR #171 aberta), #49 domínios |
| #86 | #108 comprovante, #109 prorrogação, #170 Canvas/SWOT, #110 nota final/ranking/finalistas, #111 pontuação dos alunos, #112 certificados, #104 seed |
| #87 | #118 congelamento, #119 observações, #120 listar/desclassificar, #121 painel do acadêmico (e fechar #113–#117 se confirmadas, seção 3) |
| #88 | #122 (confirmar), #123 edital, #124 ODS da edição, #125 desafios, #126 categorias, #127 critérios, #128 etapas e campos, #129 critérios da etapa, #130 encerrar edição, #169 campos Canvas/SWOT |
| #89 | #133 edição vigente/anteriores/vencedores, #134 vitrine pública, #135 chamados, #136 e #137 notificações |

### Contrato × código
- OpenAPI: 85 caminhos. Branch atual: 38 rotas. Faltam cerca de 50, quase todas de editions, public, support, notifications, results, finalistas e admin de usuários/equipes.
- Rotas do frontend ausentes do contrato: `/api/me/dashboard`, `/api/teacher/dashboard`, `/auth/complete-profile`, `/auth/microsoft/mock`, `project/draft`, `invitations/{id}/cancel`, `join-requests/{id}/cancel`, `DELETE teams/{id}/members/{id}`, `member-notes/summary`.
- O frontend guarda uma cópia própria do OpenAPI (`docs/api/openapi.yaml`) que difere da do backend.

### Frontend
React 19 + Vite sobre MSW (`VITE_ENABLE_MOCKS`). Existem telas de login, equipe, entrega, painel público, professor e suporte, ainda contra mocks. Sem entrega: telas do avaliador externo (#17–#19) e do administrador (#20–#26, #140, #141).

---

## 2. Plano até 30/11

Ordem por dependência. Itens 1 e 2 destravam o resto.

### Fase A — Fundação (21 a 23/11)
1. **Sincronizar branches.** Mesclar as PRs prontas na `developer` (#161 liderança; #171 proxy/SSL), reapoiar a `feat/100-final-form` na `developer`. Dono: #85.
2. **Uma só cópia do OpenAPI.** O frontend passa a ler o do backend (script ou submódulo). Dono: #85 + frontend.
3. **Decidir as rotas só do frontend** (seção 4, Q2).

### Fase B — Backend que bloqueia telas (23 a 27/11)
1. **editions completo** (#123–#130, #169): sem ele não há edição publicada, e o resto (equipes, projeto, avaliação) depende dela. Dono: #88.
2. **teams restante** (#118–#121). Dono: #87.
3. **projects** (#108, #109, #170). Dono: #86.
4. **evaluations** (#100 e #101). Dono: #85.

### Fase C — Resultados e vitrine (27 a 29/11)
1. **results** (#110, #111, #112): depende de P-29, P-30, P-31 e P-46, ainda sem decisão. Dono: #86.
2. **public, support, notifications** (#133–#137). Dono: #89.
3. **seed de demonstração** (#104). Dono: #86.

### Fase D — Integração e entrega (28 a 30/11)
1. Trocar mocks por API real, perfil por perfil: aluno, professor, avaliador externo, administrador, público.
2. Homologação (#99) e produção (#102).
3. Fechamento: marcar P-xx resolvidas no `api-pendencias.md`, atualizar `docs/contexto.md`, fechar issues e épicos.

**Corte previsto.** Se a Fase B passar de 27/11, o corte vem nesta ordem: certificados (#112), pontuação dos alunos (#111), chamados (#135), observações (#119), Canvas/SWOT (#169, #170).

---

## 3. Issues abertas possivelmente cobertas por código (para você fechar)

| Issue | Evidência | Confirmar |
|---|---|---|
| #113 criar/consultar equipe | PR #152 mesclada | sim, após ver a `developer` |
| #114 convites | PR #153 mesclada | idem |
| #115 solicitar/responder entrada | PR #154 mesclada | idem |
| #116 sair da equipe | PR #155 mesclada | idem |
| #117 liderança | PR #161 **aberta** | só após o merge |
| #118 congelamento | branch `feat/teams-freeze-formation-period`, sem PR | só após PR |
| #122 edição e limites | PR #143 mesclada | sim |
| #98, #97, #96 | já fechadas | — |

Pendências do `api-pendencias.md` com código mas sem marcação: P-19, P-20, P-21 (prazo, etapa final, retificação) e P-46 (endpoint de retificação).

---

## 4. Perguntas em aberto (responda por número)

- **Q1 (respondida).** A `developer` não tem os commits de #97 (zero automático), #98 (retificação) e #100 (formulário final): as PRs #167 e #168 foram mescladas em branches empilhadas depois da #166. A `developer` tem #107, #155 e #166, que a branch atual não tem. A simulação de merge não deu conflito. Ação (Fase A): mesclar a `developer` na `feat/100-final-form`, rodar a CI e abrir a PR para a `developer`.
- **Q2 (respondida).** Decidir por rota conforme os dados: se `/api/me/dashboard` e `/api/teacher/dashboard` puderem ser montados com rotas do contrato (`teams`, `project`, `me/invitations`, `teacher/projects`), o frontend se adapta. Só entram no contrato se faltar dado. Demais rotas só do frontend seguem o contrato.
- **Q3a (respondida, P-29).** Finalistas **automáticos pela nota**, sem passo manual de seleção. Falta fixar o corte (quantos por categoria e curso) e quem homologa.
- **Q3b (P-30, sem preferência).** Proposta: `final_score` = soma dos `stage_score` das etapas pontuadas; o ranking da premiação usa a média das `final_evaluation` `FINALIZED`; desempate pelo Art. 24. Confirmar.
- **Q3c (P-31, sem preferência).** Proposta provisória: pontuação individual = nota final do projeto, com `considered_period` apenas registrado. Depende de ler o RF19 no Google Doc antes de implementar.
- **Q4.** P-16: a edição ganha o status `IN_PROGRESS`, ou fica SETUP, PUBLISHED, CLOSED?
- **Q5.** Homologação e produção: qual provedor, e quem tem acesso?
- **Q6.** Login Microsoft: o frontend usa `/auth/microsoft/mock`. Em produção precisa de registro do app no Azure. Já existe?
- **Q7.** Os donos dos épicos #86 a #89 têm capacidade para 10 dias? Se não, o que cortar primeiro além da lista acima?

---

## 5. Critérios de pronto

- Frontend sem MSW nos fluxos principais, e `openapi.yaml` único com `validate_openapi.py` passando.
- CI verde: `ruff check`, `ruff format --check`, `makemigrations --check`, `pytest`, `pip-audit`.
- Todo RF/UC com issue, endpoint e tela, ou marcado explicitamente como cortado.
- Pendências P-xx decididas ou marcadas como fora do escopo.
- Homologação no ar com o seed de demonstração.
