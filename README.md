# AssetFlow

**A non-destructive image pipeline for small game teams.**

AssetFlow is a Windows-oriented desktop and CLI tool for preparing raster
game assets: resize, trim transparent margins, convert, inspect duplicates,
and pack sprites into a texture atlas with JSON coordinates.

Version **0.1.0**, initial release candidate. Python + Pillow. MIT licensed.
No account, cloud processing, analytics, or AI service is required.

## Features

- Recursive PNG, JPEG, WebP, BMP, and TGA input.
- Aspect-preserving downscaling with Lanczos filtering; never upscales.
- Optional alpha trimming with original dimensions and crop offsets recorded.
- PNG, lossless/lossy WebP, and JPEG output. PNG preserves RGBA pixels when
  resizing and trimming are disabled. JPEG explicitly uses a white matte.
- SHA-256 output checksums, exact processed-pixel duplicate detection, byte
  totals, and per-file errors in a JSON manifest.
- Deterministic, single-page sprite atlas packing with padding, clamped edge
  extrusion, power-of-two sizing where the limit permits, and no rotation.
- Dry-run optimization computes actual encoded sizes without writing output.
- GUI work runs in a background thread while progress remains visible.

## Windows quick start

Install **Python 3.11+** from [python.org](https://www.python.org/downloads/windows/)
with the Python launcher and Tcl/Tk. Extract the project, run **`Setup.cmd`**
once, then **`Start.cmd`**. Setup installs Pillow in the local `.venv` and needs
internet access. Subsequent image processing is offline.

Or use PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m assetflow gui
```

Choose an input folder and a **new output folder outside the input tree**.
Choose Optimize or Atlas and run the pipeline. Each run has its own output;
the tool does not overwrite originals or an earlier result.

## CLI examples

```powershell
python -m assetflow optimize .\art .\optimized --max-size 1024 --trim
python -m assetflow optimize .\art .\webp --format webp --lossy --quality 85
python -m assetflow optimize .\art .\estimate --dry-run
python -m assetflow atlas .\art .\atlas --trim --atlas-size 2048 --padding 2 --extrude 1
```

The optimizer preserves relative folders and appends the new extension:
`characters/hero.png` becomes `characters/hero.png.webp`. This prevents a
same-stem `hero.jpg` from colliding with it. Compression can increase file
size, and negative savings are reported honestly. Duplicates are reported,
not deleted or silently replaced. Sizes include successful image outputs,
not the manifest or failed inputs. Exit codes: **0** success, **1** partial
batch with per-file errors, **2** invalid arguments or operation failure.

## Atlas format

Outputs are always `atlas.png` and `atlas.json`. Each frame uses relative input
paths as keys and records `frame`, `rotated:false`, `trimmed`, `sourceSize`,
`spriteSourceSize`, and `originalSize`. `sourceSize` is the size after optional
downscaling and before trimming; `originalSize` is before resizing. Reconstruct
the sprite by pasting its atlas rectangle at the trim offset onto a transparent
`sourceSize` canvas. See [`docs/FORMAT.md`](docs/FORMAT.md).

## Tests and Windows build

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m build
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```

Tests compare pixels and alpha channels, reconstruct atlas frames, check
non-overlap, verify read-only behavior, and exercise corrupt and animated
inputs. GitHub Actions is configured for Windows/Ubuntu and Python 3.11–3.13.
No Windows executable or successful hosted CI run is implied by these files.
See the supplied validation record and [`docs/WINDOWS.md`](docs/WINDOWS.md).

## Limitations and resource bounds

Animated images, vector graphics, 3D meshes, audio, normal-map-aware filtering,
GPU texture formats (KTX/DDS), multipage atlases, and sprite rotation are not
implemented. Shelf packing is predictable but not optimal; a layout can fail
even if a more advanced packer could fit it. Split the batch or increase the
limit. Atlas limits above 4096 may consume substantial memory.

Inputs are capped at 40 million pixels per image and 10,000 files per batch;
atlases additionally cap processed input at 64 million pixels. EXIF orientation
is applied and metadata (including ICC profiles) is removed. No color-management
conversion is performed: use sRGB assets. Fully transparent trimmed images
become a 1×1 transparent frame. Symlinked files outside the tree are ignored.
Atlas creation is all-or-nothing; optimization reports individual failures.

## Contributing / license

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and
[LICENSE](LICENSE). Maintainer: [dhawiaymen](https://github.com/dhawiaymen).
The initial implementation was AI-assisted. No adoption metrics are claimed.
