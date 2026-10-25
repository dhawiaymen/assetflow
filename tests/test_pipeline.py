import json
import pytest
from PIL import Image
from assetflow.core import Options, optimize, build_atlas, pack_rectangles
from assetflow.cli import main


@pytest.fixture
def images(tmp_path):
    root = tmp_path / "input"
    root.mkdir()
    img = Image.new("RGBA", (80, 60))
    img.paste((255, 0, 80, 128), (20, 10, 60, 50))
    img.save(root / "hero.png")
    return root


def test_lossless_pixels_and_source_untouched(images, tmp_path):
    before = (images / "hero.png").read_bytes()
    r = optimize(images, tmp_path / "out")
    assert r["errors"] == [] and r["input_bytes"] > 0
    with Image.open(images / "hero.png") as src, Image.open(tmp_path / "out/hero.png.png") as dst:
        assert src.tobytes() == dst.tobytes()
    assert (images / "hero.png").read_bytes() == before
    assert r["saved_bytes"] == r["input_bytes"] - r["output_bytes"]


def test_trim_metadata_and_resize(images, tmp_path):
    r = optimize(images, tmp_path / "trim", Options(trim=True))
    f = r["files"][0]
    assert f["sourceSize"] == {"w": 80, "h": 60}
    assert f["spriteSourceSize"] == {"x": 20, "y": 10, "w": 40, "h": 40}
    r = optimize(images, tmp_path / "small", Options(max_size=20))
    assert r["files"][0]["sourceSize"] == {"w": 20, "h": 15}


def test_dry_run_writes_nothing(images, tmp_path):
    out = tmp_path / "dry"
    result = optimize(images, out, dry_run=True)
    assert result["files"] and not out.exists()


def test_duplicates_and_same_stem(images, tmp_path):
    (images / "sub").mkdir()
    (images / "sub/copy.png").write_bytes((images / "hero.png").read_bytes())
    Image.new("RGB", (9, 9), "blue").save(images / "hero.jpg")
    r = optimize(images, tmp_path / "out")
    assert len(r["files"]) == 3 and len(r["duplicates"]) == 1
    assert (tmp_path / "out/hero.jpg.png").exists()
    assert (tmp_path / "out/hero.png.png").exists()


@pytest.mark.parametrize("relative", ["input/nested", "input"])
def test_output_cannot_modify_input(images, tmp_path, relative):
    with pytest.raises((ValueError, FileExistsError)):
        optimize(images, tmp_path / relative)


def test_existing_output_is_safe(images, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "keep.txt").write_text("keep")
    with pytest.raises(FileExistsError):
        optimize(images, out)
    assert (out / "keep.txt").read_text() == "keep"


def test_invalid_image_partial_report_and_exit(images, tmp_path):
    (images / "bad.png").write_bytes(b"not a png")
    assert main(["optimize", str(images), str(tmp_path / "out")]) == 1
    report = json.loads((tmp_path / "out/manifest.json").read_text())
    assert len(report["files"]) == 1 and len(report["errors"]) == 1


def test_jpeg_white_matte(images, tmp_path):
    optimize(images, tmp_path / "out", Options(format="jpeg", quality=100))
    with Image.open(tmp_path / "out/hero.png.jpeg") as img:
        assert img.mode == "RGB"
        assert min(img.getpixel((0, 0))) >= 250


def test_webp_alpha(images, tmp_path):
    optimize(images, tmp_path / "out", Options(format="webp"))
    with Image.open(tmp_path / "out/hero.png.webp") as dst, Image.open(images / "hero.png") as src:
        assert dst.convert("RGBA").tobytes() == src.tobytes()


def test_empty_transparent_image(images, tmp_path):
    Image.new("RGBA", (12, 13)).save(images / "empty.png")
    r = optimize(images, tmp_path / "out", Options(trim=True))
    f = next(x for x in r["files"] if x["source"] == "empty.png")
    assert f["spriteSourceSize"]["w"] == 1 and f["sourceSize"]["h"] == 13


def test_atlas_reconstruction_and_gutters(images, tmp_path):
    Image.new("RGBA", (25, 20), "blue").save(images / "blue.png")
    m = build_atlas(images, tmp_path / "atlas", Options(trim=True, atlas_size=256))
    with Image.open(tmp_path / "atlas/atlas.png") as atlas:
        assert atlas.width <= 256 and atlas.height <= 256
        for name, record in m["frames"].items():
            r = record["frame"]
            s = record["spriteSourceSize"]
            cropped = atlas.crop((r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"]))
            with Image.open(images / name) as original:
                expected = original.convert("RGBA").crop(
                    (s["x"], s["y"], s["x"] + s["w"], s["y"] + s["h"])
                )
                assert cropped.tobytes() == expected.tobytes()
            assert atlas.getpixel((r["x"] - 1, r["y"])) == cropped.getpixel((0, 0))


def test_packing_no_overlap_and_deterministic():
    rects = [("a", 20, 30), ("b", 30, 40), ("c", 10, 10), ("d", 40, 20)]
    pos = pack_rectangles(rects, 64)
    assert pos == pack_rectangles(list(reversed(rects)), 64)
    for i, (a, w, h) in enumerate(rects):
        x, y = pos[a]
        for b, bw, bh in rects[i + 1 :]:
            bx, by = pos[b]
            assert x + w <= bx or bx + bw <= x or y + h <= by or by + bh <= y


def test_atlas_overflow_leaves_no_output(images, tmp_path):
    with pytest.raises(ValueError):
        build_atlas(images, tmp_path / "atlas", Options(atlas_size=32))
    assert not (tmp_path / "atlas").exists()


@pytest.mark.parametrize(
    "options",
    [
        Options(max_size=0),
        Options(quality=101),
        Options(padding=-1),
        Options(format="gif"),
        Options(extrude=17),
    ],
)
def test_options_validation(options):
    with pytest.raises(ValueError):
        options.validate()


def test_animated_input_rejected(images, tmp_path):
    a = Image.new("RGBA", (5, 5), "red")
    b = Image.new("RGBA", (5, 5), "blue")
    a.save(images / "animated.png", save_all=True, append_images=[b], duration=100, loop=0)
    r = optimize(images, tmp_path / "out")
    assert any("Animated" in e["error"] for e in r["errors"])


@pytest.mark.gui
def test_gui_constructs():
    import tkinter as tk
    from assetflow.gui import AssetApp

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("No graphical display available")
    try:
        app = AssetApp(root)
        root.update()
        assert app.mode.get() == "optimize"
    finally:
        root.destroy()


@pytest.mark.gui
def test_gui_runs_pipeline_in_worker(images, tmp_path):
    import time
    import tkinter as tk
    from assetflow.gui import AssetApp

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("No graphical display available")
    try:
        app = AssetApp(root)
        app.input.set(str(images))
        app.output.set(str(tmp_path / "gui output"))
        app.run()
        deadline = time.monotonic() + 10
        while app.busy and time.monotonic() < deadline:
            root.update()
            time.sleep(0.02)
        assert not app.busy
        assert (tmp_path / "gui output/manifest.json").exists()
        assert "ERROR:" not in app.log.get("1.0", "end")
    finally:
        root.destroy()
