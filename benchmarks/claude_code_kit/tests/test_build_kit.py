"""Tests for build_kit.py — offline, on a fake tools tree."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import build_kit

_CONFIG_ARGS = [
    "--base-url",
    "http://gw:4000",
    "--auth-token",
    "sk-test",
    "--model",
    "qwen-coder",
]


def _make_tools_tree(root: Path, *, with_uv: bool = True) -> Path:
    (root / "node-v20-win-x64").mkdir(parents=True)
    (root / "node-v20-win-x64" / "node.exe").write_bytes(b"MZ node")
    pkg = root / "npm-global" / "node_modules" / "@anthropic-ai" / "claude-code"
    pkg.mkdir(parents=True)
    (pkg / "cli.js").write_text("// claude cli\n", encoding="utf-8")
    (pkg / "package.json").write_text('{"name": "@anthropic-ai/claude-code"}\n')
    (root / "py312").mkdir()
    (root / "py312" / "python.exe").write_bytes(b"MZ python")
    userdir = root / "userdir" / ".claude"
    userdir.mkdir(parents=True)
    (userdir / "settings.json").write_text("{}\n", encoding="utf-8")
    if with_uv:
        (root / "uv").mkdir()
        (root / "uv" / "uv.exe").write_bytes(b"MZ uv")
    return root


def _build(tmp_path: Path, extra: list[str] | None = None, **tree_kwargs) -> tuple[int, Path]:
    tools = _make_tools_tree(tmp_path / "tools", **tree_kwargs)
    dist = tmp_path / "dist"
    code = build_kit.main(
        ["--tools-dir", str(tools), "--dist", str(dist), *_CONFIG_ARGS, *(extra or [])]
    )
    return code, dist / "claude_code_kit"


def test_build_assembles_full_layout(tmp_path):
    code, kit = _build(tmp_path)
    assert code == 0
    assert (kit / "nodejs" / "node.exe").is_file()
    assert (
        kit / "claude" / "node_modules" / "@anthropic-ai" / "claude-code" / "cli.js"
    ).is_file()
    assert (kit / "python" / "python.exe").is_file()
    assert (kit / "userdir" / ".claude" / "settings.json").is_file()
    assert (kit / "uv" / "uv.exe").is_file()
    assert (kit / "setup_client.py").is_file()
    assert (kit / "README_KIT.txt").is_file()
    assert (kit.parent / "claude_code_kit.zip").is_file()


def test_claude_bat_contains_config_and_crlf(tmp_path):
    _code, kit = _build(tmp_path)
    bat = (kit / "claude.bat").read_bytes()
    assert bat.startswith(b"@echo off\r\n")
    assert b"\n" not in bat.replace(b"\r\n", b"")  # CRLF only
    text = bat.decode("utf-8")
    assert 'set "ANTHROPIC_BASE_URL=http://gw:4000"' in text
    assert 'set "ANTHROPIC_AUTH_TOKEN=sk-test"' in text
    assert 'set "ANTHROPIC_MODEL=qwen-coder"' in text
    assert 'set "ANTHROPIC_SMALL_FAST_MODEL=qwen-coder"' in text
    assert 'set "DISABLE_AUTOUPDATER=1"' in text
    assert 'set "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1"' in text
    assert (
        '"%~dp0nodejs\\node.exe" '
        '"%~dp0claude\\node_modules\\@anthropic-ai\\claude-code\\cli.js" %*'
    ) in text


def test_auth_token_defaults_to_ollama(tmp_path):
    tools = _make_tools_tree(tmp_path / "tools")
    code = build_kit.main(
        [
            "--tools-dir",
            str(tools),
            "--dist",
            str(tmp_path / "dist"),
            "--base-url",
            "http://ollama:11434",
            "--model",
            "qwen-coder",
        ]
    )
    assert code == 0
    text = (tmp_path / "dist" / "claude_code_kit" / "claude.bat").read_text(encoding="utf-8")
    assert 'set "ANTHROPIC_AUTH_TOKEN=ollama"' in text


def test_small_fast_model_override(tmp_path):
    _code, kit = _build(tmp_path, extra=["--small-fast-model", "phi-mini"])
    text = (kit / "claude.bat").read_text(encoding="utf-8")
    assert 'set "ANTHROPIC_SMALL_FAST_MODEL=phi-mini"' in text


def test_kit_config_json(tmp_path):
    _code, kit = _build(tmp_path)
    config = json.loads((kit / "kit_config.json").read_text(encoding="utf-8"))
    assert config["model"] == "qwen-coder"
    assert config["smoke_prompt"] == "Zaplanuj pracę"
    assert config["env"]["ANTHROPIC_BASE_URL"] == "http://gw:4000"


def test_uv_optional(tmp_path):
    code, kit = _build(tmp_path, with_uv=False)
    assert code == 0
    assert not (kit / "uv").exists()


def test_zip_contains_kit_prefixed_paths(tmp_path):
    _code, kit = _build(tmp_path)
    with zipfile.ZipFile(kit.parent / "claude_code_kit.zip") as archive:
        names = archive.namelist()
    assert "claude_code_kit/claude.bat" in names
    assert "claude_code_kit/nodejs/node.exe" in names
    assert "claude_code_kit/userdir/.claude/settings.json" in names


def test_missing_claude_package_fails(tmp_path, capsys):
    tools = _make_tools_tree(tmp_path / "tools")
    pkg = tools / "npm-global" / "node_modules" / "@anthropic-ai" / "claude-code"
    (pkg / "cli.js").unlink()
    code = build_kit.main(
        ["--tools-dir", str(tools), "--dist", str(tmp_path / "dist"), *_CONFIG_ARGS]
    )
    assert code == 2
    assert "--claude-dir" in capsys.readouterr().err


def test_ambiguous_node_fails_with_listing(tmp_path, capsys):
    tools = _make_tools_tree(tmp_path / "tools")
    (tools / "node-old").mkdir()
    (tools / "node-old" / "node.exe").write_bytes(b"MZ old")
    code = build_kit.main(
        ["--tools-dir", str(tools), "--dist", str(tmp_path / "dist"), *_CONFIG_ARGS]
    )
    assert code == 2
    err = capsys.readouterr().err
    assert "ambiguous" in err and "--node-dir" in err


def test_node_dir_override_resolves_ambiguity(tmp_path):
    tools = _make_tools_tree(tmp_path / "tools")
    (tools / "node-old").mkdir()
    (tools / "node-old" / "node.exe").write_bytes(b"MZ old")
    code = build_kit.main(
        [
            "--tools-dir",
            str(tools),
            "--dist",
            str(tmp_path / "dist"),
            "--node-dir",
            str(tools / "node-v20-win-x64"),
            *_CONFIG_ARGS,
        ]
    )
    assert code == 0


def test_missing_tools_dir_fails(tmp_path, capsys):
    code = build_kit.main(
        ["--tools-dir", str(tmp_path / "nope"), "--dist", str(tmp_path / "d"), *_CONFIG_ARGS]
    )
    assert code == 2
    assert "--tools-dir" in capsys.readouterr().err
