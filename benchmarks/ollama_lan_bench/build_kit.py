#!/usr/bin/env python3
"""Build the offline Windows client kit for bench_ollama.py.

Run this on a machine WITH internet access (e.g. the Linux server); the
result is a single ``dist/ollama_bench_kit.zip`` that works on offline
Windows clients with no Python, no uv, no installation:

    kit/
      python/            official CPython "embeddable package" (amd64)
      bench_ollama.py    the benchmark script (stdlib-only)
      swe_bench_vllm.jsonl
      run_bench.bat      runs python\\python.exe bench_ollama.py, forwards args
      README_KIT.txt     short Polish instructions for the operator

Stdlib-only on purpose — it runs with any system ``python3`` (or
``uv run build_kit.py``). Assembling a Windows kit on Linux is fine: nothing
is executed, files are only downloaded and repacked. Windows text files are
written with CRLF line endings.

Integrity: the downloaded zip is structurally validated (opens as a zip,
contains ``python.exe`` and the stdlib archive) and its SHA256 is printed.
Pin it on subsequent builds with ``--expected-sha256`` (or verify the MD5
against the python.org release page).
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

PYTHON_EMBED_VERSION = "3.12.10"
PYTHON_EMBED_URL = (
    "https://www.python.org/ftp/python/"
    f"{PYTHON_EMBED_VERSION}/python-{PYTHON_EMBED_VERSION}-embed-amd64.zip"
)

_HERE = Path(__file__).resolve().parent
_DEFAULT_DATASET = (
    _HERE.parent.parent
    / "results"
    / "runs"
    / "2026-06-05_w1_evidence"
    / "benchmarking"
    / "swe_bench_vllm.jsonl"
)
_KIT_DIR_NAME = "ollama_bench_kit"

_RUN_BAT = (
    "@echo off\r\n"
    '"%~dp0python\\python.exe" "%~dp0bench_ollama.py" %*\r\n'
)

_README_KIT = """\
ollama-lan-bench — zestaw offline (Windows)
===========================================

Zestaw jest samowystarczalny: wbudowany Python + skrypt + dataset.
Niczego nie instalujesz. Rozpakuj caly katalog w dowolne miejsce
(np. C:\\ollama_bench) i uruchamiaj z wiersza polecen (cmd).

Szybki test polaczenia (1 zapytanie, bez czekania na godzine):

    run_bench.bat --base-url http://ADRES_SERWERA:11434 --model NAZWA_MODELU ^
        --num-requests 1 --warmup 0

Wlasciwy pomiar na datasecie SWE, start o 08:30 czasu lokalnego:

    run_bench.bat --base-url http://ADRES_SERWERA:11434 --model NAZWA_MODELU ^
        --dataset "%~dp0swe_bench_vllm.jsonl" --num-requests 10 --warmup 1 ^
        --start-at 08:30

Uwagi:
- NAZWA_MODELU = tag z `ollama list` na serwerze (np. llama3.3:70b).
- Przy kilku klientach naraz: ta sama --start-at, ale KAZDY klient inny
  --dataset-offset (np. 0 / 50 / 100), zeby brac rozne prompty.
- Wyniki laduja w podkatalogu results\\<znacznik-czasu>\\:
  results.jsonl (wiersz na zapytanie) i summary.json (agregaty p50/p95).
  Po tescie zgraj caly katalog results\\ z powrotem (pendrive).
- Okno musi zostac otwarte az do konca testu; skrypt czekajac na godzine
  startu wypisuje odliczanie co 30 s.
"""


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_embed_zip(path: Path) -> None:
    """Structural sanity check: a real embeddable package, not an error page."""
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
    except zipfile.BadZipFile as exc:
        raise ValueError(f"{path}: not a valid zip file ({exc})") from None
    if "python.exe" not in names:
        raise ValueError(f"{path}: python.exe missing — not an embeddable package")
    if not any(name.startswith("python3") and name.endswith(".zip") for name in names):
        raise ValueError(f"{path}: stdlib archive (python3xx.zip) missing")


def download_embeddable(
    dest_dir: Path,
    *,
    url: str = PYTHON_EMBED_URL,
    expected_sha256: str | None = None,
) -> Path:
    """Download (with caching) and validate the embeddable package zip."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / url.rsplit("/", 1)[-1]
    if not target.exists():
        print(f"downloading {url}")
        with urllib.request.urlopen(url, timeout=60.0) as response:
            with target.open("wb") as handle:
                shutil.copyfileobj(response, handle)
    else:
        print(f"using cached {target}")
    validate_embed_zip(target)
    digest = sha256_of(target)
    if expected_sha256 is not None and digest != expected_sha256.lower():
        raise ValueError(
            f"{target}: SHA256 mismatch — expected {expected_sha256}, got {digest}"
        )
    print(f"embeddable sha256: {digest}")
    if expected_sha256 is None:
        print("(pin it on future builds with --expected-sha256)")
    return target


def assemble_kit(
    *,
    embed_zip: Path,
    dist_dir: Path,
    script: Path,
    dataset: Path | None,
) -> Path:
    """Assemble the kit directory from an already-validated embeddable zip."""
    kit_dir = dist_dir / _KIT_DIR_NAME
    if kit_dir.exists():
        shutil.rmtree(kit_dir)
    (kit_dir / "python").mkdir(parents=True)

    with zipfile.ZipFile(embed_zip) as archive:
        archive.extractall(kit_dir / "python")

    shutil.copy2(script, kit_dir / "bench_ollama.py")
    if dataset is not None:
        shutil.copy2(dataset, kit_dir / "swe_bench_vllm.jsonl")

    # Windows text files: explicit CRLF, written binary so nothing translates.
    (kit_dir / "run_bench.bat").write_bytes(_RUN_BAT.encode("ascii"))
    readme_crlf = _README_KIT.replace("\n", "\r\n")
    (kit_dir / "README_KIT.txt").write_bytes(readme_crlf.encode("utf-8"))
    return kit_dir


def zip_kit(kit_dir: Path, zip_path: Path) -> Path:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(kit_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(kit_dir.parent))
    return zip_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the offline Windows kit (embedded Python + bench_ollama.py "
        "+ SWE dataset) into dist/ollama_bench_kit.zip.",
    )
    parser.add_argument(
        "--dist",
        default=str(_HERE / "dist"),
        help="Output directory for the kit and downloads (default: ./dist).",
    )
    parser.add_argument(
        "--dataset",
        default=str(_DEFAULT_DATASET),
        help="Dataset JSONL to bundle; pass 'none' to skip "
        "(default: the repo's SWE-bench Lite export).",
    )
    parser.add_argument(
        "--embed-zip",
        default=None,
        help="Path to an already-downloaded embeddable package zip "
        "(skips the download; still validated).",
    )
    parser.add_argument(
        "--expected-sha256",
        default=None,
        help="Pin the embeddable zip's SHA256 (fails the build on mismatch).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    dist_dir = Path(args.dist)

    dataset: Path | None
    if args.dataset.lower() == "none":
        dataset = None
    else:
        dataset = Path(args.dataset)
        if not dataset.is_file():
            print(f"dataset not found: {dataset} (use --dataset PATH or 'none')",
                  file=sys.stderr)
            return 2

    try:
        if args.embed_zip is not None:
            embed_zip = Path(args.embed_zip)
            validate_embed_zip(embed_zip)
            digest = sha256_of(embed_zip)
            if args.expected_sha256 and digest != args.expected_sha256.lower():
                raise ValueError(
                    f"{embed_zip}: SHA256 mismatch — expected "
                    f"{args.expected_sha256}, got {digest}"
                )
            print(f"embeddable sha256: {digest}")
        else:
            embed_zip = download_embeddable(
                dist_dir, expected_sha256=args.expected_sha256
            )
    except (OSError, ValueError) as exc:
        print(f"embeddable package error: {exc}", file=sys.stderr)
        return 1

    kit_dir = assemble_kit(
        embed_zip=embed_zip,
        dist_dir=dist_dir,
        script=_HERE / "bench_ollama.py",
        dataset=dataset,
    )
    zip_path = zip_kit(kit_dir, dist_dir / f"{_KIT_DIR_NAME}.zip")
    size_mb = zip_path.stat().st_size / (1 << 20)
    print(f"kit ready: {kit_dir}")
    print(f"archive:   {zip_path} ({size_mb:.1f} MB)")
    print("copy the zip to a Windows client, unpack, run run_bench.bat "
          "(see README_KIT.txt inside)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
