from unittest.mock import Mock

import pytest

from lottolab.application import biglotto_frozen_hpsb as hpsb
from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow


def test_weighted_fallback_boundary_and_zone_protection(monkeypatch: pytest.MonkeyPatch) -> None:
    # These controlled component tickets were also run through the pinned
    # donor's weighted vote and ZDP to obtain the full ranking and final bet.
    components = {
        "_statistical": (1, 2, 3, 4, 5, 6),
        "frozen_markov_ticket": ((1, 2, 3, 4, 5, 17), 1),
        "_unified_repeat_booster_ticket": (1, 2, 3, 4, 18, 19),
        "frozen_bayesian_ticket": (2, 3, 4, 5, 6, 18),
        "_unified_hot_cold_mix_ticket": (1, 2, 3, 4, 5, 19),
        "frozen_deviation_ticket": (1, 2, 3, 5, 6, 20),
    }
    for name, value in components.items():
        monkeypatch.setattr(hpsb, name, Mock(return_value=value))
    numbers = (1, 2, 3, 4, 5, 6)
    rows = tuple(CausalDrawRow(str(i), f"2007-01-{i:02}", numbers) for i in range(1, 21))
    assert hpsb._static_candidates(rows[:19]) == [2, 3, 4, 1, 5, 6, 18, 19, 17, 20]
    dms = Mock(return_value=numbers)
    monkeypatch.setattr(hpsb, "_dms_ticket", dms)
    adapter = hpsb.FrozenHpsbOptimizer()
    assert adapter.get_bets(rows[:19], LotteryType.BIG_LOTTO) == ((2, 3, 4, 17, 18, 19),)
    dms.assert_not_called()
    # At 20 draws DMS supplies only six candidates. ZDP relaxes the zone
    # cap to retain six numbers when it cannot fill all positions otherwise.
    assert adapter.get_bets(rows, LotteryType.BIG_LOTTO) == (numbers,)
    dms.assert_called_once_with(rows)


@pytest.mark.parametrize("first_winner", [0, 1, 2, 3, 4, None])
def test_fifteen_draw_audit_and_method_tie_order(
    monkeypatch: pytest.MonkeyPatch, first_winner: int | None
) -> None:
    numbers = (1, 2, 3, 4, 5, 6)
    history = tuple(CausalDrawRow(str(i), f"2007-01-{i:02}", numbers) for i in range(1, 25))
    methods = (
        "_unified_hot_cold_mix_ticket", "frozen_markov_ticket", "frozen_deviation_ticket",
        "frozen_trend_ticket", "_statistical",
    )
    visited = {method: [] for method in methods}
    # Use the production mapping and its insertion order, bypassing only the
    # memoization so these artificial predictions cannot enter the real cache.
    monkeypatch.setattr(hpsb, "_audit_tickets", hpsb._audit_tickets.__wrapped__)

    def component(index, method):
        def predict(prefix):
            cutoff = len(prefix)
            ids = [
                row.draw if isinstance(row, CausalDrawRow) else row.draw_number for row in prefix
            ]
            assert ids == [row.draw for row in history[:cutoff]]
            visited[method].append(cutoff)
            if cutoff == len(history):
                ticket = (10 + index, 17, 21, 29, 35, 46)
            elif first_winner is not None and index >= first_winner and cutoff == 23 - index:
                ticket = (1, 2, 3, 17, 21, 29)  # Later-declared methods hit earlier.
            else:
                ticket = (1, 2, 10, 17, 21, 29)  # Two matches do not score.
            return (ticket, 1) if method == "frozen_markov_ticket" else ticket

        return predict

    for index, method in enumerate(methods):
        monkeypatch.setattr(hpsb, method, component(index, method))
    assert hpsb._dms_ticket(history) == (10 + (first_winner or 0), 17, 21, 29, 35, 46)
    assert all(cutoffs == list(range(9, 25)) for cutoffs in visited.values())
