from ledger.resources import gpu_snapshot, parse_gpu_csv


def test_parse_gpu_csv_reads_fields():
    snap = parse_gpu_csv("14, 512, 4096, 41\n")
    assert snap.util == 14
    assert snap.vram_used == 512
    assert snap.vram_total == 4096
    assert snap.temp == 41


def test_parse_gpu_csv_returns_none_on_garbage():
    assert parse_gpu_csv("") is None
    assert parse_gpu_csv("N/A, N/A") is None


def test_gpu_snapshot_returns_none_when_nvidia_smi_missing():
    def run(*_a, **_k):
        raise FileNotFoundError("nvidia-smi")
    assert gpu_snapshot(run=run) is None
