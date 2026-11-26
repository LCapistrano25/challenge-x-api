"""Cálculos puros de resultados (RF15): sem banco."""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

CENT = Decimal("0.01")


@dataclass(frozen=True)
class RankEntry:
    """Projeto a classificar dentro do grupo (curso ou categoria).

    `tiebreak` segue a ordem de desempate depois da nota.
    """

    project_id: int
    group_id: int
    score: Decimal
    tiebreak: tuple[Decimal, ...] = ()


def compute_ranks(entries: list[RankEntry]) -> dict[int, int]:
    """Posição de cada projeto no grupo, pela nota e pelo desempate (Art. 24).

    Empate que sobra divide a posição, e a seguinte é pulada (1, 1, 3).
    """
    by_group = defaultdict(list)
    for entry in entries:
        by_group[entry.group_id].append(entry)
    ranks = {}
    for group in by_group.values():
        keys = [(e.score, *e.tiebreak) for e in group]
        for entry, key in zip(group, keys, strict=True):
            ranks[entry.project_id] = 1 + sum(other > key for other in keys)
    return ranks
