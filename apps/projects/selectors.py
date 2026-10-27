from apps.projects.models import Submission, SubmissionVersion


def get_submission_deadline(project, stage):
    """Prazo de entrega da equipe: a prorrogação, se houver, senão o da etapa."""
    extension = project.deadline_extensions.filter(stage=stage).first()
    return extension.ends_at if extension else stage.ends_at


def get_valid_version(submission: Submission) -> SubmissionVersion | None:
    """Versão que vale: a de maior número enviada até o prazo da equipe na etapa.

    Nenhuma versão no prazo = entrega não enviada (None).
    """
    deadline = get_submission_deadline(submission.project, submission.stage)
    return (
        submission.versions.filter(submitted_at__lte=deadline)
        .order_by("-number")
        .first()
    )
