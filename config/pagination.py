from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    """Paginação padrão das listagens (P-38): `page` e `page_size`, 20 por página.

    Resposta: {count, next, previous, results}. Listagem curta e de configuração
    (cursos, etapas, critérios) desliga com `pagination_class = None` e devolve
    um array simples.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
