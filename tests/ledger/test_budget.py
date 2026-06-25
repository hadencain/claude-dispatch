from ledger.budget import OK, OVER, WARN, CrossingTracker, evaluate


def test_states_ok_warn_over():
    r = evaluate(day_total=5.0, session_costs={}, daily_budget=10.0,
                 per_session_budget=5.0, warn_ratio=0.8)
    assert r.day_state == OK
    r = evaluate(day_total=8.5, session_costs={}, daily_budget=10.0,
                 per_session_budget=5.0, warn_ratio=0.8)
    assert r.day_state == WARN
    r = evaluate(day_total=12.0, session_costs={}, daily_budget=10.0,
                 per_session_budget=5.0, warn_ratio=0.8)
    assert r.day_state == OVER


def test_per_session_over():
    r = evaluate(day_total=0.0, session_costs={"s1": 6.0}, daily_budget=100.0,
                 per_session_budget=5.0, warn_ratio=0.8)
    assert r.session_states["s1"] == OVER


def test_crossing_fires_once():
    tracker = CrossingTracker()
    over = evaluate(12.0, {}, 10.0, 5.0, 0.8)
    assert tracker.check(over) == ["day"]
    assert tracker.check(over) == []  # already fired, edge-triggered
