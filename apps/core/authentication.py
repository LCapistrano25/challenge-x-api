from rest_framework import authentication


class SessionAuthentication(authentication.SessionAuthentication):
    """Sessão do DRF que responde 401 sem login, como o contrato pede.

    O DRF só devolve 401 quando a autenticação informa o cabeçalho
    WWW-Authenticate; sem ele, a falta de login vira 403.
    """

    def authenticate_header(self, request):
        return "Session"
