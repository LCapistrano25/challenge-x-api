from django.core.mail.backends.console import EmailBackend


class ReadableConsoleEmailBackend(EmailBackend):
    """Console de desenvolvimento que mostra o corpo do e-mail já decodificado.

    O backend padrão imprime a mensagem MIME crua; linhas longas (como o link de
    confirmação) saem em quoted-printable, com `=` no fim da linha e `=3D`.
    """

    def write_message(self, message):
        self.stream.write(
            f"From: {message.from_email}\n"
            f"To: {', '.join(message.recipients())}\n"
            f"Subject: {message.subject}\n\n"
            f"{message.body}\n"
        )
        self.stream.write("-" * 79 + "\n")
