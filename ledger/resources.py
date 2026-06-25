from __future__ import annotations

import subprocess
from dataclasses import dataclass

try:
    import psutil as _psutil
except ImportError:  # logged as a dependency; import guarded so tests of pure fns still run
    _psutil = None


@dataclass
class GpuSnapshot:
    util: int
    vram_used: int
    vram_total: int
    temp: int


@dataclass
class SystemSnapshot:
    cpu_percent: float
    ram_used: int
    ram_total: int


@dataclass
class ProcRow:
    name: str
    pid: int
    cpu: float
    ram: int
    vram: int
    project: str | None


_GPU_QUERY = [
    "nvidia-smi",
    "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
    "--format=csv,noheader,nounits",
]
_PROC_QUERY = [
    "nvidia-smi",
    "--query-compute-apps=pid,used_memory",
    "--format=csv,noheader,nounits",
]


def parse_gpu_csv(text: str) -> GpuSnapshot | None:
    line = text.strip().splitlines()[0] if text.strip() else ""
    parts = [p.strip() for p in line.split(",")]
    if len(parts) != 4:
        return None
    try:
        util, used, total, temp = (int(p) for p in parts)
    except ValueError:
        return None
    return GpuSnapshot(util, used, total, temp)


def gpu_snapshot(run=subprocess.run) -> GpuSnapshot | None:
    try:
        proc = run(_GPU_QUERY, capture_output=True, text=True, timeout=5)
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return None
    if getattr(proc, "returncode", 1) != 0:
        return None
    return parse_gpu_csv(proc.stdout)


def gpu_processes(run=subprocess.run) -> dict[int, int]:
    try:
        proc = run(_PROC_QUERY, capture_output=True, text=True, timeout=5)
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return {}
    if getattr(proc, "returncode", 1) != 0:
        return {}
    out: dict[int, int] = {}
    for line in proc.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 2:
            continue
        try:
            out[int(parts[0])] = int(parts[1])
        except ValueError:
            continue
    return out


def system_snapshot(ps=_psutil) -> SystemSnapshot:
    vm = ps.virtual_memory()
    return SystemSnapshot(ps.cpu_percent(interval=None), vm.used, vm.total)


def ai_processes(names: list[str], project_dirs: set[str],
                 gpu_pids: dict[int, int], ps=_psutil) -> list[ProcRow]:
    wanted = {n.lower() for n in names}
    rows: list[ProcRow] = []
    for proc in ps.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
        try:
            info = proc.info
            name = (info.get("name") or "").lower()
            if not any(w in name for w in wanted):
                continue
            try:
                cwd = proc.cwd()
            except Exception:
                cwd = ""
            project = next((d for d in project_dirs if cwd and cwd.startswith(d)), None)
            mem = info.get("memory_info")
            rows.append(ProcRow(
                name=info.get("name") or "",
                pid=info.get("pid", 0),
                cpu=info.get("cpu_percent") or 0.0,
                ram=mem.rss if mem else 0,
                vram=gpu_pids.get(info.get("pid", 0), 0),
                project=project,
            ))
        except Exception:
            continue
    rows.sort(key=lambda r: (r.vram, r.cpu), reverse=True)
    return rows
