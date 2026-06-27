# tests/ledger/test_main.py
from datetime import datetime, timezone

from ledger.__main__ import _show_resources, build_state
from ledger.aggregate import Aggregator
from ledger.config import Config
from ledger.models import UsageEvent
from ledger.resources import GpuSnapshot, ProcRow


def _fake_run(query, **_kw):
    class R:
        returncode = 0
        stdout = "0, 0, 4096, 40\n"
    return R()


def _fake_ps():
    import types
    vm = types.SimpleNamespace(used=1_000_000_000, total=8_000_000_000)
    return types.SimpleNamespace(
        cpu_percent=lambda interval=None: 5.0,
        virtual_memory=lambda: vm,
        process_iter=lambda attrs: iter([]),
    )


def test_build_state_assembles_snapshot():
    agg = Aggregator()
    agg.add(UsageEvent(
        session_id="s", project="proj", model="claude-opus-4-8",
        timestamp=datetime(2026, 6, 25, 12, tzinfo=timezone.utc), request_id="r",
        input_tokens=1_000_000, output_tokens=0, cache_read_tokens=0,
        cache_write_5m_tokens=0, cache_write_1h_tokens=0,
        web_search_requests=0, web_fetch_requests=0,
    ))
    state = build_state(agg, Config(), datetime(2026, 6, 25, 12, tzinfo=timezone.utc),
                        run=_fake_run, ps=_fake_ps())
    assert state.totals.all_time == 1_000_000  # 1M input tokens x weight 1.0
    assert state.gpu is not None
    assert len(state.sessions) == 1
    assert state.show_resources is False  # auto: idle GPU + no busy procs -> hidden


def test_show_resources_gate():
    gpu_idle = GpuSnapshot(0, 0, 4096, 40)
    gpu_busy = GpuSnapshot(55, 1200, 4096, 60)
    busy = [ProcRow("python", 1, 90.0, 100, 0)]
    idle = [ProcRow("node", 1, 1.0, 100, 0)]
    assert _show_resources("always", gpu_idle, {}, idle) is True
    assert _show_resources("never", gpu_busy, {1: 500}, busy) is False
    assert _show_resources("auto", gpu_idle, {}, idle) is False
    assert _show_resources("auto", gpu_busy, {}, idle) is True      # GPU utilisation
    assert _show_resources("auto", gpu_idle, {1: 500}, idle) is True  # GPU compute app
    assert _show_resources("auto", gpu_idle, {}, busy) is True      # CPU-bound process
