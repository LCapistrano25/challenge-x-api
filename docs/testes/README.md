# Testes manuais da API — Desafio X

Roteiros para testar a API **sem o frontend**, antes da integração. Cada pessoa fica com um fluxo, roda no **seu próprio ambiente local** e registra o resultado de cada passo no próprio roteiro.

- Fonte de verdade das rotas, campos, status e códigos de erro: o contrato `docs/api/openapi.yaml` (Swagger em `http://127.0.0.1:8000/api/docs/` com o servidor rodando).
- Mudanças recentes que os roteiros já cobrem: `docs/api/mudancas-frontend.md`, seção 0.
- Teste sempre sobre a `developer` atualizada (`git fetch origin` e `git switch developer` + `git pull`), nunca sobre a `feat/emergencia-backend-completo`.

## Quem faz qual fluxo

| Roteiro | Fluxo | Perfis | Cenário | Rotas usadas | Responsável (task) |
|---|---|---|---|---|---|
| [01](01-admin-configuracao-edicao.md) | Admin — configuração da edição | ADMIN (+ aluno para 403) | só `seed_users` | 39 | @Viniciusgt39 (#274) |
| [02](02-aluno-equipe.md) | Aluno — equipe | STUDENT (+ professor para 403) | `cenario.py` padrão | 23 | @theokkkk1 (#275) |
| [03](03-aluno-projeto-entregas.md) | Aluno — projeto e entregas | STUDENT, ADMIN, TEACHER | `cenario.py` padrão | 18 | @ViniciusGGomes (#276) |
| [04](04-professor-avaliador.md) | Professor e avaliador externo | TEACHER, EXTERNAL_REVIEWER, ADMIN | `cenario.py` padrão | 19 | @LCapistrano25 (#277) |
| [05](05-admin-usuarios-resultados-suporte.md) | Admin — usuários, equipes, suporte e resultados | ADMIN, STUDENT, TEACHER | `cenario.py` com `CENARIO=resultados` | 39 | @Shueiz (#278) |

As 124 operações do contrato estão cobertas; algumas aparecem em mais de um roteiro (por exemplo, o roteiro 3 usa a desclassificação, que é do 5).

**Por que a divisão não é exata por número de rotas:** o roteiro 1 tem mais rotas, mas quase todas são cadastros simples (criar, listar, editar e excluir). O roteiro 3 tem menos rotas, mas é o mais trabalhoso: envio com arquivo, prazos, prorrogação e regras de categoria. As rotas de sessão (`/api/auth/...`) foram para os roteiros 2, 4 e 5. O encerramento da edição foi para o roteiro 5, porque fecha o ciclo depois da homologação.

## 1. Subir o ambiente (≈10 min na primeira vez)

Pré-requisitos: Docker Desktop, [uv](https://docs.astral.sh/uv/) e Git Bash (os exemplos usam `curl`).

```bash
uv sync
cp .env.example .env
```

No `.env`, preencha `DJANGO_SECRET_KEY`, use `POSTGRES_PASSWORD=dev_password` (a senha do `docker-compose.yaml`) e um banco **só para os testes**, para não mexer no seu banco de desenvolvimento. **Acrescente também a última linha**: ela deixa aluno e professor entrarem por senha, só no ambiente local.

```
POSTGRES_DB=desafiox_testes
POSTGRES_PASSWORD=dev_password
ALLOW_PASSWORD_LOGIN_FOR_ALL_ROLES=True
```

```bash
docker compose up -d                       # Postgres na porta 5433
docker exec desafiox-db-dev createdb -U desafiox desafiox_testes
uv run python manage.py migrate
uv run python manage.py seed_users --password 'Teste!2026x'
```

Depois, conforme a coluna **Cenário** da tabela acima:

```bash
# Roteiros 2, 3 e 4
uv run python manage.py shell -c "exec(open('docs/testes/cenario.py').read())"

# Roteiro 5
CENARIO=resultados uv run python manage.py shell -c "exec(open('docs/testes/cenario.py').read())"

# Roteiro 1: não rode o cenário (ele já publica uma edição)
```

O cenário imprime os IDs que os roteiros usam, um por linha (`EDITION=1`, `TEAM_A=1`...). **Copie essa saída** para o topo do seu roteiro: onde o roteiro escreve `{TEAM_A}`, use o número impresso.

Para começar do zero (por exemplo, para repetir o roteiro), pare o servidor e recrie só o banco de testes:

```bash
docker exec desafiox-db-dev dropdb -U desafiox desafiox_testes
docker exec desafiox-db-dev createdb -U desafiox desafiox_testes
uv run python manage.py migrate
# e repita seed_users e o cenário
```

Suba o servidor e deixe o terminal aberto:

```bash
uv run python manage.py runserver
```

## 2. Login e CSRF (leia antes de começar, senão tudo dá 403)

A API usa sessão por cookie:

1. `GET /api/auth/csrf` cria o cookie `csrftoken`.
2. `POST /api/auth/sessions/password` com `{"email", "password"}` abre a sessão (cookie `sessionid`).
3. **Todo POST, PUT, PATCH e DELETE** leva o header `X-CSRFToken` com o valor do cookie `csrftoken`. Sem ele, a resposta é `403 permission_denied` com "CSRF Failed".
4. O `csrftoken` **muda no login**: leia o cookie de novo depois de entrar.
5. A sessão expira após **30 minutos sem uso**. Se uma rota que funcionava passar a dar `401 not_authenticated`, faça login de novo.

Em HTTP local o header `Referer` não é exigido. Em homologação com HTTPS, mande também `Referer: <origem>`.

### Atalho em Git Bash: `docs/testes/api.sh`

```bash
source docs/testes/api.sh                  # usa B=http://127.0.0.1:8000
login admin.jar admin@desafiox.local 'Teste!2026x'
api admin.jar GET /api/admin/courses
api admin.jar POST /api/admin/courses -d '{"name":"Curso X","term_count":8}'
upload aluno.jar POST /api/projects/1/stages/3/versions -F 'items=[...]' -F 'files[]=@relatorio.pdf'
```

Cada `.jar` guarda os cookies de um perfil. Use um arquivo por usuário (`admin.jar`, `aluno.jar`, `prof.jar`...). A última linha de cada resposta mostra o status (`[HTTP 201]`).

### Usuários

| Perfil | E-mail | Senha |
|---|---|---|
| ADMIN | `admin@desafiox.local` | a do `seed_users` |
| STUDENT (líder da "Equipe Seed" no cenário) | `aluno@aluno.desafiox.local` | a do `seed_users` |
| TEACHER (curso Engenharia de Software) | `professor@professor.desafiox.local` | a do `seed_users` |
| EXTERNAL_REVIEWER | `avaliador@empresa.local` | a do `seed_users` |
| Alunos criados pelo cenário (`membro1`, `membro2`, `livre1` a `livre6`, `semliderb1`..., `semliderc1`..., `novoaluno`) | `<nome>@aluno.desafiox.local` | `TesteForte!2026x` |
| Professor sem perfil (autocadastro) | `novoprof@professor.desafiox.local` | `TesteForte!2026x` |

O avaliador externo só entra se estiver vinculado à edição **publicada** (o cenário já faz o vínculo). Sem edição publicada, o login dele dá `403 reviewer_not_in_current_edition`.

### Sem a linha `ALLOW_PASSWORD_LOGIN_FOR_ALL_ROLES` (login de aluno e professor pela Microsoft)

Aluno e professor entram pela Microsoft, o que não dá para fazer só com `curl`. Para testar sem essa linha, use a sessão que o cenário imprime no fim (`SESSION STUDENT aluno@... <sessionid>`). Ela é criada com `django.test.Client().force_login(user)`:

```bash
sessao aluno.jar <sessionid impresso>      # monta o jar e já pega o csrftoken
```

Para outro usuário:

```bash
uv run python manage.py shell -c "from django.test import Client; from apps.accounts.models import User; c=Client(); c.force_login(User.objects.get(email='membro1@aluno.desafiox.local')); print(c.cookies['sessionid'].value)"
```

### Postman ou Insomnia

Também servem. Chame `GET /api/auth/csrf` primeiro e depois o login. Em cada requisição de escrita, coloque o header `X-CSRFToken` com o valor do cookie `csrftoken` (o Postman mostra os cookies em "Cookies", abaixo do botão Send).

## 3. Como preencher o roteiro

Cada passo tem uma coluna **Resultado**. Marque `ok` ou `falhou #N`, em que `#N` é a issue que você abriu. Se um passo depende de outro que falhou, marque `bloqueado`.

Todos os roteiros cobrem, no mínimo, estes erros:

| Caso | Esperado |
|---|---|
| Perfil errado (ex.: aluno em rota de admin) | `403 permission_denied` |
| Recurso de outra equipe | `403` ou `404`, conforme o roteiro (o contrato define qual) |
| Recurso inexistente (id 999999) | `404 not_found` |
| Corpo inválido (campo faltando, tipo errado, campo extra) | `400 validation_error`, com o campo em `error.details` |
| JSON malformado | `400 parse_error` |
| Regra de negócio | `409` com o `code` do contrato |
| Filtro inválido (`?active=abc`, `?status=FOO`) | `400 validation_error` |
| Página inexistente (`?page=999`) | `404 not_found` ("Página inválida.") |
| Sem login | `401 not_authenticated` |

Erros sempre vêm no formato `{"error": {"code", "message", "details"}}`. Confira o `code`, não só o status.

## 4. Registrar um defeito

Abra uma issue em <https://github.com/LCapistrano25/challenge-x-api/issues> com o título `[teste manual] <rota> — <resumo>` e o corpo abaixo. **Na primeira linha do corpo, escreva `Parte da #217`** (nunca "Closes"/"Fixes").

```markdown
Parte da #217

**Roteiro/passo:** 03, passo 3.7
**Rota:** POST /api/projects/{project_id}/stages/{stage_id}/versions
**Perfil:** STUDENT (aluno@aluno.desafiox.local, líder da Equipe Seed)
**Corpo enviado:**
{"items": [{"field_id": 2, "link": "https://github.com/x/y"}]}

**Resposta recebida:** 500 / corpo ...
**Resposta esperada (contrato):** 201 com `receipt` preenchido
**Commit da developer testado:** `git log -1 --oneline`
```

Coloque o número da issue na coluna Resultado do passo.

## 5. Divergências encontradas ao escrever os roteiros

Achados ao validar os passos na `developer` (`c46e676`), em 27/11/2026. Nada foi corrigido: cada item precisa de decisão ou issue.

1. **Duas edições publicadas ao mesmo tempo.** `POST /api/admin/editions/{id}/publish` publica uma segunda edição mesmo com outra já `PUBLISHED`. A "edição vigente" (P-41) passa a ser a mais nova, e as rotas do aluno mudam de edição sem aviso. O contrato não lista um 409 para esse caso. Por isso o roteiro 1 roda sem o cenário.
2. **`GET /api/sdgs` devolve campos a mais.** Vêm `active`, `created_at` e `updated_at`, que o schema `PublicSdg` não lista (só `id`, `number`, `title`, `description` e `icon`). Não quebra o front, mas expõe dados de administração numa rota pública.
3. **`400 team_invitations_required` fora dos exemplos.** `POST /api/teams` com convites de menos responde `400` com `code: team_invitations_required`. A descrição da rota cita o código, mas os exemplos de 400 só mostram `validation_error`, `parse_error` e `request_too_large`.
4. **Comandos de fechamento citados no pedido não existem na `developer`.** `compute_results`, `select_finalists`, `compute_awards` e `approve_results` não estão em `apps/*/management/commands/`. Na `developer`, o fechamento é feito pelas rotas `results/calculate` → `finalists` → `awards/calculate` → `results/homologate`, e é assim que o roteiro 5 testa. Os comandos que existem são `apply_zero_scores` e `classify_team_status`.
5. **Mensagem de busca com texto trocado.** `GET /api/teams/{id}/invitable-students?search=li` diz "tenha mais de 3 caracteres", mas a regra (e o comportamento) é **pelo menos** 3: `search=liv` funciona.

### Segunda rodada (27/11, as 55 rotas que ainda não tinham sido chamadas)

154 checagens, 144 conforme o contrato. Os desvios da API:

6. **`DELETE /api/admin/sdgs/{id}` com ODS usada por desafio responde 500** (`ProtectedError`), em vez de `409 sdg_in_use`. Roteiro 01, passo 1.8.11. Issue #280.
7. **`POST /api/admin/sdgs` com número repetido responde `400 validation_error`** (`non_field_errors`), em vez de `409 sdg_number_taken`. Roteiro 01, passo 1.2.3. Issue #281.
8. **`GET /api/admin/sdgs?active=talvez` responde 200 e ignora o filtro**, em vez de `400 validation_error` (as outras listas já recusam). Roteiro 01, passo 1.2.2. Issue #282.
9. **`POST /api/teams/{id}/leadership-transfer` exige `student_id`**, mas o contrato (`LeadershipTransfer`) pede `member_id`; e a resposta é o integrante, não a `Team`. Roteiro 02, passo 2.7.11. Issue #283.
10. **Convite em equipe da qual o aluno não é líder responde `409 business_rule_violation`**, em vez de 403; o código nem existe no contrato. Roteiro 02, passo 2.4.10. Issue #284.
11. **Pedido de liderança exige desafio escolhido**: sem projeto, `POST /api/teams/{id}/leadership-requests` responde `409 leadership_request_rejected`, regra e código fora do contrato. O cenário passou a dar projeto à Equipe C para o roteiro 02 seguir. Issue #285.

Desvios menores, aceitos pelo contrato (que lista 403 e 404): membro que lista os pedidos de entrada da equipe recebe 404 (as outras rotas do líder dão `403 not_team_leader`); observação sobre integrante de fora da equipe recebe 404.

## 6. Rotas fora dos roteiros

Todas as 124 operações do contrato aparecem em pelo menos um roteiro. Duas só têm teste parcial:

| Rota | O que fica de fora | Por quê |
|---|---|---|
| `POST /api/auth/sessions/microsoft` | O caminho feliz (200) | Exige um código real de login da Microsoft no tenant da universidade. O roteiro 5 testa só o erro (código falso → `401 invalid_credentials`, ou `503 external_service_error` sem as variáveis `MICROSOFT_*`). |
| `GET /api/public/editions/{edition_id}/regulation/{token}` | Falha do armazenamento (503) | Precisa derrubar o armazenamento de arquivos. O roteiro 1 testa o 200 e o 404. |

Também ficam de fora os casos que dependem do relógio, como `409 formation_closed` e o `409 stage_not_open`. Os roteiros mostram como forçá-los alterando a data da etapa pelo `manage.py shell`, porque o admin do Django está só leitura.
