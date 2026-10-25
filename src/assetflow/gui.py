import json
import io
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
from .core import Options, optimize, build_atlas, prepare, encode


class AssetApp(ttk.Frame):
    def __init__(self, root):
        super().__init__(root, padding=22)
        self.pack(fill="both", expand=True)
        root.title("AssetFlow · Game image pipeline")
        root.geometry("890x720")
        root.minsize(700, 600)
        self.events = queue.Queue()
        self.busy = False
        self.cancel = threading.Event()
        ttk.Label(self, text="AssetFlow", font=("Segoe UI", 24, "bold")).pack(anchor="w")
        ttk.Label(
            self, text="Resize, trim, convert, and pack game assets. Your originals stay untouched."
        ).pack(anchor="w", pady=(0, 18))
        paths = ttk.Frame(self)
        paths.pack(fill="x")
        self.input = tk.StringVar()
        self.output = tk.StringVar()
        for row, (label, var, fn) in enumerate(
            [
                ("Input folder", self.input, self.input_folder),
                ("New output folder", self.output, self.output_folder),
            ]
        ):
            ttk.Label(paths, text=label).grid(row=row, column=0, sticky="w", pady=6)
            ttk.Entry(paths, textvariable=var).grid(row=row, column=1, sticky="ew", padx=10)
            ttk.Button(paths, text="Browse", command=fn).grid(row=row, column=2)
        paths.columnconfigure(1, weight=1)
        opts = ttk.LabelFrame(self, text="Pipeline options", padding=12)
        opts.pack(fill="x", pady=14)
        self.mode = tk.StringVar(value="optimize")
        self.format = tk.StringVar(value="png")
        self.size = tk.StringVar(value="2048")
        self.quality = tk.StringVar(value="85")
        self.atlas_size = tk.StringVar(value="2048")
        self.padding = tk.StringVar(value="2")
        self.extrude = tk.StringVar(value="1")
        self.trim = tk.BooleanVar(value=False)
        self.lossless = tk.BooleanVar(value=True)
        self.dry = tk.BooleanVar(value=False)
        fields = [
            ("Operation", self.mode, ["optimize", "atlas"]),
            ("Format", self.format, ["png", "webp", "jpeg"]),
            ("Max image side", self.size, None),
            ("Quality", self.quality, None),
            ("Atlas limit", self.atlas_size, None),
            ("Padding", self.padding, None),
            ("Edge extrusion", self.extrude, None),
        ]
        for i, (label, var, values) in enumerate(fields):
            row, col = divmod(i, 3)
            col *= 2
            ttk.Label(opts, text=label).grid(row=row, column=col, sticky="w", padx=5, pady=6)
            w = (
                ttk.Combobox(opts, textvariable=var, values=values, state="readonly", width=11)
                if values
                else ttk.Entry(opts, textvariable=var, width=10)
            )
            w.grid(row=row, column=col + 1, padx=6)
        checks = ttk.Frame(self)
        checks.pack(fill="x")
        for label, var in [
            ("Trim transparent borders", self.trim),
            ("Lossless WebP", self.lossless),
            ("Dry run (optimize only)", self.dry),
        ]:
            ttk.Checkbutton(checks, text=label, variable=var).pack(side="left", padx=8)
        ttk.Label(
            self,
            text="Atlas output is PNG + JSON. JPEG uses a white background. Metadata is removed.",
        ).pack(anchor="w", pady=12)
        actions = ttk.Frame(self)
        actions.pack(fill="x")
        self.run_button = ttk.Button(actions, text="Run pipeline", command=self.run)
        self.run_button.pack(side="left")
        ttk.Button(actions, text="Preview one image", command=self.preview).pack(side="left", padx=8)
        ttk.Button(actions, text="Cancel", command=self.cancel.set).pack(side="left")
        self.progress = ttk.Progressbar(self, mode="determinate")
        self.progress.pack(fill="x", pady=10)
        self.log = tk.Text(self, height=14, wrap="word", font=("Consolas", 10))
        self.log.pack(fill="both", expand=True)
        self._poll_id = self.after(100, self.poll)
        root.protocol("WM_DELETE_WINDOW", self.close)

    def close(self):
        if self.busy:
            messagebox.showinfo(
                "Pipeline running", "Let the current pipeline finish before closing."
            )
        else:
            self.winfo_toplevel().destroy()

    def destroy(self):
        self.after_cancel(self._poll_id)
        # Tk variables must be finalized on the UI thread. A later image worker
        # can otherwise trigger cyclic GC for an already-destroyed workbench.
        for name, value in list(vars(self).items()):
            if isinstance(value, tk.Variable):
                setattr(self, name, None)
        del value
        super().destroy()

    def input_folder(self):
        p = filedialog.askdirectory()
        if p:
            self.input.set(p)

    def output_folder(self):
        p = filedialog.asksaveasfilename(
            title="Name a NEW output folder", initialfile="optimized-assets"
        )
        if p:
            self.output.set(p)

    def run(self):
        if self.busy:
            return
        try:
            if not self.input.get() or not self.output.get():
                raise ValueError("Choose both folders.")
            options = self.options()
            mode = self.mode.get()
            dry = self.dry.get()
            if mode == "atlas" and dry:
                raise ValueError("Dry run is available for optimize only.")
            source = self.input.get()
            output = self.output.get()
        except ValueError as exc:
            messagebox.showerror("Invalid options", str(exc))
            return
        self.busy = True
        self.cancel.clear()
        self.run_button.configure(state="disabled")
        self.log.delete("1.0", "end")

        def work():
            try:

                def progress(i, total, name):
                    return self.events.put(("progress", (i, total, name)))

                result = (
                    optimize(source, output, options, dry, progress, self.cancel)
                    if mode == "optimize"
                    else build_atlas(source, output, options, progress, self.cancel)
                )
                self.events.put(("done", result))
            except Exception as exc:
                self.events.put(("error", str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def options(self):
        return Options(
            format=self.format.get(), max_size=int(self.size.get()), trim=self.trim.get(),
            quality=int(self.quality.get()), lossless=self.lossless.get(),
            atlas_size=int(self.atlas_size.get()), padding=int(self.padding.get()),
            extrude=int(self.extrude.get()),
        ).validate()

    def preview(self):
        if self.busy:
            return
        try:
            options = self.options()
        except ValueError as exc:
            messagebox.showerror("Invalid options", str(exc))
            return
        path = filedialog.askopenfilename(
            title="Preview an image without writing output", initialdir=self.input.get() or None,
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp *.tga")],
        )
        if not path:
            return
        self.busy = True
        self.run_button.configure(state="disabled")

        def work():
            try:
                before, metadata = prepare(path, Options(max_size=360))
                processed, _ = prepare(path, options)
                data = encode(processed, options)
                size = processed.size
                processed.close()
                with Image.open(io.BytesIO(data)) as decoded:
                    after = decoded.convert("RGBA")
                after.thumbnail((360, 300))
                before.thumbnail((360, 300))
                self.events.put(("preview", (path, before, after, metadata, size, len(data))))
            except Exception as exc:
                self.events.put(("error", str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def show_preview(self, result):
        path, before, after, metadata, size, output_bytes = result
        window = tk.Toplevel(self)
        window.title(f"Preview · {Path(path).name}")
        frame = ttk.Frame(window, padding=16)
        frame.pack(fill="both", expand=True)
        photos = []
        labels = [
            f"Original: {metadata['originalSize']} · {Path(path).stat().st_size:,} bytes",
            f"Encoded output: {size[0]} × {size[1]} · {output_bytes:,} bytes",
        ]
        for col, (img, label) in enumerate(zip((before, after), labels)):
            checker = Image.new("RGBA", img.size)
            for y in range(0, img.height, 12):
                for x in range(0, img.width, 12):
                    color = "#cccccc" if (x // 12 + y // 12) % 2 else "#eeeeee"
                    checker.paste(color, (x, y, min(x + 12, img.width), min(y + 12, img.height)))
            checker.alpha_composite(img)
            photo = ImageTk.PhotoImage(checker)
            photos.append(photo)
            ttk.Label(frame, text=label).grid(row=0, column=col, padx=10, pady=8)
            ttk.Label(frame, image=photo).grid(row=1, column=col, padx=10)
        window.preview_images = photos
        ttk.Label(frame, text="Scaled previews. Checkerboard indicates transparency. No output files were written.").grid(row=2, column=0, columnspan=2, pady=12)

    def poll(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "progress":
                    i, total, name = data
                    self.progress.configure(maximum=total, value=i)
                    self.log.insert("end", f"{i}/{total}  {name}\n")
                else:
                    self.busy = False
                    self.run_button.configure(state="normal")
                    if kind == "error":
                        self.log.insert("end", f"ERROR: {data}\n")
                    elif kind == "preview":
                        self.show_preview(data)
                    else:
                        summary = {k: v for k, v in data.items() if k not in ("files", "frames")}
                        summary["processed_count"] = len(data.get("files", data.get("frames", {})))
                        self.log.insert("end", json.dumps(summary, indent=2) + "\n")
                if int(self.log.index("end-1c").split(".")[0]) > 500:
                    self.log.delete("1.0", "100.0")
                self.log.see("end")
        except queue.Empty:
            pass
        self._poll_id = self.after(100, self.poll)


def main():
    root = tk.Tk()
    ttk.Style().theme_use("clam")
    AssetApp(root)
    root.mainloop()
