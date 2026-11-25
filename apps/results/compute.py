"""Cálculos puros de resultados (RF15): sem banco."""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

CENT = Decimal("0.01")


@dataclass(frozen=True)
class RankEntry:
    """Projeto a classificar; `tiebreak` segue a ordem dos critérios de desempate."""

    project_id: int
    course_id: int
    final_score: Decimal
    tiebreak: tuple[Decimal, ...] = ()


def compute_course_ranks(entries: list[RankEntry]) -> dict[int, int]:
    """Posição de cada projeto no curso, pela nota e pelo desempate (Art. 24).

    Empate que sobra divide a posição, e a seguinte é pulada (1, 1, 3).
    """
    by_course = defaultdict(list)
    for entry in entries:
        by_course[entry.course_id].append(entry)
    ranks = {}
    for course_entries in by_course.values():
        keys = [(e.final_score, *e.tiebreak) for e in course_entries]
        for entry, key in zip(course_entries, keys, strict=True):
            ranks[entry.project_id] = 1 + sum(other > key for other in keys)
    return ranks
