"""Non-destructive image pipeline and deterministic trimmed sprite atlas packing."""

from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import io
import json
import math
import os
import shutil
import tempfile
import warnings
from PIL import Image, ImageOps

SUPPORTED = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tga"}


class PipelineCancelled(ValueError):
    """Cancelled before publication; the staging directory is discarded."""


def check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise PipelineCancelled("Cancelled. No output was published; originals are unchanged.")


@dataclass(frozen=True)
class Options:
    format: str = "png"
    max_size: int = 2048
    trim: bool = False
    quality: int = 85
    lossless: bool = True
    padding: int = 2
    atlas_size: int = 2048
    extrude: int = 1

    def validate(self):
        if self.format not in ("png", "webp", "jpeg"):
            raise ValueError("Format must be png, webp, or jpeg")
        for key, low, high in [
            ("max_size", 1, 8192),
            ("quality", 1, 100),
            ("padding", 0, 64),
            ("atlas_size", 32, 8192),
            ("extrude", 0, 16),
        ]:
            value = getattr(self, key)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{key} must be an integer in [{low}, {high}]")
        if type(self.trim) is not bool or type(self.lossless) is not bool:
            raise ValueError("trim and lossless must be booleans")
        return self


def discover(source):
    root = Path(source).resolve()
    if not root.is_dir():
        raise ValueError("Input must be an existing folder")
    found = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not (Path(directory) / d).is_symlink())
        for filename in sorted(files):
            path = Path(directory) / filename
        # Do not follow symlinked files or read outside the requested tree.
            if (
                path.suffix.lower() in SUPPORTED
                and not path.is_symlink()
                and path.resolve().is_relative_to(root)
            ):
                found.append(path)
                if len(found) > 10000:
                    raise ValueError("Split this input into batches of at most 10,000 images")
    if not found:
        raise ValueError("No supported images found")
    if len(found) > 10000:
        raise ValueError("Split this input into batches of at most 10,000 images")
    return root, sorted(found)


def prepare(path, options):
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(path) as source:
            if getattr(source, "n_frames", 1) > 1:
                raise ValueError("Animated images are not supported")
            if source.width * source.height > 40_000_000:
                raise ValueError("Image exceeds 40 million pixels")
            img = ImageOps.exif_transpose(source).convert("RGBA")
    original = list(img.size)
    img.thumbnail((options.max_size, options.max_size), Image.Resampling.LANCZOS)
    resized = list(img.size)
    box = img.getchannel("A").getbbox() if options.trim else (0, 0, *img.size)
    if box is None:
        box = (0, 0, 1, 1)
        img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    else:
        img = img.crop(box)
    meta = {
        "originalSize": original,
        "sourceSize": {"w": resized[0], "h": resized[1]},
        "spriteSourceSize": {"x": box[0], "y": box[1], "w": img.width, "h": img.height},
        "trimmed": list(box) != [0, 0, *resized],
    }
    # Strip EXIF, ICC, and comments from output; no color-space conversion is claimed.
    clean = Image.new("RGBA", img.size)
    clean.paste(img)
    return clean, meta


def encode(img, options):
    stream = io.BytesIO()
    if options.format == "png":
        img.save(stream, format="PNG", optimize=True)
    elif options.format == "webp":
        img.save(
            stream,
            format="WEBP",
            lossless=options.lossless,
            quality=options.quality,
            method=6,
            exact=True,
        )
    else:
        # JPEG cannot preserve alpha: use an explicit, documented white matte.
        background = Image.new("RGB", img.size, "white")
        background.paste(img, mask=img.getchannel("A"))
        background.save(
            stream, format="JPEG", quality=options.quality, optimize=True, progressive=True
        )
    return stream.getvalue()


def destination(source, output):
    out = Path(output).resolve()
    if out.exists():
        raise FileExistsError("Output must be a new folder; existing output is never overwritten")
    if out == source or out.is_relative_to(source) or source.is_relative_to(out):
        raise ValueError(
            "Output must be separate from the input folder, not an ancestor or descendant"
        )
    return out


def staging_dir(out):
    out.parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=".assetflow-", dir=out.parent))


def optimize(source, output, options=None, dry_run=False, progress=None, cancel=None):
    options = (options or Options()).validate()
    root, paths = discover(source)
    out = destination(root, output)
    stage = None if dry_run else staging_dir(out)
    report = {
        "version": 1,
        "operation": "optimize",
        "options": asdict(options),
        "files": [],
        "errors": [],
        "input_bytes": 0,
        "output_bytes": 0,
        "duplicates": [],
        "dry_run": dry_run,
    }
    seen = {}
    try:
        for i, path in enumerate(paths):
            check_cancel(cancel)
            name = path.relative_to(root).as_posix()
            if progress:
                progress(i + 1, len(paths), name)
            try:
                img, meta = prepare(path, options)
                data = encode(img, options)
                pixel_hash = hashlib.sha256(str(img.size).encode())
                pixel_hash.update(img.tobytes())
                digest = pixel_hash.hexdigest()
                img.close()
                if digest in seen:
                    report["duplicates"].append({"file": name, "same_pixels_as": seen[digest]})
                else:
                    seen[digest] = name
                # Preserve the original extension in the new name to avoid same-stem collisions.
                relative = path.relative_to(root).as_posix() + "." + options.format
                if stage:
                    target = stage / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                before = path.stat().st_size
                after = len(data)
                report["input_bytes"] += before
                report["output_bytes"] += after
                report["files"].append(
                    {
                        "source": name,
                        "output": relative,
                        "input_bytes": before,
                        "output_bytes": after,
                        "sha256": hashlib.sha256(data).hexdigest(),
                        **meta,
                    }
                )
            except (
                OSError,
                ValueError,
                Image.DecompressionBombError,
                Image.DecompressionBombWarning,
            ) as exc:
                report["errors"].append({"source": name, "error": str(exc)})
        report["saved_bytes"] = report["input_bytes"] - report["output_bytes"]
        check_cancel(cancel)
        if stage:
            (stage / "manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            os.rename(stage, out)
        return report
    except BaseException:
        if stage:
            shutil.rmtree(stage, ignore_errors=True)
        raise


def pack_rectangles(rectangles, size):
    """Shelf packing; deterministic order, no rotation, reject rather than crop."""
    x = y = row_height = 0
    positions = {}
    for name, w, h in sorted(rectangles, key=lambda r: (-r[2], -r[1], r[0])):
        if w > size or h > size:
            raise ValueError(f"{name} is too large for this atlas")
        if x + w > size:
            x = 0
            y += row_height
            row_height = 0
        if y + h > size:
            raise ValueError("Sprites do not fit. Increase atlas size or split the input folder.")
        positions[name] = (x, y)
        x += w
        row_height = max(row_height, h)
    return positions


def build_atlas(source, output, options=None, progress=None, cancel=None):
    options = (options or Options(trim=True)).validate()
    root, paths = discover(source)
    out = destination(root, output)
    sprites = []
    rectangles = []
    margin = options.padding + options.extrude
    pixels = 0
    # Validate and pack before allocating the output or writing anything.
    for i, path in enumerate(paths):
        check_cancel(cancel)
        name = path.relative_to(root).as_posix()
        if progress:
            progress(i + 1, len(paths), name)
        img, meta = prepare(path, options)
        pixels += img.width * img.height
        if pixels > 64_000_000:
            raise ValueError("Atlas input exceeds the 64 million pixel memory budget")
        sprites.append((name, path, meta, img.size))
        rectangles.append((name, img.width + 2 * margin, img.height + 2 * margin))
        img.close()
    positions = pack_rectangles(rectangles, options.atlas_size)
    used_w = max(positions[n][0] + w for n, w, h in rectangles)
    used_h = max(positions[n][1] + h for n, w, h in rectangles)

    # Power-of-two output, bounded by the requested size even for non-POT limits.
    def pot(n):
        return min(options.atlas_size, 2 ** math.ceil(math.log2(max(1, n))))

    atlas = Image.new("RGBA", (pot(used_w), pot(used_h)))
    frames = {}
    for name, path, meta, expected_size in sprites:
        check_cancel(cancel)
        img, current_meta = prepare(path, options)
        if img.size != expected_size or current_meta != meta:
            raise ValueError(f"Input changed during packing: {name}. Retry with stable inputs.")
        px, py = positions[name]
        x = px + margin
        y = py + margin
        e = options.extrude
        if e:
            # Clamp edge pixels into the gutter, including corners.
            padded = Image.new("RGBA", (img.width + 2 * e, img.height + 2 * e))
            padded.paste(img, (e, e))
            padded.paste(img.crop((0, 0, img.width, 1)).resize((img.width, e)), (e, 0))
            padded.paste(
                img.crop((0, img.height - 1, img.width, img.height)).resize((img.width, e)),
                (e, e + img.height),
            )
            padded.paste(
                padded.crop((e, 0, e + 1, padded.height)).resize((e, padded.height)), (0, 0)
            )
            padded.paste(
                padded.crop((e + img.width - 1, 0, e + img.width, padded.height)).resize(
                    (e, padded.height)
                ),
                (e + img.width, 0),
            )
            atlas.paste(padded, (x - e, y - e))
        else:
            atlas.paste(img, (x, y))
        frames[name] = {
            "frame": {"x": x, "y": y, "w": img.width, "h": img.height},
            "rotated": False,
            **meta,
        }
        img.close()
    manifest = {
        "frames": frames,
        "meta": {
            "app": "AssetFlow",
            "version": "0.1.0",
            "image": "atlas.png",
            "format": "RGBA8888",
            "size": {"w": atlas.width, "h": atlas.height},
            "scale": "1",
            "padding": options.padding,
            "extrude": options.extrude,
        },
    }
    stage = staging_dir(out)
    try:
        check_cancel(cancel)
        atlas.save(stage / "atlas.png", optimize=True)
        (stage / "atlas.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        check_cancel(cancel)
        os.rename(stage, out)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return manifest
