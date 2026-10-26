from django.apps import apps
from django.core.exceptions import ValidationError

# Os models importam estas regras; por isso elas pegam os models pelo registro
# do Django (como a FK por string), sem import que fecharia o ciclo.


def ensure_student_in_project_team(score) -> None:
    """Só pontua quem integrou a equipe do projeto (RF16)."""
    members = apps.get_model("teams", "TeamMember").objects
    if not members.filter(
        team_id=score.project.team_id, student_id=score.student_id
    ).exists():
        raise ValidationError({"student": "O aluno não integrou a equipe do projeto."})
