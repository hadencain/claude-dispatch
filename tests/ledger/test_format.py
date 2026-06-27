from ledger.format import bar, short_project, sparkline, units


def test_units_compact_suffixes():
    assert units(14_000_000) == "14M"
    assert units(2_100_000) == "2.1M"
    assert units(48_000) == "48K"
    assert units(500) == "500"


def test_short_project_takes_tail_after_src_marker():
    assert short_project("C--Users-haden-Documents-Ship-src-casino-bjap") == "casino-bjap"
    assert short_project("C--Users-haden-Documents-Ship-src-claude-dispatch") == "claude-dispatch"
    assert short_project("no-marker-here") == "no-marker-here"


def test_bar_fills_proportionally():
    assert bar(0.0, width=10) == "░" * 10
    assert bar(1.0, width=10) == "█" * 10
    assert bar(0.5, width=10).count("█") == 5


def test_sparkline_maps_values_to_blocks():
    line = sparkline([0.0, 1.0, 2.0, 4.0])
    assert len(line) == 4
    assert line[0] != line[-1]  # low vs high differ
    assert sparkline([]) == ""
