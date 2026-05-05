# Agent State - nanoserve-mini

This file is the repo-tracked handoff state for Claude Code, Codex, and human work.

Keep it concise and current. Update it after meaningful repo changes, especially before
committing, pushing, or handing work to another agent.

---

## Canonical file roles

- `CLAUDE.md` - stable instructions for Claude Code.
- `AGENTS.md` - stable instructions for Codex.
- `docs/agent-state.md` - current project state, decisions, next step, and blockers.
- `ROADMAP.md` - project scope; do not change it without an explicit decision.

Note: the current roadmap content in this repo is stored as `docs/ROADMAP_v_1_0.md`.
Treat it as the current scope document unless a root `ROADMAP.md` is added later.

---

## Current phase

Bootstrap / Phase 1 preparation.

The current goal is to keep the repo organized, finish the GitHub-facing description,
and prepare for the first server environment snapshot before the first vLLM run.

---

## Current known status

- GitHub repo exists: `https://github.com/Czyszka/nanoserve-mini.git`
- Local Windows laptop bootstrap is done.
- Python workflow uses `uv`.
- `ruff` and `pytest` are configured and pass locally.
- `README.md`, `CLAUDE.md`, `AGENTS.md`, and `docs/agent-state.md` are committed and pushed to GitHub.
- `.gitattributes` exists to normalize line endings.
- Local research PDFs are kept outside Git in ignored `docs/papers/`.
- Server access is expected later this week.
- Server has Ubuntu 24 and 8x H200 NVL, but the repo has not yet recorded an environment snapshot from it.
- Latest paper-reading workflow documentation changes are tracked in the handoff log;
  `.claude/` remains untracked.

---

## Important project docs

Read these before making non-trivial changes:

- `docs/ROADMAP_v_1_0.md` - current scope, phases, and definition of done.
- `docs/infrastructure_v_1_0.md` - machine roles and workflow.
- `docs/server-first-session.md` - runbook for the first server session (env snapshot + vLLM setup decision).
- `docs/reading-list.md` - papers by phase.
- `docs/nvidia_self_paced_courses.md` - optional NVIDIA courses.
- `AGENTS.md` - Codex-specific repo instructions.
- `CLAUDE.md` - Claude Code-specific repo instructions.

Do not rewrite the roadmap/scope document unless explicitly asked.

---

## Current technical direction

Do not start vLLM setup until the server environment is captured.

Immediate milestone:

1. README and agent coordination docs are committed and pushed (done).
2. Laptop-safe scaffolding for the first server session is committed:
   `docs/server-first-session.md`, `scripts/__init__.py`, `scripts/_client.py`,
   `scripts/_metrics.py`, `scripts/request_once.py`,
   `scripts/measure_ttft_once.py`, `scripts/run_sequential_benchmark.py`
   plus tests with httpx.MockTransport (done).
3. run `uv run python -m scripts.check_server_env` on the server when available,
4. commit `results/raw/server_env_snapshot.json` from the server if it is small and useful,
5. decide vLLM setup path: Docker vs uv/native (follow `docs/server-first-session.md`),
6. once vLLM is up:
   `uv run python -m scripts.request_once` ->
   `uv run python -m scripts.measure_ttft_once` ->
   `uv run python -m scripts.run_sequential_benchmark`.

---

## Standard commands

Local / laptop:

```bash
uv sync --extra dev
uv run ruff check .
uv run pytest
```

Server, once available:

```bash
git clone https://github.com/Czyszka/nanoserve-mini.git
cd nanoserve-mini
uv sync --extra dev
uv run python -m scripts.check_server_env
```

---

## Current decisions

| Area | Decision |
|---|---|
| Central sync | GitHub repo |
| Laptop role | dev, docs, analysis |
| Server role | primary GPU execution |
| Optional cloud | backup GPU access only |
| Python workflow | uv on laptop and server |
| Heavy GPU deps | not in laptop base config |
| vLLM setup | decide after server snapshot |
| Agent memory | `docs/agent-state.md` is repo-tracked shared handoff |
| Claude Code entrypoint | root `CLAUDE.md` |
| Codex entrypoint | root `AGENTS.md` |
| State updates | Codex and Claude Code must update `docs/agent-state.md` after meaningful work and before commit/push handoff |
| Local papers | Store read scientific papers in ignored `docs/papers/`; commit bibliographic notes/summaries separately if useful |

---

## Open questions

- [ ] Is server Docker installed and usable?
- [ ] Does `nvidia-smi` show all 8x H200 NVL?
- [ ] Which Python version is available on the server?
- [ ] Does `uv sync --extra dev` work on the server?
- [ ] Should vLLM be launched via Docker or uv/native?
- [ ] Should raw result files be committed directly or summarized after first GPU run?
- [ ] Should the roadmap be copied/renamed to root `ROADMAP.md`, or should `docs/ROADMAP_v_1_0.md` remain canonical?

---

## Last validation

Most recent local validation (2026-05-03, laptop, after Efficient LLM Serving Survey note):

```text
uv run ruff check .     OK, all checks passed
uv run pytest           OK, 32 passed
git status              OK, working tree has docs changes plus pre-existing untracked .claude/
```

---

## Handoff log

### 2026-05-05 - company H200 plan capacity estimates

- Updated `docs/company-ai-support-h200-plan.md` with a new planning section:
  "Przykładowe wyliczenia pojemności i scenariusze użycia".
- Added capacity-planning estimates for 8xH200 NVL:
  raw HBM size, DeepSeek-V4-Pro and DeepSeek-V4-Flash deployment assumptions,
  approximate checkpoint/KV-cache implications, and concurrency-oriented
  scenarios for code questions, PR/module work, large repo analysis, repo-scale
  tasks, and team load tests.
- Added the rationale for measuring concurrency 1 / 4 / 8 / 16 and interpreting
  response time as `E2E latency ~= TTFT + output_tokens * TPOT`.
- Added technical source links to vLLM DeepSeek V4 recipes, the vLLM DeepSeek V4
  blog post, and NVIDIA H200.
- Renumbered later sections in `docs/company-ai-support-h200-plan.md`.
- Commands run:
  `git status -sb`, `Get-Content docs\company-ai-support-h200-plan.md`,
  `git diff -- docs\company-ai-support-h200-plan.md`,
  `Select-String -Path docs\company-ai-support-h200-plan.md -Pattern '^## '`,
  `Select-String -Path docs\company-ai-support-h200-plan.md -Pattern '^### 6'`.
- Validation: docs-only change; ruff/pytest not run.
- Next recommended action: review the new estimates for tone and acceptable SLO
  targets before turning them into firm commitments in the company note.

### 2026-05-05 - company H200 plan proxy/routing alignment

- Updated `docs/company-ai-support-h200-plan.md` to align with the roadmap's
  proxy/routing scope.
- Added LiteLLM Proxy as the shared OpenAI-compatible endpoint in the target
  architecture, with manual routing by `model`, per-user API keys, and usage logs.
- Updated target architecture, modernization rationale, planning scenarios,
  12-week phases, success criteria, effort scope, and team value to include
  multi-model proxy/routing.
- Added vLLM Semantic Router as a later measurement experiment comparing
  automatic classification against manual routing through LiteLLM Proxy.
- Commands run:
  `Select-String -Path docs\ROADMAP_v_1_0.md -Pattern 'proxy|router|routing|gateway|endpoint' -Context 2,3`,
  `Select-String -Path docs\company-ai-support-h200-plan.md -Pattern 'LiteLLM|Semantic Router|routing|proxy' -Context 1,2`,
  `Select-String -Path docs\company-ai-support-h200-plan.md -Pattern '^## '`,
  `git diff --stat`,
  `git diff -- docs\company-ai-support-h200-plan.md`.
- Validation: docs-only change; ruff/pytest not run.
- Next recommended action: review whether vLLM Semantic Router should remain a
  hard success criterion or be worded as an optional experiment after the manual
  LiteLLM routing baseline is stable.

### 2026-05-05 - company H200 plan shared-node Kimi experiment

- Updated `docs/company-ai-support-h200-plan.md` with a vLLM-only shared-node
  experiment for the target two-model setup.
- Added Kimi K2.6 as the premium model candidate running on the full 8xH200 node
  with `tensor_parallel_size=8`.
- Added the second model as a separate faster vLLM endpoint on the same 8xH200
  node, for example DeepSeek-V4-Flash / Qwen / Gemma.
- Clarified that this is not a hard GPU split such as 5+3 or 6+2, but a
  shared-node experiment where both vLLM instances share GPU memory, compute, and
  HBM bandwidth.
- Added the key measurement question: whether the faster model preserves
  acceptable p95/p99 latency while Kimi K2.6 performs long prefill or decode.
- Added a minimal measurement matrix: Kimi solo, faster model solo, both idle,
  Kimi long-context plus short requests to the faster model, and both models
  under load.
- Added Kimi K2.6 vLLM recipe source link and updated the candidate model naming
  from Kimi K2 to Kimi K2.6.
- Commands run:
  `git status -sb`,
  `Select-String -Path docs\company-ai-support-h200-plan.md -Pattern 'Kimi|DeepSeek-V4|LiteLLM|Routing|Scenariusze|Kryteria|Plan 12' -Context 1,2`,
  `Select-String -Path docs\company-ai-support-h200-plan.md -Pattern '^## |^### '`,
  `Select-String -Path docs\company-ai-support-h200-plan.md -Pattern 'Kimi K2' -Context 0,1`,
  `Select-String -Path docs\company-ai-support-h200-plan.md -Pattern 'shared-node|Kimi K2.6|TP=8|tensor_parallel_size' -Context 1,2`.
- Validation: docs-only change; ruff/pytest not run.
- Next recommended action: commit and push the updated company note and shared
  agent state.

### 2026-05-03 - Efficient LLM Serving Survey paper note

- Added full Phase 1 paper note:
  `docs/papers-notes/efficient-llm-serving-survey.md`.
- Used the full paper-note template because this is a foundational Phase 1 paper.
- The note focuses on the project-relevant parts of the survey:
  vLLM baseline interpretation, TTFT/E2E and future TPOT, prefill vs decode,
  KV cache and memory management, scheduling/batching, observability, and
  benchmark methodology.
- Updated `docs/reading-list.md` with a short "Notatki własne" entry for the
  survey.
- Did not modify roadmap or project scope. Did not add or commit PDFs.
- Commands run:
  `Get-Content -Raw docs/paper-reading-guide.md`,
  `Get-Content -Raw docs/templates/paper-note-template.md`,
  `Get-Content -Raw docs/reading-list.md`,
  `Get-Content -Raw docs/ROADMAP_v_1_0.md`,
  `Get-Content -Raw docs/agent-state.md`,
  `Get-ChildItem -Force docs`, `Get-ChildItem -Force docs\papers`,
  `git status -sb`, `rg --files` (failed, `rg` is not installed),
  bundled Python/pypdf PDF metadata and targeted text extraction,
  `Get-Content -Raw scripts\measure_ttft_once.py`,
  `Get-Content -Raw scripts\run_sequential_benchmark.py`,
  `Get-Content -Raw scripts\_metrics.py`,
  `git diff -- docs\reading-list.md`,
  `uv run ruff check .`, `uv run pytest`, `git status`.
- Validation: `uv run ruff check .` OK; `uv run pytest` OK (32 passed);
  `git status` OK and shows modified docs plus untracked `docs/papers-notes/`
  and pre-existing untracked `.claude/`.
- Next recommended action: when vLLM is available on the server, run
  `scripts/request_once.py` and `scripts/measure_ttft_once.py`, then use
  `scripts/run_sequential_benchmark.py` to compare short/medium/long prompts
  with fixed controls before adding vLLM `/metrics` scraping.

### 2026-05-03 - align paper reading guide with Keshav review

- Pulled latest `origin/main` with `git pull --ff-only` before editing. The remote
  had added `docs/templates/paper-note-lite.md` and a "Recommended first use" section
  in `docs/paper-reading-guide.md`.
- Updated `docs/paper-reading-guide.md` with targeted fixes only:
  - renamed the old "Przejście 0" heading to mark it as a project-specific
    pre-reading step,
  - broadened the `Correctness` question beyond LLM/GPU only,
  - added pass-2 note-taking during reading,
  - added explicit defer/background/pass-3 choices after an unsuccessful pass 2,
  - adjusted pass-3 timing to match Keshav more closely,
  - added missing citations and future-work ideas to pass 3,
  - added the survey-paper escape hatch, key-researcher lookup, and recent top
    conference proceedings to the mini literature survey workflow,
  - updated "Recommended first use" wording to refer to the pre-reading step rather
    than "Przejście 0".
- Did not change roadmap, scope, reading-list ordering, or template structure.
- Commands run:
  `git status -sb`, `git branch --show-current`,
  `git log --oneline --max-count=5 -- docs/paper-reading-guide.md
  docs/templates/paper-note-template.md docs/agent-state.md`,
  `git log --oneline HEAD..origin/main`, `git diff --stat HEAD..origin/main`,
  `git diff --name-only HEAD..origin/main`, `git pull --ff-only`,
  `Get-Content -Raw docs/paper-reading-guide.md`,
  `Get-Content -Raw docs/templates/paper-note-lite.md`,
  `Get-Content -Raw docs/templates/paper-note-template.md`,
  `Get-Content -Raw docs/agent-state.md`, `uv run ruff check .`,
  `uv run pytest`, `git diff --check`, `git diff --stat`.
- Validation: `uv run ruff check .` OK; `uv run pytest` OK (32 passed);
  `git diff --check` OK.

### 2026-05-03 - paper-note-lite + recommended first use

- Verified `.gitignore` already lists `docs/papers/`; no change required.
- Added `docs/templates/paper-note-lite.md` — short note format for the
  majority of papers (status/date/phase/why/verdict, 5-line summary, LLM
  inference lens, project experiment, takeaway). The full
  `docs/templates/paper-note-template.md` is reserved for foundational
  works (Efficient LLM Serving Survey, PagedAttention/vLLM, Efficiently
  Scaling Transformer Inference, Orca, Sarathi-Serve, FlashAttention).
- Added a "Recommended first use" section to `docs/paper-reading-guide.md`
  that names the lite template as the default and explicitly enumerates
  the foundational papers that justify the full template; the existing
  "Konwencja notatek" section was updated to reference both templates.
- No roadmap or scope change.
- Validation: `uv run ruff check .` OK, `uv run pytest` OK (32 passed).

### 2026-05-03 - paper reading workflow docs

- Read local `docs/papers/how to read papers.pdf` (S. Keshav, "How to Read a Paper")
  with a bundled PDF-capable Python runtime.
- Added `docs/paper-reading-guide.md`, a practical three-pass paper reading workflow
  adapted to `nanoserve-mini` and LLM inference performance work.
- Added `docs/templates/paper-note-template.md`, a reusable Markdown template for
  future paper notes with an explicit `LLM inference lens` section covering prefill,
  decode, scheduling, memory, kernel-level work, TTFT, TPOT, throughput, memory,
  cost, SLO/tail latency, utilization, vLLM interaction, trade-offs, bottleneck
  evidence, and minimal project experiments.
- No Python/config files changed.
- Commands run:
  `Get-Content -Raw docs/agent-state.md`, `Get-ChildItem -Recurse -File`,
  `Get-ChildItem -Recurse -File -Filter *.pdf`, bundled Python `pypdf` text
  extraction for `docs/papers/how to read papers.pdf`, `git diff --check`,
  `git status --short`, `git status -sb`, `git branch --show-current`,
  `git remote -v`, `git diff -- docs\agent-state.md docs\paper-reading-guide.md
  docs\templates\paper-note-template.md`.
- Validation: `git diff --check` OK. Ruff/pytest were not run because this was a
  docs-only change. An initial `uv run python -c ...` probe failed before extraction
  because uv could not initialize `C:\Users\Dom\AppData\Local\uv\cache`
  (`os error 183`), so the bundled Codex PDF runtime was used instead.
- Next recommended action: use `docs/templates/paper-note-template.md` for the next
  required paper, likely `Efficient LLM Serving Survey`, and fill in the
  `LLM inference lens` section before deciding on experiments.

### 2026-05-03 - bootstrap state

- Local repo was initialized and pushed to GitHub.
- Codex bootstrap created repo configuration.
- `.gitattributes` was added after LF/CRLF warnings.
- `scripts/check_server_env.py` exists for the first H200 server environment snapshot. (Run as `python -m scripts.check_server_env` after the review-fix entry made the `scripts/` package importable.)

### 2026-05-03 - README and shared agent state

- `README.md` was added with project overview, local workflow, repo layout, and suggested GitHub description.
- `CLAUDE.md` was added as the Claude Code entrypoint.
- `docs/agent-state.md` was verified and updated as the shared handoff file for Codex, Claude Code, and human work.
- `AGENTS.md` and `CLAUDE.md` now require updating `docs/agent-state.md` after meaningful work and before commit/push handoff.

### 2026-05-03 - coordination docs committed and pushed

- `README.md`, `CLAUDE.md`, `AGENTS.md`, and `docs/agent-state.md` are now committed to the repo and pushed to GitHub (`origin/main`).
- Working tree clean on branch `claude/vigorous-margulis-ac5191`.
- Local validation re-run on laptop: `uv sync --extra dev` OK, `uv run ruff check .` OK, `uv run pytest` OK (1 passed).
- Next recommended action: when the server is available, run `uv run python -m scripts.check_server_env` and capture `results/raw/server_env_snapshot.json`. (Module-execution form was introduced in the later "review fixes" entry; the older path-based form `python scripts/check_server_env.py` is no longer the canonical invocation.)

### 2026-05-03 - first-server-session scaffolding (D1-D4)

Four laptop-safe artifacts added across four commits, all pushed to `origin/main`:

- D1 `docs/server-first-session.md` - strict runbook for the first H200 slot
  (clone -> uv sync -> env snapshot -> commit -> Docker vs uv/native decision).
  No vLLM install, no model downloads, no observability stack in that session.
- D2 `scripts/_client.py` + `scripts/request_once.py` - shared HTTP client for
  the OpenAI-compatible vLLM endpoint and a single non-streaming smoke script.
- D3 `scripts/_metrics.py` + `scripts/measure_ttft_once.py` - Benchmark
  Contract record shape (`RunControls`, `summarize`, `percentile`) and a
  one-shot streaming TTFT/E2E measurement that writes
  `results/raw/first_ttft.json`. TTFT is anchored on the first chunk with
  non-empty `delta.content`, so role-only chunks don't pollute the metric.
- D4 `scripts/run_sequential_benchmark.py` - 1 warmup + N measured sequential
  streaming requests, JSONL of every run + `summary.json` with p50/p95/min/max/
  mean for TTFT and E2E. Errors are captured per-run and don't abort the loop.

Test coverage: 30 tests total, all using `httpx.MockTransport` so the laptop
gate (`uv run ruff check .` + `uv run pytest`) covers request shaping,
streaming SSE parsing, percentile math, JSONL/summary write paths, and the
CLI entry points. No real network or GPU dependency on laptop.

Validation (laptop, 2026-05-03):

```text
uv run ruff check .     OK, all checks passed
uv run pytest           OK, 30 passed
```

Next recommended action: when the server is available, work through
`docs/server-first-session.md` step-by-step.

### 2026-05-03 - review fixes (CLI import + JSON strictness)

Two laptop-safe corrections before the first H200 server slot:

- `scripts/__init__.py` added so `scripts._client` and `scripts._metrics`
  are importable as a real package. All entry-point scripts are now
  invoked via module execution (`uv run python -m scripts.<name>`) in
  `README.md`, `docs/server-first-session.md`, every script docstring,
  and the "Standard commands" block above. This avoids brittle path
  invocations that break the relative imports.
- `scripts/_metrics.py` no longer emits `float('nan')` from
  `percentile()` / `summarize()`; empty input now returns `None`
  (serializes as JSON `null`). `RunRow.e2e_seconds` for errored runs is
  also `None`. JSON writers in `measure_ttft_once.py` and
  `run_sequential_benchmark.py` now use `allow_nan=False` so any future
  regression that reintroduces NaN raises at write time instead of
  silently producing invalid JSON.

New tests cover strict-JSON round-trip for empty summaries and for
errored-run JSONL rows. Module-execution paths smoke-checked locally
with `python -m scripts.<name> --help`.

Validation (laptop, 2026-05-03, after fixes):

```text
uv sync --extra dev     OK
uv run ruff check .     OK, all checks passed
uv run pytest           OK, 32 passed
```

### 2026-05-03 - local papers directory

- Added ignored local directory `docs/papers/` for scientific paper PDFs already read or being reviewed.
- Moved local `docs/Efficient LLM Serving Survey.pdf` into `docs/papers/`.
- `.gitignore` now excludes `docs/papers/`; paper notes or summaries should be committed separately as Markdown when useful.
