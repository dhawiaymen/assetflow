"""Exercise the packaged app on a real Windows runner, including Tk startup."""
import json
import platform
from pathlib import Path
import tempfile
import traceback
import tkinter as tk


def run(result_path):
    result = {"status": "failed", "platform": platform.platform(), "checks": []}
    root = None
    try:
        with tempfile.TemporaryDirectory(prefix="portable smoke ") as temporary:
            work = Path(temporary)
            from PIL import Image
            from .core import Options, optimize, build_atlas
            from .gui import AssetApp
            source = work / "input"
            source.mkdir()
            Image.new("RGBA", (20, 16), (255, 80, 20, 128)).save(source / "hero.png")
            original = (source / "hero.png").read_bytes()
            report = optimize(source, work / "optimized", Options(format="webp"))
            assert not report["errors"]
            with Image.open(source / "hero.png") as before, Image.open(work / "optimized/hero.png.webp") as after:
                assert before.tobytes() == after.convert("RGBA").tobytes()
            atlas = build_atlas(source, work / "atlas", Options(atlas_size=64))
            assert len(atlas["frames"]) == 1
            assert (source / "hero.png").read_bytes() == original
            result["checks"] += ["WebP alpha roundtrip", "atlas PNG and JSON", "original preserved"]
            root = tk.Tk()
            app = AssetApp(root)
            root.update()
            assert app.options().format == "png"
            result["checks"].append("native Tk workbench")
            root.destroy()
            root = None
        result["status"] = "passed"
    except Exception:
        result["error"] = traceback.format_exc()
    finally:
        if root is not None:
            root.destroy()
        Path(result_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0 if result["status"] == "passed" else 1
