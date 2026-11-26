from apps.core.exceptions import BusinessRuleViolation


class ResultsError(BusinessRuleViolation):
    """Base das violações de regra de negócio do app results."""

    code = "results_error"
    default_message = "Operação não permitida para o resultado."


class NoScoredStages(ResultsError):
    code = "no_scored_stages"
    default_message = "A edição não tem etapa pontuada."


class ResultsAlreadyApproved(ResultsError):
    code = "results_already_approved"
    default_message = "O resultado da edição já foi homologado."


class ResultsNotCalculated(ResultsError):
    code = "results_not_calculated"
    default_message = "As notas finais ainda não foram calculadas."


class FinalistAlreadyEvaluated(ResultsError):
    code = "finalist_already_evaluated"
    default_message = "Há finalista já avaliado fora da lista enviada."


class NoFinalists(ResultsError):
    code = "no_finalists"
    default_message = "Escolha os finalistas antes de homologar."


class ResultsOutdated(ResultsError):
    code = "results_outdated"
    default_message = "As notas mudaram depois do cálculo. Calcule novamente."


class AwardsNotCalculated(ResultsError):
    code = "awards_not_calculated"
    default_message = "Calcule o pódio antes de homologar."


class PendingScores(ResultsError):
    code = "results_pending_scores"
    default_message = "Há projeto com nota de etapa pendente. Conclua as avaliações."
