# Desafio X — backend Django

Plataforma do Desafio X da UniCatólica. Django 6.1 + DRF, uv, PostgreSQL. Contexto e histórico das decisões: `docs/contexto.md`.

## Fontes de verdade (nesta ordem)

1. **Guia de implementação** — `docs/guia-implementacao-django.md` (branch `main`). O glossário da seção 7 define os nomes em inglês; termo fora dele se discute antes.
2. **Modelagem** — `docs/modelagem/desafio-x.dbml` (em português, FKs simples). O código traduz os nomes para inglês. O DBML em inglês do outro chat serve só como fonte de ideias.
3. **Requisitos** — Google Doc "DOCUMENTAÇÃO PADRÃO DE REQUISITOS | PLATAFORMA DESAFIO X".
4. **Contrato da API** — `docs/api/` (OpenAPI gerado por `gen_openapi.py`; edite o gerador, nunca o YAML). Quando guia e OpenAPI divergem, vale o guia e o ajuste vai para o gerador.

## Rodar

```bash
uv sync
cp .env.example .env          # preencher DJANGO_SECRET_KEY
docker compose up -d          # Postgres na porta 5433
uv run python manage.py migrate
uv run python manage.py seed_users --password "SuaSenha!2026"   # só com DEBUG=True
uv run pytest
```

Rode o servidor e os testes na branch mais nova: as branches antigas ficam atrás do banco migrado.

## Convenções

- Código em inglês; `verbose_name`, mensagens de erro, docstrings e commits em português.
- Model: docstring com RF/RN, FK entre apps por string, `PROTECT` por padrão (`CASCADE` só com comentário), `related_name` explícito, constraints no `Meta` com nome em inglês. `models.py` vira pacote `models/` acima de 5 models.
- Regra que consulta outra tabela vai em `rules.py` (`ensure_...`); o `clean()` do model só chama a regra, para o admin validar.
- Escrita em `use_cases/` (um arquivo, uma função, argumentos nomeados, `@transaction.atomic`); view não tem regra.
- Um teste por constraint (tentando violar) e por regra nova. Testes novos em pytest.
- CI: `ruff check`, `ruff format --check`, `makemigrations --check`, `pytest`, `pip-audit`.

## Git

- Commit: `tipo(app): descrição` em português, terminando com `Refs #N`. **Sem linha `Co-Authored-By`.**
- Uma branch por task: `feat/<app>-models-bmN`, criada a partir da anterior enquanto a PR anterior não é mesclada. Um app por PR.
- Não fazer push nem abrir PR sem o pedido do dono. `main` e `developer` são protegidas: toda mudança entra por PR.
- Migração de branch ainda não mesclada pode ser refeita; depois do merge, só migração nova.
