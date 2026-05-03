# Codex Task — Bootstrap repo configuration for `nanoserve-mini`

Use this file as the first task prompt for Codex.

## Goal

Prepare the local repository configuration for `nanoserve-mini` on a Windows 11 laptop.

This is **not** the GPU/vLLM setup yet. The laptop is used for:

- editing code,
- writing documentation,
- preparing benchmark scripts,
- analysing results,
- synchronizing with GitHub.

The GPU server / cloud will be used later for model execution and benchmark runs.

## Project context

`nanoserve-mini` is a 12-week LLM inference performance lab.

Core scope:

- vLLM serving baseline,
- Prometheus/Grafana observability,
- benchmark harness,
- workload and KV/prefix cache analysis,
- one Triton kernel later in the project,
- technical write-ups.

Important constraints:

- Do not expand project scope.
- Do not add TensorRT-LLM, SGLang, Kubernetes, multi-GPU, FP8, MoE, speculative decoding, or custom engine work now.
- Do not install or configure GPU dependencies on the Windows laptop unless explicitly asked.
- Do not add secrets to the repo.
- Do not commit model weights, Hugging Face cache, large logs, Nsight traces, or large benchmark artifacts.

## Existing project docs expected

The repo should contain or soon contain:

```text
ROADMAP.md
docs/infrastructure.md
docs/reading-list.md
docs/nvidia_self_paced_courses.md
```

Before making changes, inspect these files if they exist.

## Task

Create or update the repository bootstrap configuration.

The desired output is a clean initial repository that can be committed to GitHub and later cloned on the GPU server.

## Files to create or update

### 1. `AGENTS.md`

Create repository-level Codex instructions.

Use this content unless the existing repo already has a better version:

```md
# AGENTS.md

## Project context

This repository is `nanoserve-mini`: a 12-week LLM inference performance lab.

The project focuses on:

- vLLM serving baseline,
- observability,
- benchmark harness,
- workload and cache analysis,
- one Triton kernel later in the project,
- technical write-ups.

## Current phase

We are in bootstrap / Phase 1 preparation.

The current goal is:

1. keep the repo organized,
2. prepare local development configuration,
3. prepare scripts and docs,
4. later run vLLM and first TTFT measurement on the GPU server.

## Scope boundaries

Do not add the following unless explicitly requested:

- custom inference engine,
- TensorRT-LLM,
- SGLang integration,
- Kubernetes,
- multi-GPU / tensor parallelism,
- FP8 quantization,
- MoE,
- speculative decoding,
- production HA/autoscaling,
- large cloud infrastructure.

## Working rules

- Keep changes small and reviewable.
- Prefer simple Python scripts over complex frameworks.
- Use Python 3.12 and `uv`.
- Do not add heavy GPU dependencies on the Windows laptop.
- Do not commit secrets.
- Do not commit model weights, Hugging Face cache, large logs, or Nsight traces.
- Keep documentation in Markdown.
- Keep raw benchmark results small; commit summaries when raw data is large.
- When modifying benchmark logic, preserve reproducibility metadata.
- Do not rewrite `ROADMAP.md` unless explicitly asked.
- Do not change project scope unless explicitly asked.

## Validation

After Python/config changes, try to run:

```bash
uv sync --extra dev
uv run ruff check .
uv run pytest
```

If a command fails because the environment is not ready, report the exact error and do not hide it.

## Response format

When you finish, report:

1. files created/changed,
2. commands run,
3. checks passed/failed,
4. next recommended command for the user.
```

---

### 2. `.codex/config.toml`

Create project-scoped Codex config.

Use conservative defaults suitable for a first-time Codex workflow.

```toml
# Project-scoped Codex configuration for nanoserve-mini.
# Keep permissions conservative while the repo is being bootstrapped.

model = "gpt-5.5"
approval_policy = "on-request"
sandbox_mode = "workspace-write"
web_search = "cached"
default_permissions = ":workspace"

[windows]
sandbox = "elevated"

[features]
shell_snapshot = true
```

If this config is invalid for the installed Codex version, adjust it to the closest supported equivalent and explain the change.

---

### 3. `.gitignore`

Create or update:

```gitignore
# Secrets
.env
.env.*
!.env.example

# Python
.venv/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/

# Local caches
.cache/
hf_cache/
.cache/huggingface/

# Logs and traces
*.log
*.ncu-rep
*.nsys-rep
*.sqlite

# OS/editor
.DS_Store
Thumbs.db
.vscode/*
!.vscode/extensions.json
!.vscode/settings.json

# Large local-only artifacts
artifacts/
tmp/
```

---

### 4. `.env.example`

Create:

```env
HF_TOKEN=
VLLM_MODEL=Qwen/Qwen3-0.6B
VLLM_PORT=8000
HF_HOME=/workspace/.cache/huggingface
```

Do not create `.env` unless explicitly asked.

---

### 5. `.editorconfig`

Create:

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true

[*.md]
trim_trailing_whitespace = false

[*.ps1]
end_of_line = crlf
```

---

### 6. `pyproject.toml`

Create or update minimal Python project configuration:

```toml
[project]
name = "nanoserve-mini"
version = "0.1.0"
description = "LLM inference performance lab focused on vLLM serving, observability, benchmark harness, and Triton."
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27.0",
    "pydantic>=2.8.0",
    "rich>=13.7.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "ruff>=0.5.0",
    "mypy>=1.10.0",
]

[tool.uv]
package = false

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
ignore = []

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

Do not add PyTorch, vLLM, CUDA, Triton, or NVIDIA dependencies to the laptop project config now.

---

### 7. Repository directories

Ensure this structure exists:

```text
docs/
docs/weekly/
scripts/
benchmarks/
benchmarks/prompts/
benchmarks/configs/
infra/
infra/docker/
infra/compose/
results/
results/raw/
results/runs/
results/summaries/
tests/
```

Add `.gitkeep` files to empty directories.

---

### 8. `tests/test_bootstrap.py`

Create a minimal placeholder test:

```python
def test_project_bootstrap() -> None:
    assert True
```

This is only to make the initial `pytest` command pass before real tests exist.

---

### 9. `scripts/check_local.ps1`

Create a Windows local validation script:

```powershell
$ErrorActionPreference = "Stop"

Write-Host "==> Python"
python --version

Write-Host "==> uv"
uv --version

Write-Host "==> Sync dependencies"
uv sync --extra dev

Write-Host "==> Ruff"
uv run ruff check .

Write-Host "==> Pytest"
uv run pytest

Write-Host "==> Done"
```

Do not make this script install system tools. It should only validate the repo once Git, Python and uv are already installed.

---

### 10. Optional: `.vscode/extensions.json`

If `.vscode/` is acceptable, create:

```json
{
  "recommendations": [
    "ms-python.python",
    "charliermarsh.ruff",
    "ms-python.mypy-type-checker"
  ]
}
```

Do not create complex IDE settings.

---

## Commands to run

After creating files, run if available:

```powershell
uv sync --extra dev
uv run ruff check .
uv run pytest
git status
```

If `uv` is not installed, do not try to install it automatically. Report that the user should install it.

## Acceptance criteria

The task is complete when:

- `AGENTS.md` exists,
- `.codex/config.toml` exists,
- `.gitignore` exists,
- `.env.example` exists,
- `.editorconfig` exists,
- `pyproject.toml` exists,
- directory structure exists,
- `tests/test_bootstrap.py` exists,
- `scripts/check_local.ps1` exists,
- `uv sync --extra dev` succeeds or the reason for failure is clearly reported,
- `uv run ruff check .` succeeds or the reason for failure is clearly reported,
- `uv run pytest` succeeds or the reason for failure is clearly reported,
- `git status` is shown in the final response.

## Final response expected from Codex

When done, respond in this exact structure:

```md
## Summary

Created initial repo configuration for `nanoserve-mini`.

## Files changed

- ...

## Commands run

- ...

## Results

- ...

## Next step

Run:

```powershell
git add .
git commit -m "chore: bootstrap local repo configuration"
git push
```
```
