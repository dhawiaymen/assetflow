import json
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from .core import Options, optimize, build_atlas


class AssetApp(ttk.Frame):
    def __init__(self, root):
        super().__init__(root, padding=22)
        self.pack(fill="both", expand=True)
        root.title("AssetFlow · Game image pipeline")
        root.geometry("890x720")
        root.minsize(700, 600)
        self.events = queue.Queue()
        self.busy = False
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
        self.run_button = ttk.Button(self, text="Run pipeline", command=self.run)
        self.run_button.pack(anchor="w")
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
            options = Options(
                format=self.format.get(),
                max_size=int(self.size.get()),
                trim=self.trim.get(),
                quality=int(self.quality.get()),
                lossless=self.lossless.get(),
                atlas_size=int(self.atlas_size.get()),
                padding=int(self.padding.get()),
                extrude=int(self.extrude.get()),
            ).validate()
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
        self.run_button.configure(state="disabled")
        self.log.delete("1.0", "end")

        def work():
            try:

                def progress(i, total, name):
                    return self.events.put(("progress", (i, total, name)))

                result = (
                    optimize(source, output, options, dry, progress)
                    if mode == "optimize"
                    else build_atlas(source, output, options, progress)
                )
                self.events.put(("done", result))
            except Exception as exc:
                self.events.put(("error", str(exc)))

        threading.Thread(target=work, daemon=True).start()

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
                    else:
                        self.log.insert("end", json.dumps(data, indent=2) + "\n")
                self.log.see("end")
        except queue.Empty:
            pass
        self._poll_id = self.after(100, self.poll)


def main():
    root = tk.Tk()
    ttk.Style().theme_use("clam")
    AssetApp(root)
    root.mainloop()
