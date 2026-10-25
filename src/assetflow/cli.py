import argparse
import json
import sys
from .core import Options, optimize, build_atlas


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Non-destructive image optimizer and sprite atlas packer."
    )
    sub = p.add_subparsers(dest="command")
    sub.add_parser("gui")
    for command in ("optimize", "atlas"):
        s = sub.add_parser(command)
        s.add_argument("input")
        s.add_argument("output")
        s.add_argument("--max-size", type=int, default=2048)
        s.add_argument("--trim", action="store_true")
        if command == "optimize":
            s.add_argument("--format", choices=["png", "webp", "jpeg"], default="png")
            s.add_argument("--quality", type=int, default=85)
            s.add_argument("--lossy", action="store_true")
            s.add_argument("--dry-run", action="store_true")
        else:
            s.add_argument("--atlas-size", type=int, default=2048)
            s.add_argument("--padding", type=int, default=2)
            s.add_argument("--extrude", type=int, default=1)
    args = p.parse_args(argv)
    try:
        if args.command in (None, "gui"):
            from .gui import main as gui

            gui()
            return 0
        if args.command == "optimize":
            result = optimize(
                args.input,
                args.output,
                Options(
                    format=args.format,
                    max_size=args.max_size,
                    trim=args.trim,
                    quality=args.quality,
                    lossless=not args.lossy,
                ),
                dry_run=args.dry_run,
            )
            print(json.dumps(result, indent=2))
            return 1 if result["errors"] else 0
        result = build_atlas(
            args.input,
            args.output,
            Options(
                max_size=args.max_size,
                trim=args.trim,
                atlas_size=args.atlas_size,
                padding=args.padding,
                extrude=args.extrude,
            ),
        )
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
