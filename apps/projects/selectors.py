from apps.projects.models import Submission, SubmissionVersion


def get_valid_version(submission: Submission) -> SubmissionVersion | None:
    """Versão que vale: a de maior número enviada até o fim do prazo da etapa.

    Nenhuma versão no prazo = entrega não enviada (None).
    """
    return (
        submission.versions.filter(submitted_at__lte=submission.stage.ends_at)
        .order_by("-number")
        .first()
    )
