"""Regression for the donor's tied sixth-place Fourier score."""

# This regression intentionally tests the candidate's private compatibility hook.
# pyright: reportPrivateUsage=false

import pytest

from lottolab.application import legacy_analyze_k3_candidate as candidate
from lottolab.application.k3_predraw_guard import _supplement
from lottolab.strategies.adapters.base import CausalDrawRow


def test_historical_tie_uses_legacy_indirect_sort(monkeypatch: pytest.MonkeyPatch) -> None:
    # Frozen candidate scores for historical target 108000100, in 1..49 order.
    scores = (
        0.294,
        0.04216867469879518,
        0.14821124361158433,
        0.06177606177606178,
        0.057021276595744685,
        0.26144756277695713,
        0.3137254901960784,
        0.21982758620689655,
        0.4662756598240469,
        0.2588495575221239,
        0.10873440285204992,
        0.4666666666666667,
        0.73828125,
        0.20268006700167504,
        0.6136363636363635,
        0.26144756277695713,
        0.3582089552238806,
        0.1114864864864865,
        0.34400000000000003,
        0.8636363636363643,
        0.08333333333333333,
        0.18681318681318682,
        0.5531914893617021,
        0.43589743589743574,
        0.39799999999999996,
        0.2012779552715655,
        0.098,
        0.1602409638554217,
        0.06307525717379535,
        0.11513859275053305,
        0.20600000000000002,
        0.17136498516320475,
        0.39230769230769236,
        0.10706150341685648,
        0.13968253968253969,
        0.36046511627906974,
        0.043478260869565216,
        0.12525252525252525,
        0.3360323886639676,
        0.128,
        0.4666666666666667,
        0.6840277777777778,
        0.05532190229699127,
        0.036608863198458574,
        0.04705274043433299,
        0.04080551139374669,
        0.3157894736842105,
        0.14814814814814814,
        0.16161616161616163,
    )
    def fixed_scores(_history: tuple[CausalDrawRow, ...]) -> dict[int, float]:
        return dict(enumerate(scores, 1))

    def fixed_two_bets(
        _history: tuple[CausalDrawRow, ...],
    ) -> tuple[tuple[int, ...], tuple[int, ...]]:
        ticket = (1, 2, 3, 4, 5, 6)
        return ticket, ticket

    monkeypatch.setattr(candidate, "_fourier_rhythm_scores", fixed_scores)
    monkeypatch.setattr(candidate, "_p0_hot_echo_2bets", fixed_two_bets)
    history = (CausalDrawRow("1", "2020-01-01", (1, 2, 3, 4, 5, 6)),) * 500
    result = candidate.analyze_native_14(history)
    assert scores[11] == scores[40]
    assert result[2] == (13, 15, 20, 23, 41, 42)


def test_dedup_only_reads_original_three_positions():
    a = (1, 2, 3, 4, 5, 6)
    b = (7, 8, 9, 10, 11, 12)
    c = (19, 20, 21, 22, 23, 24)
    unique, positions = candidate.deduplicate_native_prefix((a, tuple(reversed(a)), b, c))
    assert unique == (a, b)
    assert positions == (1, 3)
    all_unique, all_positions = candidate.deduplicate_all_then_k3(
        (a, tuple(reversed(a)), b, c) + (a,) * 10
    )
    assert all_unique == (a, b, c)
    assert all_positions == (1, 3, 4)
    historical, supplement_indices = _supplement(unique)
    assert historical == (a, b, (13, 14, 15, 16, 17, 18))
    assert supplement_indices == (2,)
