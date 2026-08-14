"""Tests for build_kit.py — offline, on a dummy embeddable zip."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

import build_kit


def _make_dummy_embed_zip(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("python.exe", b"MZ fake")
        archive.writestr("python312.zip", b"PK fake stdlib")
        archive.writestr("python312.dll", b"MZ fake dll")
    return path


def test_validate_embed_zip_accepts_real_structure(tmp_path):
    embed = _make_dummy_embed_zip(tmp_path / "embed.zip")
    build_kit.validate_embed_zip(embed)  # no raise


def test_validate_embed_zip_rejects_non_zip(tmp_path):
    bad = tmp_path / "embed.zip"
    bad.write_bytes(b"<html>error page</html>")
    with pytest.raises(ValueError, match="not a valid zip"):
        build_kit.validate_embed_zip(bad)


def test_validate_embed_zip_rejects_zip_without_python(tmp_path):
    bad = tmp_path / "embed.zip"
    with zipfile.ZipFile(bad, "w") as archive:
        archive.writestr("readme.txt", b"nope")
    with pytest.raises(ValueError, match="python.exe missing"):
        build_kit.validate_embed_zip(bad)


def test_assemble_kit_layout_and_crlf(tmp_path):
    embed = _make_dummy_embed_zip(tmp_path / "embed.zip")
    dataset = tmp_path / "swe.jsonl"
    dataset.write_text(json.dumps({"prompt": "p"}) + "\n", encoding="utf-8")
    script = tmp_path / "bench_ollama.py"
    script.write_text("print('hi')\n", encoding="utf-8")

    kit_dir = build_kit.assemble_kit(
        embed_zip=embed, dist_dir=tmp_path / "dist", script=script, dataset=dataset
    )

    assert (kit_dir / "python" / "python.exe").is_file()
    assert (kit_dir / "python" / "python312.zip").is_file()
    assert (kit_dir / "bench_ollama.py").read_text(encoding="utf-8") == "print('hi')\n"
    assert (kit_dir / "swe_bench_vllm.jsonl").is_file()

    bat = (kit_dir / "run_bench.bat").read_bytes()
    assert bat.startswith(b"@echo off\r\n")
    assert b"%~dp0python\\python.exe" in bat and b"%*" in bat
    assert b"\n" not in bat.replace(b"\r\n", b"")  # CRLF only

    readme = (kit_dir / "README_KIT.txt").read_bytes()
    assert b"\r\n" in readme
    assert b"run_bench.bat" in readme


def test_assemble_kit_without_dataset(tmp_path):
    embed = _make_dummy_embed_zip(tmp_path / "embed.zip")
    script = tmp_path / "bench_ollama.py"
    script.write_text("pass\n", encoding="utf-8")
    kit_dir = build_kit.assemble_kit(
        embed_zip=embed, dist_dir=tmp_path / "dist", script=script, dataset=None
    )
    assert not (kit_dir / "swe_bench_vllm.jsonl").exists()


def test_zip_kit_contains_kit_prefixed_paths(tmp_path):
    embed = _make_dummy_embed_zip(tmp_path / "embed.zip")
    script = tmp_path / "bench_ollama.py"
    script.write_text("pass\n", encoding="utf-8")
    kit_dir = build_kit.assemble_kit(
        embed_zip=embed, dist_dir=tmp_path / "dist", script=script, dataset=None
    )
    zip_path = build_kit.zip_kit(kit_dir, tmp_path / "dist" / "kit.zip")
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
    assert "ollama_bench_kit/run_bench.bat" in names
    assert "ollama_bench_kit/python/python.exe" in names


def test_main_with_embed_zip_and_sha_pin(tmp_path, capsys):
    embed = _make_dummy_embed_zip(tmp_path / "embed.zip")
    digest = build_kit.sha256_of(embed)
    dataset = tmp_path / "swe.jsonl"
    dataset.write_text(json.dumps({"prompt": "p"}) + "\n", encoding="utf-8")

    code = build_kit.main(
        [
            "--dist",
            str(tmp_path / "dist"),
            "--embed-zip",
            str(embed),
            "--expected-sha256",
            digest,
            "--dataset",
            str(dataset),
        ]
    )
    assert code == 0
    assert (tmp_path / "dist" / "ollama_bench_kit.zip").is_file()
    assert digest in capsys.readouterr().out


def test_main_sha_mismatch_fails(tmp_path, capsys):
    embed = _make_dummy_embed_zip(tmp_path / "embed.zip")
    code = build_kit.main(
        [
            "--dist",
            str(tmp_path / "dist"),
            "--embed-zip",
            str(embed),
            "--expected-sha256",
            "0" * 64,
            "--dataset",
            "none",
        ]
    )
    assert code == 1
    assert "mismatch" in capsys.readouterr().err


def test_main_missing_dataset_fails(tmp_path):
    embed = _make_dummy_embed_zip(tmp_path / "embed.zip")
    code = build_kit.main(
        [
            "--dist",
            str(tmp_path / "dist"),
            "--embed-zip",
            str(embed),
            "--dataset",
            str(tmp_path / "missing.jsonl"),
        ]
    )
    assert code == 2
