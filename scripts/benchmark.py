"""Reproducible synthetic workload; pip install psutil before running."""
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import threading
import time
import psutil
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
try:
    process = psutil.Process()
except psutil.NoSuchProcess:
    process = None  # PID namespaces can expose a different /proc mapping.
stop = threading.Event()
peak = [0]
def sample():
    while process is not None and not stop.is_set():
        total = 0
        for item in [process, *process.children(recursive=True)]:
            try:
                total += item.memory_info().rss
            except psutil.Error:
                pass
        peak[0] = max(peak[0], total)
        stop.wait(.02)
thread = threading.Thread(target=sample, daemon=True)
thread.start()
begin = time.perf_counter()
with tempfile.TemporaryDirectory(prefix="benchmark ") as temporary:
    work = Path(temporary)
    from PIL import Image
    from assetflow.core import optimize, build_atlas, Options
    source = work / "images"
    source.mkdir()
    for index in range(1000):
        Image.new("RGBA", (64,64), (index % 256, index // 256, 120, 128)).save(source / f"{index:04}.png")
    result = optimize(source, work / "optimized")
    assert len(result["files"]) == 1000 and not result["errors"]
    for path in sorted(source.iterdir())[256:]:
        path.unlink()
    assert len(build_atlas(source, work / "atlas", Options(atlas_size=2048))["frames"]) == 256
elapsed = time.perf_counter() - begin
stop.set()
thread.join()
scope = "20 ms sampled sum of own and child RSS; shared pages may be counted more than once"
if process is None:
    import resource
    peak[0] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    scope = "Linux getrusage peak RSS of Python process only; excludes browser subprocesses"
versions = {}
for name in ("Pillow", "playwright", "psutil"):
    try:
        versions[name] = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        pass
print(json.dumps({"workload": '1000 64x64 RGBA PNG optimizations and one 256-sprite atlas', "elapsed_seconds": round(elapsed, 4), "peak_process_tree_rss_bytes": peak[0], "python": platform.python_version(), "platform": platform.platform(), "dependencies": versions, "browser_override": os.environ.get("GAMETEST_BROWSER_PATH"), "measurement": scope + "; includes fixture creation; synthetic local workload, not a Windows benchmark"}, indent=2))
