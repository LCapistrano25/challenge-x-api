# Plano — manter as decisões de 24/11 e corrigir nos merges

Data-base: 25/11/2026, `developer` em `1166905` (#221 mesclada).

## Regra do plano

1. **Decisão só vale registrada no repositório.** As decisões de 24/11 estão na seção 0 do `docs/decisoes-regulamento.md` e no `docs/api/api-pendencias.md`. Quem revisa uma PR confere ali.
2. **PR que fere decisão não entra sem a correção.** Correção pequena: o autor ajusta antes do merge. Correção que depende de outra PR: mescla e abre a PR de correção logo em seguida, já anotada aqui.
3. **Mudança de contrato:** issue de decisão → `gen_openapi.py` → YAML regenerado. Nunca só no código.
4. Ao fechar cada item, marcar `[x]` aqui.

## Passo 0 — registrar as decisões (antes de qualquer merge)

- [x] Versionar o `docs/decisoes-regulamento.md` com o resultado de 24/11 (D-01 a D-10, desempate, chamados, convite, PATCH de equipe, certificados adiados).
- [x] No `docs/api/api-pendencias.md`: marcar como resolvidas P-06, P-07, P-08, P-10, P-12 (chamados), P-29 (finalistas), P-30 (pódio por categoria, D-02, desempate) e P-31 (fora do escopo, D-04); P-34 adiada (D-07).
- [x] Uma issue por decisão ainda não aplicada (lista do passo 2), linkada à #217: #228 a #234.

## Passo 1 — ordem de merge das PRs abertas

| Ordem | PR | Situação | O que fazer no merge |
|---|---|---|---|
| 1 | #225 cursos | De acordo | Mesclar. |
| 2 | #219 desclassificação | De acordo | Mesclar. Logo depois: PR da D-06 completa (passo 2). |
| 3 | #215 observações | De acordo | Resolver conflito com a #219 (`serializers.py`, `views.py`). Mesclar. |
| 4 | #227 painel do aluno | Diverge (D-06) | Antes do merge: falta de categoria vira `PROJECT_DATA_MISSING` em `incomplete_requirements` e conta em `PROJECT_DATA_PENDING`; trocar a busca por texto das mensagens por códigos devolvidos por `compute_unmet_requirements`. Resolver conflitos com #215/#219. |
| 5 | #223 notificações | De acordo | Mesclar. O texto "Resultado da edição publicado" muda quando a ordem da homologação for corrigida (passo 2, D-01). |
| 6 | #224 chamados | Diverge (decisão dos chamados) | Antes do merge: `WAITING_USER` volta a ser aceito (a orientação é não usar, não bloquear). |
| 7 | ~~#226 edital~~ ajustado | Fere D-02 | Esperar a PR da D-02. Depois: tirar a exigência "critérios de cada etapa somam o valor dela"; registrar a rota `GET /api/public/editions/{id}/regulation/{uuid}` no contrato (P-43); falha de armazenamento como `503 storage_unavailable`; responder a pergunta do `durable=True`. |

## Passo 2 — decisões ainda não aplicadas (uma PR cada)

| Ordem | Decisão | Onde | Depende de |
|---|---|---|---|
| A | ~~**D-02** escala dos critérios (#228)~~ feito | Tirar `ensure_criterion_fits_stage` (`apps/editions/rules.py`); `recalculate_stage_score` proporcional (soma dos points ÷ soma dos max_score × `Stage.max_score`, média entre professores); descrições no `gen_openapi.py` | — (destrava a #226) |
| B | ~~**D-06** categoria obrigatória (#229)~~ feito | `category` em `ensure_project_complete`; testes e factories de teams e projects | #219 |
| C | ~~**D-01** pódio por categoria na edição (#230)~~ feito | Trazer `compute_awards` da branch de emergência com o grupo por `category_id`; homologação depois da avaliação externa e do pódio (pendência 3 da #220); texto da rota `winners`; `list_edition_winners` | A, B |
| D | Convite `student_id` ou `email` (#231) | `InvitationCreate` com `oneOf` no gerador; código não muda | — |
| E | Rota `invitable-students` (#232) | Rota nova no contrato + selector + view (só líder, `search` ≥ 3, nome e curso) | D |
| F | `PATCH /api/teams/{id}` só com `name` (#233) | Contrato + use case + view (líder, formação aberta) | — |

## Decisões que você ainda precisa tomar

- [x] **Nota pendente na homologação** (pendência 4 da #220): recusar homologar (decidido em 25/11, #230).

## Fora deste plano (aguardam terceiros)

- Certificados (D-07): aguardando a coordenação.
- Carga oficial do Apêndice A (D-09a) e banca da final: aguardando a coordenação.
- E-mail real (D-09c, #234): desenho do envio a definir.
