#!/usr/bin/env python3
"""
export.py
=========
Unified command-line interface for raw_to_woudc.

Subcommands:
  woudc    Export to WOUDC extCSV format
  aims     Export to NASA AIMS (.bXX) format

Examples:
    # Export SHARP files to WOUDC
    python export.py woudc --sdk so240111.q10 so240112.q10

    # Export MR files to WOUDC
    python export.py woudc --mr mr_20211020_1146.txt

    # Export mixed stations
    python export.py woudc --sdk so*.q* --mr mr_*.txt -o output/

    # Export to NASA AIMS
    python export.py aims --sdk so240111.q10 -o aims_output/
"""

import sys
import argparse
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE / "src"))

from sharp_dqa import parse_sharp, apply_dqa
from nogdb_mr_parser import load_nogdb_mr
from woudc_export import write_woudc_csv, write_woudc_batch
from nasaaims_export import write_nasa_aims, write_nasa_aims_batch


def _resolve_files(patterns: list[str]) -> list[Path]:
    """Resolve file paths and glob patterns into sorted file list."""
    files: list[Path] = []
    for p in patterns:
        path = Path(p)
        if path.is_absolute():
            if path.is_file():
                files.append(path)
            else:
                for f in sorted(path.parent.glob(path.name)):
                    if f.is_file():
                        files.append(f)
        else:
            for f in sorted(Path().glob(p)):
                if f.is_file():
                    files.append(f)
    return sorted(set(files))


def cmd_woudc(args):
    sdk_files = _resolve_files(args.sdk) if args.sdk else []
    mr_files = _resolve_files(args.mr) if args.mr else []

    if not sdk_files and not mr_files:
        print("No files specified. Use --sdk and/or --mr with file paths or glob patterns.")
        return 1

    out = Path(args.output) if args.output else Path.cwd()
    out.mkdir(parents=True, exist_ok=True)

    results = []
    for f in sdk_files:
        try:
            meta, df = parse_sharp(f)
            if args.dqa:
                df = apply_dqa(df, meta)
            results.append((meta, df))
            print(f"  OK  SDK {f.name}")
        except Exception as e:
            print(f"  ERR SDK {f.name}: {e}")

    for f in mr_files:
        try:
            meta, df = load_nogdb_mr(f, apply_dqa_flag=args.dqa)
            results.append((meta, df))
            print(f"  OK  MR  {f.name}")
        except Exception as e:
            print(f"  ERR MR  {f.name}: {e}")

    if results:
        written = write_woudc_batch(results, output_dir=str(out))
        print(f"\n{len(written)} WOUDC file(s) written to {out}")
    return 0


def cmd_aims(args):
    sdk_files = _resolve_files(args.sdk) if args.sdk else []
    mr_files = _resolve_files(args.mr) if args.mr else []

    if not sdk_files and not mr_files:
        print("No files specified. Use --sdk and/or --mr with file paths or glob patterns.")
        return 1

    out = Path(args.output) if args.output else Path.cwd()
    out.mkdir(parents=True, exist_ok=True)

    for f in sdk_files:
        try:
            meta, df = parse_sharp(f)
            if args.dqa:
                df = apply_dqa(df, meta)
            fpath = write_nasa_aims(meta, df, output_dir=out, station_key="sdk")
            print(f"  OK  SDK {f.name} -> {fpath.name}")
        except Exception as e:
            print(f"  ERR SDK {f.name}: {e}")

    for f in mr_files:
        try:
            meta, df = load_nogdb_mr(f, apply_dqa_flag=args.dqa)
            fpath = write_nasa_aims(meta, df, output_dir=out, station_key="mr")
            print(f"  OK  MR  {f.name} -> {fpath.name}")
        except Exception as e:
            print(f"  ERR MR  {f.name}: {e}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="raw_to_woudc export tool")
    parser.add_argument("--no-dqa", dest="dqa", action="store_false", default=True,
                        help="Skip DQA corrections")

    sub = parser.add_subparsers(dest="command", required=True)

    p_woudc = sub.add_parser("woudc", help="Export to WOUDC extCSV")
    p_woudc.add_argument("--sdk", nargs="*", default=[], help="SHARP file(s) or glob pattern")
    p_woudc.add_argument("--mr", nargs="*", default=[], help="MR file(s) or glob pattern")
    p_woudc.add_argument("-o", "--output", default=None, help="Output directory")
    p_woudc.set_defaults(func=cmd_woudc)

    p_aims = sub.add_parser("aims", help="Export to NASA AIMS .bXX")
    p_aims.add_argument("--sdk", nargs="*", default=[], help="SHARP file(s) or glob pattern")
    p_aims.add_argument("--mr", nargs="*", default=[], help="MR file(s) or glob pattern")
    p_aims.add_argument("-o", "--output", default=None, help="Output directory")
    p_aims.set_defaults(func=cmd_aims)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
