import threading
import weakref
import pytest
from PIL import Image
from assetflow.core import optimize, build_atlas, PipelineCancelled, discover


@pytest.mark.gui
def test_destroy_releases_tk_variables_on_ui_thread():
    import tkinter as tk
    from assetflow.gui import AssetApp
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("No display")
    app = AssetApp(root)
    variables = [weakref.ref(value) for value in vars(app).values() if isinstance(value, tk.Variable)]
    assert variables
    root.destroy()
    # No GC timing assumption: the destroyed app can stay referenced by tests
    # or callbacks without retaining Tk variables for a worker to finalize.
    assert all(reference() is None for reference in variables)


@pytest.mark.parametrize("operation", [optimize, build_atlas])
def test_cancellation_publishes_nothing(tmp_path, operation):
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGBA", (20, 20), "red").save(source / "a.png")
    Image.new("RGBA", (20, 20), "blue").save(source / "b.png")
    before = {p.name: p.read_bytes() for p in source.iterdir()}
    cancel = threading.Event()
    def progress(i, total, name):
        if i == 1:
            cancel.set()
    with pytest.raises(PipelineCancelled):
        operation(source, tmp_path / "out", progress=progress, cancel=cancel)
    assert not (tmp_path / "out").exists()
    assert not list(tmp_path.glob(".assetflow-*"))
    assert before == {p.name: p.read_bytes() for p in source.iterdir()}


def test_symlink_directory_is_not_traversed(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    Image.new("RGBA", (20, 20)).save(source / "keep.png")
    Image.new("RGBA", (20, 20)).save(outside / "secret.png")
    try:
        (source / "linked").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Symlinks not permitted")
    _, found = discover(source)
    assert [p.name for p in found] == ["keep.png"]


@pytest.mark.gui
def test_before_after_preview_is_real_and_read_only(tmp_path, monkeypatch):
    import time
    import tkinter as tk
    from assetflow.gui import AssetApp
    source = tmp_path / "image.png"
    Image.new("RGBA", (80, 60), (255, 0, 0, 100)).save(source)
    original = source.read_bytes()
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("No display")
    try:
        app = AssetApp(root)
        app.size.set("40")
        monkeypatch.setattr("assetflow.gui.filedialog.askopenfilename", lambda **kw: str(source))
        app.preview()
        deadline = time.monotonic() + 10
        while app.busy and time.monotonic() < deadline:
            root.update()
            time.sleep(.01)
        assert not app.busy
        windows = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)]
        assert len(windows) == 1
        assert len(windows[0].preview_images) == 2
        assert source.read_bytes() == original
        assert list(tmp_path.iterdir()) == [source]
    finally:
        root.destroy()
