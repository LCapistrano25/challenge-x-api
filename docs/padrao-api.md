# Padrão de endpoint: view → serializer → caso de uso

Como escrever um endpoint da API. Copie o exemplo e troque os nomes. As regras de código (nomes, models, casos de uso) estão no [guia de implementação](guia-implementacao-django.md); esta página cobre só a camada HTTP.

## Quem faz o quê

| Camada | Arquivo | Faz | Não faz |
| :- | :- | :- | :- |
| View | `views.py` | recebe a requisição, chama o serializer e o caso de uso, devolve a resposta | regra de negócio, `try/except` para montar erro |
| Serializer | `serializers.py` | valida o **formato** da entrada (obrigatório, tipo, tamanho, `min_value`) | consultar o banco para decidir regra |
| Caso de uso | `use_cases/<acao>.py` | decide: aplica as regras (`ensure_...` de `rules.py`), escreve, lança exceção | conhecer HTTP (`Response`, status) |

Leitura e listagem não viram caso de uso: ficam em `selectors.py`.

## Exemplo: escrita

```python
# apps/accounts/serializers.py
class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    registration_number = serializers.CharField(max_length=50)
    course_id = serializers.IntegerField()
    term = serializers.IntegerField(min_value=1)


# apps/accounts/views.py
class RegisterView(APIView):
    permission_classes = [AllowAny]  # rota pública
    authentication_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        register_student(
            actor=None,
            **serializer.validated_data,
            confirmation_url=request.build_absolute_uri(reverse("confirm-email")),
        )
        return Response({...}, status=status.HTTP_201_CREATED)
```

A view não tem `try/except`. O erro de validação (`is_valid`) e as exceções do caso de uso sobem até o handler, que monta a resposta.

## Erros

Todo erro sai no formato do contrato (P-37), montado por `config/exception.py`:

```json
{"error": {"code": "team_full", "message": "A equipe está completa.", "details": null}}
```

- **Validação de entrada:** `serializer.is_valid(raise_exception=True)` → 400, `code: "validation_error"`, `details` = campo → lista de mensagens. Erro sem campo vai em `details.non_field_errors`.
- **Regra de negócio:** o caso de uso (ou a regra em `rules.py`) lança uma exceção da aplicação:

```python
# apps/<app>/exceptions.py
from http import HTTPStatus

from apps.core.exceptions import BusinessRuleViolation


class TeamFull(BusinessRuleViolation):
    code = "team_full"
    default_message = "A equipe está completa."
    # http_status só quando foge do padrão da base (409)


class NotTeamLeader(BusinessRuleViolation):
    code = "not_team_leader"
    default_message = "Apenas o líder pode realizar esta ação."
    http_status = HTTPStatus.FORBIDDEN
```

| Base (`apps/core/exceptions.py`) | Para | Status padrão |
| :- | :- | :- |
| `BusinessRuleViolation` | regra de negócio violada | 409 |
| `ExternalServiceError` | serviço externo fora do ar (e-mail, armazenamento) | 503 |

- O `code` é estável, em `snake_case`, e é o mesmo do `conflicts` da operação no `gen_openapi.py`.
- Lance com a mensagem padrão (`raise TeamFull()`) ou com uma específica (`raise TeamFull("...")`).
- **Erro da própria view** (objeto inexistente, sem permissão): use o que o DRF já tem — `get_object_or_404`, `NotFound`, `PermissionDenied`.
- **Nunca** `return Response({"erro": ...}, status=400)`: essa resposta não passa pelo handler e sai fora do formato.
- **Nunca** `except Exception` para "tratar" erro: bug tem que sair como 500 e aparecer no log.

## Permissão

Sem `permission_classes`, a view exige login (`IsAuthenticated` é o padrão do `REST_FRAMEWORK`). Declare sempre o papel:

```python
from apps.accounts.permissions import IsAdmin, IsStudent

class FreezeFormationView(APIView):
    permission_classes = [IsAdmin]
```

| Classe | Libera |
| :- | :- |
| `IsAdmin`, `IsStudent`, `IsTeacher`, `IsExternalReviewer` | usuário logado com o papel e o perfil que ele exige |
| `IsAuthenticated` | qualquer usuário logado |
| `AllowAny` | rota pública (login, cadastro, painel público) |

Permissão que depende do objeto ("é o líder desta equipe?") é regra: vai no caso de uso, com o `actor`.

## Listagem

As views genéricas do DRF (`ListAPIView`, `ModelViewSet`) já saem paginadas (P-38): `?page=2&page_size=50`, padrão 20, máximo 100, resposta `{count, next, previous, results}`.

```python
class TeamListView(generics.ListAPIView):
    permission_classes = [IsStudent]
    serializer_class = TeamListingSerializer

    def get_queryset(self):
        return available_teams(edition=current_edition())  # selectors.py
```

Lista curta e de configuração (cursos, etapas, critérios) devolve array simples: `pagination_class = None` na view.

## Testes

Para cada endpoint, em `tests/test_api.py`:

- um teste de sucesso, conferindo status e corpo;
- um teste por papel que **não** pode acessar (403) e um sem login;
- um teste por erro que a view expõe, conferindo `resposta.data["error"]["code"]`.

As regras em si se testam no caso de uso (`tests/test_use_cases.py`), sem HTTP.
