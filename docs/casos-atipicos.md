# Casos atípicos — o que falta para o sistema absorver

Situações fora do fluxo normal do Desafio X e o que o sistema permite hoje. Levantado lendo o código da `developer` em 28/11/2026; nada aqui foi testado rodando, salvo onde indicado. Cada item que pede rota nova passa pelo processo do contrato (issue de decisão → `gen_openapi.py` → YAML) antes de virar código.

Parte da #217. Decisões dos casos do professor: #304 (28/11/2026).

## 1. Administrador — casos que precisam de rota

Já resolvido sem rota (Django admin, #267 e #301): status e limites da edição só leitura, avaliação e nota só leitura, limite de integrantes no cadastro da equipe, ações "Reverter desclassificação" e "Tornar líder da equipe", formação só em edição publicada. Etapa de edição publicada continua ajustável pelo Django admin (#128).

| # | Caso | Hoje | O que falta decidir/implementar |
|---|---|---|---|
| A1 | Adiar o prazo de uma etapa para todas as equipes depois de publicar | Só pelo Django admin, editando a etapa. A API recusa (`edition_published`) | Rota no painel para mudar **só as datas** da etapa publicada, ou prorrogação em lote. Decidir qual |
| A2 | Prorrogar o prazo de uma equipe pelo painel | Só pelo Django admin (`DeadlineExtension`) | Rota de prorrogação por equipe. Avisar o admin quando a prorrogação passar do prazo de avaliação da etapa (P1) |
| A3 | Reabrir a avaliação de um professor para ele refazer | Não existe. Só a retificação item por item (`POST /api/admin/evaluations/{id}/rectifications`) | Rota que volta a avaliação a rascunho, com motivo e histórico, e recalcula a nota. Efeito no front: avaliação finalizada pode voltar a rascunho |
| A4 | Retirar um arquivo entregue (arquivo errado ou impróprio) | Versões são só leitura em todo lugar | Rota que invalida uma versão com motivo, sem apagar (histórico RF31). Efeito no front: versão "retirada" na lista |
| A5 | Corrigir algo depois de encerrar a edição | Nada: o encerramento é irreversível e `ensure_edition_not_closed` barra nota, desclassificação e avaliador | Janela de correção antes de encerrar (de preferência por datas/flag, não status novo) ou deixar explícito no painel que encerrar é definitivo |
| A6 | Reverter desclassificação e trocar líder pelo painel | Só como ação do Django admin | Rota se o painel do admin precisar; os casos de uso (`reinstate_team`, `assign_leader`) já existem |
| A7 | Status de equipe e projeto editáveis à mão no Django admin | Grava qualquer valor, sem efeitos colaterais | Decidir se o campo fica só leitura (sem rota) |

## 2. Professor

O professor avalia a entrega das equipes cujo desafio é do curso dele (vínculo ativo em `TeacherCourse`) e decide os pedidos de liderança dessas equipes. A nota da etapa é a média das avaliações **finalizadas**; com menos avaliações que o `min_evaluations` da etapa (padrão 1) ela fica **pendente**, e nota pendente impede aprovar os finalistas (`ensure_no_pending_scores`).

Regras da avaliação: só finaliza depois do prazo de entrega da equipe (com a prorrogação dela) e até o `evaluation_ends_at` da etapa; finalizada é imutável; só muda pela retificação do admin.

| # | Caso | O que acontece hoje | Quem resolve hoje | Lacuna |
|---|---|---|---|---|
| P1 | **Prorrogação da equipe passa do prazo de avaliação** | `ensure_extension_after_stage_end` só exige depois do fim da etapa. Se a prorrogação termina depois de `evaluation_ends_at`, o professor nunca consegue finalizar: antes do prazo da equipe recusa, depois passa do prazo de avaliação. A nota fica pendente e trava os finalistas | Admin estendendo `evaluation_ends_at` da etapa no Django admin (vale para todas as equipes) | **Decidido (28/11): fica como está.** O admin estende o `evaluation_ends_at` da etapa no Django admin quando conceder prorrogação longa |
| P2 | Professor perdeu o prazo de avaliação | Não finaliza mais; a nota fica pendente | Admin estende `evaluation_ends_at` da etapa no Django admin | Não há prazo de avaliação por professor ou por projeto; a extensão vale para todos. Rota se o painel precisar (junto da A1) |
| P3 | Professor finalizou com nota errada | Avaliação imutável | Admin retifica item por item (rota existe, com histórico) | Nenhuma, se a retificação bastar. Se o professor tiver que refazer tudo, ver A3 |
| P4 | Curso sem professor ativo (saiu, desativado, sem vínculo) | Ninguém avalia os projetos do curso; nota pendente; pedidos de liderança das equipes ficam parados | Admin vincula outro professor ao curso (rota de professores do admin) | Nenhum aviso ao admin de curso sem professor ativo. Avaliar um alerta no painel |
| P5 | Professor desligado no meio da etapa, com rascunho | O rascunho fica e não conta; as avaliações já finalizadas continuam valendo na média | Outro professor do curso avalia | Nenhuma, mas o rascunho órfão aparece no Django admin; nada a fazer |
| P6 | `min_evaluations` maior que o número de professores do curso | A nota nunca chega a definitiva; trava os finalistas | Admin baixaria o mínimo, mas a etapa publicada só muda pelo Django admin | **Corrigido (#304):** publicar exige professores ativos suficientes em cada curso com desafio (pendência `teachers`). Professor desligado depois da publicação continua sem aviso (ver P4) |
| P7 | Professor quer corrigir antes do prazo uma avaliação que já finalizou | Imutável | Admin retifica | Decidir se o professor pode reabrir a própria avaliação até `evaluation_ends_at` (seria a A3 com o professor como ator) |
| P8 | Pedido de liderança parado (professor não responde) | Fica `PENDING` sem prazo | Admin usa "Tornar líder da equipe" no Django admin, mas o pedido continua `PENDING` | **Corrigido (#304):** "Tornar líder da equipe" cancela o pedido pendente da equipe, com a justificativa registrada |
| P9 | Professor avalia projeto de equipe desclassificada | `evaluate_submission` não confere o status da equipe; a nota é gravada, mas o projeto já está fora dos finalistas e do ranking | Ninguém precisa agir | **Corrigido (#304):** avaliação de equipe desclassificada ou desfeita é recusada (400 `validation_error`, `details.team`) |
| P10 | Projeto com desafio invalidado (curso sem representante) | Sem desafio, nenhum professor tem vínculo; sem entrega válida, a etapa vira zero (`apply_zero_scores`) | Sistema | Nenhuma: comportamento coerente |
| P11 | Equipe enviou nova versão depois de o professor começar o rascunho | O rascunho continua; a finalização só abre depois do prazo da equipe, então ele avalia a versão válida | Sistema | Nenhuma |

## Ordem sugerida

1. Feito na #304: P6, P8 e P9. P1 decidido como está.
2. Decisões de contrato: A1/P2 (datas da etapa publicada), A3/P7 (reabrir avaliação), A2, A4, A5.
3. P4: alerta ao admin de curso sem professor ativo.
