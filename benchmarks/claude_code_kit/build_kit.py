#!/usr/bin/env python3
"""Build the offline Windows starter kit for Claude Code talking to Ollama over LAN.

Ollama v0.14.0+ natively exposes the Anthropic Messages API (/v1/messages),
so Claude Code points straight at the Ollama server — no proxy or gateway.

Run this next to the user's directory of offline tools (no downloads — the
tools are already there): Node.js for Windows, an npm tree with
``@anthropic-ai/claude-code`` installed, Python 3.12 for Windows, optionally
``uv.exe``, and a userdir with ``.claude``. The result is a single
``dist/claude_code_kit.zip`` for offline Windows clients:

    kit/
      nodejs/                node.exe + runtime
      claude/node_modules/@anthropic-ai/claude-code/cli.js
      python/                python.exe (runs setup_client.py on the client)
      userdir/.claude/       user configuration to install on the client
      uv/uv.exe              (only if found in the tools dir)
      claude.bat             session env (server URL, token, model) + runs cli.js
      setup.bat              runs setup_client.py with the bundled python
      setup_client.py        client-side setup: .claude, optional setx, smoke test
      kit_config.json        values baked at build time (also used by setup)
      README_KIT.txt         Polish instructions for the operator

Tool locations are auto-detected by searching --tools-dir for anchor files
(node.exe, cli.js under node_modules/@anthropic-ai/claude-code, python.exe,
uv.exe, a ``.claude`` directory); every location can be overridden with a
flag. Ambiguous or missing anchors fail the build with a clear message.

Stdlib-only; assembling a Windows kit on Linux is fine (files are only
copied and repacked, nothing is executed; .bat files are written with CRLF).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_KIT_DIR_NAME = "claude_code_kit"
_CLAUDE_PKG_REL = Path("node_modules") / "@anthropic-ai" / "claude-code"

_STATIC_ENV = {
    "DISABLE_AUTOUPDATER": "1",
    "DISABLE_TELEMETRY": "1",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
}

_README_KIT = """\
Claude Code — zestaw offline (Windows)
======================================

Zestaw jest samowystarczalny: Node.js + Claude Code + Python + konfiguracja.
Niczego nie instalujesz z internetu. Rozpakuj caly katalog w dowolne miejsce
(np. C:\\claude_kit) i pracuj z wiersza polecen (cmd).

Krok 1 — przygotowanie stanowiska (jednorazowo):

    setup.bat

  - kopiuje konfiguracje .claude do profilu uzytkownika
    (istniejaca .claude dostaje kopie zapasowa, nic nie jest nadpisywane
    bez sladu),
  - na koniec odpala probne zapytanie do modelu ("smoke test") — wynik
    OK/BLAD zobaczysz na ekranie.

  Opcje: setup.bat --persist   (zapisze zmienne srodowiskowe na stale, setx)
         setup.bat --skip-smoke  (bez probnego zapytania)

Krok 2 — praca:

    claude.bat

  claude.bat ustawia polaczenie z serwerem (adres, token, model) tylko na
  czas sesji i uruchamia Claude Code. Wszystkie argumenty sa przekazywane
  dalej, np.:

    claude.bat -p "Zaplanuj prace"

Uwagi:
- Maszyna musi widziec serwer-gateway w sieci lokalnej (adres wpisany
  w claude.bat). Internet nie jest potrzebny.
- Pierwsza odpowiedz moze trwac dlugo (ladowanie modelu na serwerze).
- Problemy: przepisz komunikat bledu ze smoke testu i przekaz osobie
  prowadzacej testy.
"""


class BuildError(Exception):
    """Raised for user-facing build problems (bad layout, ambiguity)."""


def _find_unique(
    candidates: list[Path],
    *,
    what: str,
    flag: str,
) -> Path:
    if not candidates:
        raise BuildError(f"{what}: not found in --tools-dir (override with {flag})")
    unique = sorted(set(candidates))
    if len(unique) > 1:
        listing = "\n  ".join(str(path) for path in unique)
        raise BuildError(
            f"{what}: ambiguous, {len(unique)} candidates found "
            f"(pick one with {flag}):\n  {listing}"
        )
    return unique[0]


def detect_node_dir(tools_dir: Path) -> Path:
    """Directory containing node.exe (the Node.js runtime for Windows)."""
    candidates = [path.parent for path in tools_dir.rglob("node.exe")]
    return _find_unique(candidates, what="Node.js (node.exe)", flag="--node-dir")


def detect_claude_root(tools_dir: Path) -> Path:
    """The node_modules root that contains @anthropic-ai/claude-code/cli.js."""
    candidates = []
    for path in tools_dir.rglob("cli.js"):
        pkg_dir = path.parent
        if pkg_dir.match(str(_CLAUDE_PKG_REL)):
            candidates.append(pkg_dir.parent.parent)  # the node_modules directory
    return _find_unique(
        candidates,
        what="Claude Code (node_modules/@anthropic-ai/claude-code/cli.js)",
        flag="--claude-dir",
    )


def detect_python_dir(tools_dir: Path) -> Path:
    """Directory containing python.exe (used on the client for setup_client.py)."""
    candidates = [path.parent for path in tools_dir.rglob("python.exe")]
    return _find_unique(candidates, what="Python (python.exe)", flag="--python-dir")


def detect_userdir(tools_dir: Path) -> Path:
    """The ``.claude`` user-configuration directory."""
    candidates = [path for path in tools_dir.rglob(".claude") if path.is_dir()]
    return _find_unique(candidates, what="userdir (.claude)", flag="--userdir")


def detect_uv_exe(tools_dir: Path) -> Path | None:
    """Optional uv.exe — bundled only when present and unambiguous."""
    candidates = sorted(set(tools_dir.rglob("uv.exe")))
    if not candidates:
        return None
    if len(candidates) > 1:
        listing = "\n  ".join(str(path) for path in candidates)
        raise BuildError(
            f"uv.exe: ambiguous, {len(candidates)} found "
            f"(pick one with --uv-exe or drop the extras):\n  {listing}"
        )
    return candidates[0]


def render_claude_bat(config: dict[str, str]) -> str:
    """The session launcher: env vars for this run only, then cli.js. CRLF."""
    cli_rel = "claude\\" + str(_CLAUDE_PKG_REL).replace("/", "\\") + "\\cli.js"
    lines = ["@echo off"]
    for key, value in _env_pairs(config).items():
        lines.append(f'set "{key}={value}"')
    lines.append('set "PATH=%~dp0nodejs;%PATH%"')
    lines.append(f'"%~dp0nodejs\\node.exe" "%~dp0{cli_rel}" %*')
    return "\r\n".join(lines) + "\r\n"


def render_setup_bat() -> str:
    return (
        "@echo off\r\n"
        '"%~dp0python\\python.exe" "%~dp0setup_client.py" %*\r\n'
    )


def _env_pairs(config: dict[str, str]) -> dict[str, str]:
    """All env vars the launcher sets (and --persist writes via setx)."""
    return {
        "ANTHROPIC_BASE_URL": config["base_url"],
        "ANTHROPIC_AUTH_TOKEN": config["auth_token"],
        "ANTHROPIC_MODEL": config["model"],
        "ANTHROPIC_SMALL_FAST_MODEL": config["small_fast_model"],
        **_STATIC_ENV,
    }


def assemble_kit(
    *,
    dist_dir: Path,
    node_dir: Path,
    claude_root: Path,
    python_dir: Path,
    userdir: Path,
    uv_exe: Path | None,
    config: dict[str, str],
) -> Path:
    """Copy tools and generate launcher/setup files into dist/claude_code_kit/."""
    kit_dir = dist_dir / _KIT_DIR_NAME
    if kit_dir.exists():
        shutil.rmtree(kit_dir)
    kit_dir.mkdir(parents=True)

    print(f"copying nodejs from {node_dir}")
    shutil.copytree(node_dir, kit_dir / "nodejs")
    print(f"copying claude package from {claude_root}")
    shutil.copytree(claude_root, kit_dir / "claude" / "node_modules")
    print(f"copying python from {python_dir}")
    shutil.copytree(python_dir, kit_dir / "python")
    print(f"copying userdir from {userdir}")
    shutil.copytree(userdir, kit_dir / "userdir" / ".claude")
    if uv_exe is not None:
        print(f"copying uv from {uv_exe}")
        (kit_dir / "uv").mkdir()
        shutil.copy2(uv_exe, kit_dir / "uv" / "uv.exe")

    shutil.copy2(_HERE / "setup_client.py", kit_dir / "setup_client.py")
    # Windows text files: explicit CRLF, written binary so nothing translates.
    (kit_dir / "claude.bat").write_bytes(render_claude_bat(config).encode("utf-8"))
    (kit_dir / "setup.bat").write_bytes(render_setup_bat().encode("ascii"))
    (kit_dir / "README_KIT.txt").write_bytes(
        _README_KIT.replace("\n", "\r\n").encode("utf-8")
    )
    (kit_dir / "kit_config.json").write_text(
        json.dumps(
            {**config, "env": _env_pairs(config)}, indent=2, allow_nan=False
        )
        + "\n",
        encoding="utf-8",
    )
    return kit_dir


def zip_kit(kit_dir: Path, zip_path: Path) -> Path:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(kit_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(kit_dir.parent))
    return zip_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assemble the offline Windows Claude Code kit from a directory "
        "of pre-downloaded tools (no network access needed).",
    )
    parser.add_argument(
        "--tools-dir",
        required=True,
        help="Directory with the offline tools (Node.js, npm tree with "
        "@anthropic-ai/claude-code, Python 3.12, optional uv.exe, .claude).",
    )
    parser.add_argument(
        "--base-url",
        required=True,
        help="Anthropic-compatible endpoint, e.g. http://<ollama-host>:11434 "
        "(Ollama v0.14.0+ serves /v1/messages natively).",
    )
    parser.add_argument(
        "--auth-token",
        default="ollama",
        help="ANTHROPIC_AUTH_TOKEN value; Claude Code requires it but Ollama "
        'ignores it (default: "ollama").',
    )
    parser.add_argument("--model", required=True, help="Model tag as known to the server.")
    parser.add_argument(
        "--small-fast-model",
        default=None,
        help="ANTHROPIC_SMALL_FAST_MODEL (default: same as --model).",
    )
    parser.add_argument(
        "--smoke-prompt",
        default="Zaplanuj prac\u0119",
        help='Prompt used by the client-side smoke test (default: "Zaplanuj pracę").',
    )
    parser.add_argument("--node-dir", default=None, help="Override Node.js autodetection.")
    parser.add_argument(
        "--claude-dir",
        default=None,
        help="Override: the node_modules root containing @anthropic-ai/claude-code.",
    )
    parser.add_argument("--python-dir", default=None, help="Override Python autodetection.")
    parser.add_argument("--userdir", default=None, help="Override .claude autodetection.")
    parser.add_argument("--uv-exe", default=None, help="Override uv.exe autodetection.")
    parser.add_argument(
        "--dist",
        default=str(_HERE / "dist"),
        help="Output directory (default: ./dist).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    tools_dir = Path(args.tools_dir)
    if not tools_dir.is_dir():
        print(f"--tools-dir not found: {tools_dir}", file=sys.stderr)
        return 2

    try:
        node_dir = Path(args.node_dir) if args.node_dir else detect_node_dir(tools_dir)
        claude_root = (
            Path(args.claude_dir) if args.claude_dir else detect_claude_root(tools_dir)
        )
        python_dir = (
            Path(args.python_dir) if args.python_dir else detect_python_dir(tools_dir)
        )
        userdir = Path(args.userdir) if args.userdir else detect_userdir(tools_dir)
        uv_exe = Path(args.uv_exe) if args.uv_exe else detect_uv_exe(tools_dir)

        if not (node_dir / "node.exe").is_file():
            raise BuildError(f"{node_dir}: node.exe missing (Windows build required)")
        if not (claude_root / "@anthropic-ai" / "claude-code" / "cli.js").is_file():
            raise BuildError(
                f"{claude_root}: @anthropic-ai/claude-code/cli.js missing "
                "(expected the node_modules directory itself)"
            )
        if not (python_dir / "python.exe").is_file():
            raise BuildError(f"{python_dir}: python.exe missing (Windows build required)")
        if not userdir.is_dir() or userdir.name != ".claude":
            raise BuildError(f"{userdir}: expected a directory named .claude")
    except BuildError as exc:
        print(f"build error: {exc}", file=sys.stderr)
        return 2

    config = {
        "base_url": args.base_url,
        "auth_token": args.auth_token,
        "model": args.model,
        "small_fast_model": args.small_fast_model or args.model,
        "smoke_prompt": args.smoke_prompt,
    }
    dist_dir = Path(args.dist)
    kit_dir = assemble_kit(
        dist_dir=dist_dir,
        node_dir=node_dir,
        claude_root=claude_root,
        python_dir=python_dir,
        userdir=userdir,
        uv_exe=uv_exe,
        config=config,
    )
    zip_path = zip_kit(kit_dir, dist_dir / f"{_KIT_DIR_NAME}.zip")
    size_mb = zip_path.stat().st_size / (1 << 20)
    print(f"kit ready: {kit_dir}")
    print(f"archive:   {zip_path} ({size_mb:.1f} MB)")
    print("copy the zip to a Windows client, unpack, run setup.bat "
          "(see README_KIT.txt inside)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
