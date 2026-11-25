from decimal import Decimal as D

from apps.results.compute import RankEntry, compute_course_ranks


def entry(pid, score, tiebreak=(), course=1):
    return RankEntry(pid, course, D(score), tuple(D(t) for t in tiebreak))


def test_ranking_por_curso_pela_nota():
    ranks = compute_course_ranks(
        [entry(1, "7"), entry(2, "9"), entry(3, "5", course=2)]
    )
    assert ranks == {2: 1, 1: 2, 3: 1}


def test_desempate_pelo_primeiro_e_depois_pelo_segundo_criterio():
    ranks = compute_course_ranks(
        [
            entry(1, "8", ("2", "1")),
            entry(2, "8", ("3", "0")),
            entry(3, "8", ("2", "2")),
        ]
    )
    assert ranks == {2: 1, 3: 2, 1: 3}


def test_empate_total_divide_a_posicao_e_pula_a_seguinte():
    ranks = compute_course_ranks([entry(1, "8"), entry(2, "8"), entry(3, "7")])
    assert ranks == {1: 1, 2: 1, 3: 3}
