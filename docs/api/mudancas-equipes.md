# Equipes (task #66): regras novas e o que muda no frontend

Fonte de verdade: `docs/api/openapi.yaml`. Prints de cada item em `Claude outputs/task-66/`.
Erro de todas as rotas: `{"error": {"code", "message", "details"}}`.

## Resumo das regras

1. Uma equipe **não nasce só com o líder**: o corpo da criação traz os convites.
2. O líder que está **sozinho** pode sair: a equipe vira `DISBANDED` (desfeita).
3. O líder com outros integrantes **precisa transferir a liderança** antes de sair.
4. Saída que deixa a equipe **abaixo do mínimo** da edição só vale com confirmação.
5. Saída nas **últimas 24 horas** do prazo que derruba a equipe abaixo do mínimo dá **48 horas extras** (uma vez só) para repor a vaga.

## 1. `POST /api/teams` agora exige `invitations`

```json
{"name": "Minha equipe", "invitations": [{"student_id": 42}, {"email": "ana@unicatolica.edu.br"}]}
```

- Quantidade: de `min_members - 1` até `max_members - 1` convites (nunca menos de 1).
- Fora disso: **400** `team_invitations_required`. Convite inválido derruba a criação inteira (nada fica salvo).
- O nome de uma equipe desfeita volta a ficar livre.

Prints: `1-criar-equipe-sem-convites-400.jpg`, `2-criar-equipe-com-convites-201.jpg`.

## 2. `POST /api/teams/{id}/leave`

Corpo opcional: `{"confirm": true}` (padrão `false`). Respostas:

| Situação | Resposta |
|---|---|
| Líder com outros integrantes | 409 `leader_must_transfer` (mensagem "Transfira a liderança antes de sair da equipe.") |
| Líder sozinho | 204, equipe vira `DISBANDED`; convites e pedidos pendentes são cancelados e os envolvidos são avisados |
| Saída deixa a equipe abaixo do mínimo, sem `confirm` | 409 `leave_below_minimum` ("Sua saída deixa a equipe com 2 de 3 integrantes. Confirme para sair.") |
| Mesma saída com `confirm: true` | 204 |
| Fora do prazo de formação (e sem janela extra) | 409 |

**Fazer no front:** ao receber `leave_below_minimum`, mostrar a mensagem num diálogo e reenviar com `confirm: true` se a pessoa aceitar.

Prints: `3-lider-com-integrantes-nao-sai-409.jpg`, `4-lider-sozinho-sai-204.jpg`, `5-equipe-desfeita-DISBANDED.jpg`, `6-saida-abaixo-do-minimo-409.jpg`.

## 3. Janela extra de 48 horas (`formation_extended_until`)

- `Team.formation_extended_until` (datetime ou `null`) vem no `GET /api/teams/{id}`.
- É preenchido quando alguém sai nas **últimas 24 h** do prazo e a equipe cai abaixo do mínimo: vale `fim do prazo + 48 h`. Só acontece **uma vez** por equipe.
- Os integrantes que ficam recebem notificação com a data limite ("A equipe tem até 23/11 01:43 para repor a vaga.").
- **Durante a janela:** o líder convida, alunos pedem para entrar e convites/pedidos podem ser aceitos. **Ninguém sai** (evita saída em cadeia).
- **Depois da janela**, ou sem janela: tudo isso volta a dar 409.

**Fazer no front:** se `formation_extended_until` não for `null` e estiver no futuro, mostrar o aviso "Prazo extra até ..." na tela da equipe e manter os botões de convite habilitados.

Prints: `7-janela-extra-concedida-formation_extended_until.jpg`, `8-convite-durante-janela-extra-201.jpg`, `9-convite-fora-do-prazo-409.jpg`.

## Correção encontrada ao tirar os prints

`POST /api/teams/{id}/invitations` fora do prazo respondia **500** (a exceção do caso de uso não era tratada pela view). Agora responde **409** com a mensagem "Não existe prazo de formação aberto para esta equipe.", como o contrato já previa. Teste: `test_convite_fora_do_prazo_retorna_409_e_nao_500`.

## Para o time do congelamento (#118)

O `freeze_formation_period` precisa: ignorar equipes `DISBANDED`, respeitar `formation_extended_until` (não marcar `INCOMPLETE` nem cancelar convites enquanto a janela estiver aberta) e rodar só depois dela.

## Constantes fixas

24 h (`FORMATION_LAST_HOURS`) e 48 h (`FORMATION_EXTENSION`) ficam em `apps/teams/rules.py`. Se o regulamento passar a variar por edição, levar para o modelo `Edition`.
