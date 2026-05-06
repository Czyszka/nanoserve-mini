# Agent State - nanoserve-mini

This file is the repo-tracked handoff state for Claude Code, Codex, and human work.

Keep it concise and current. Update it after meaningful repo changes, especially before
committing, pushing, or handing work to another agent.

The `sync-state` routine (see `docs/templates/sync-state-agent.md`) maintains
this file. Older handoff entries live in `docs/handoff-archive/YYYY-MM.md`.

---

## Summary cursor

- Last summarized commit: `d39eff3`
- Last summarized at: 2026-05-06

The `sync-state` routine reads this block to find the diff window. Update only
via the routine.

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

**Phase 1 - first vLLM run in progress.**

Server is up, environment snapshot is committed, Docker vLLM image is installed,
Kimi-K2.6 weights are being downloaded to the `nanoserve-hf-cache` named volume.

---

## Current known status

- GitHub repo exists: `https://github.com/Czyszka/nanoserve-mini.git`
- Local Windows laptop bootstrap is done.
- Python workflow uses `uv`.
- `ruff` and `pytest` are configured and pass locally.
- `README.md`, `CLAUDE.md`, `AGENTS.md`, and `docs/agent-state.md` are committed and pushed to GitHub.
- `.gitattributes` exists to normalize line endings.
- Local research PDFs are kept outside Git in ignored `docs/papers/`.
- **Server is available**: ubuntusrv2 (Ubuntu 24.04, 8x H200 NVL 143 GB, CUDA 13.2, driver 595.58.03).
- **`results/raw/server_env_snapshot.json` committed** (2026-05-06).
- **vLLM Docker image installed** on the server (`vllm/vllm-openai:v0.20.0-cu130`).
- **Kimi-K2.6 model download in progress** to named volume `nanoserve-hf-cache`.
  Also downloading: `lightseekorg/kimi-k2.6-eagle3-mla` (Eagle3 speculative head).
- Compose file: `infra/compose/docker-compose.kimi-k2.6.yml` (single-node DEP, DP=8, EP).
- `.claude/` remains untracked locally.

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

Server is active. vLLM Docker is installed. Model weights downloading now.

Immediate next steps (in order):

1. ~~README and agent coordination docs committed and pushed~~ (done)
2. ~~Laptop-safe scaffolding committed~~ (done)
3. ~~Run `uv run python -m scripts.check_server_env` on the server~~ (done, 2026-05-06)
4. ~~Commit `results/raw/server_env_snapshot.json`~~ (done, 2026-05-06)
5. ~~Decide vLLM setup path: Docker~~ (done, 2026-05-06)
6. **Wait for Kimi-K2.6 + Eagle3 model download to complete.**
7. Start the stack: `docker compose -f infra/compose/docker-compose.kimi-k2.6.yml up -d`
8. Smoke test: `curl http://localhost:8000/v1/models`
9. First inference: `uv run python -m scripts.request_once`
10. First TTFT measurement: `uv run python -m scripts.measure_ttft_once`
11. Sequential benchmark: `uv run python -m scripts.run_sequential_benchmark`

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
| vLLM setup | **Docker** (`vllm/vllm-openai:v0.20.0-cu130`) |
| vLLM strategy | single-node DEP: DP=8, EP, TP=1 + Eagle3 speculative decoding |
| Model | `moonshotai/Kimi-K2.6` + `lightseekorg/kimi-k2.6-eagle3-mla` |
| HF weights storage | named Docker volume `nanoserve-hf-cache` |
| Compose file | `infra/compose/docker-compose.kimi-k2.6.yml` |
| Agent memory | `docs/agent-state.md` is repo-tracked shared handoff |
| Claude Code entrypoint | root `CLAUDE.md` |
| Codex entrypoint | root `AGENTS.md` |
| State updates | Codex and Claude Code must update `docs/agent-state.md` after meaningful work and before commit/push handoff |
| Local papers | Store read scientific papers in ignored `docs/papers/`; commit bibliographic notes/summaries separately if useful |

---

## Open questions

- [x] ~~Is server Docker installed and usable?~~ Yes (Docker 28.5, Compose v2.39).
- [x] ~~Does `nvidia-smi` show all 8x H200 NVL?~~ Yes, all 8x H200 NVL 143 GB visible.
- [x] ~~Which Python version is available on the server?~~ Python 3.12.11.
- [x] ~~Should vLLM be launched via Docker or uv/native?~~ Docker.
- [ ] Does `uv sync --extra dev` work on the server? (not yet tested, not blocking)
- [ ] Should raw result files be committed directly or summarized after first GPU run?
- [ ] Should the roadmap be copied/renamed to root `ROADMAP.md`, or should `docs/ROADMAP_v_1_0.md` remain canonical?

---

## Last validation

Most recent local validation (2026-05-06, laptop):

```text
uv run ruff check .     OK, all checks passed
uv run pytest           OK, 32 passed
```

---

## Handoff log

Most recent entries only. Older entries live in
`docs/handoff-archive/YYYY-MM.md`. Newest entry first. Maintained by the
`sync-state` routine — see `docs/templates/sync-state-agent.md`.

### 2026-05-06 - sync-state routine + Model B refactor

- Why: avoid drift between agent-state, CLAUDE.md, AGENTS.md and prevent agent-state bloat.
- Did: stripped phase blocks from CLAUDE.md/AGENTS.md (now point to agent-state); added Summary cursor; created `docs/templates/sync-state-agent.md`; archived 9 older handoff entries to `docs/handoff-archive/2026-05.md`; compressed remaining log to new format.
- Range: `d39eff3..HEAD` (1 commit pending)
- Validation: skipped (doc-only).
- Next: invoke `/sync-state` after future meaningful commits.

### 2026-05-06 - vLLM Kimi-K2.6 single-node DEP compose

- Why: enable first vLLM run on 8xH200 with Kimi-K2.6 per recipe single_node_dep.
- Did: added `infra/compose/docker-compose.kimi-k2.6.yml` (vLLM 0.20.0-cu130, DP=8 + EP, Eagle3 MTP, named volume `nanoserve-hf-cache`, port 8000), `.env.example`, README.
- Range: `7c5e755..3f20c5e` (5 commits)
- Validation: ruff/pytest OK (32 passed).
- Next: wait for K2.6 + Eagle3 download, `docker compose up -d`, `curl /v1/models`.

### 2026-05-05 - company H200 plan: capacity, routing, shared-node Kimi

- Why: align `docs/company-ai-support-h200-plan.md` with roadmap and 8xH200 reality.
- Did: added capacity estimates (DeepSeek-V4-Pro/Flash, concurrency 1/4/8/16); LiteLLM Proxy + vLLM Semantic Router scope; Kimi-K2.6 + faster-model shared-node experiment with measurement matrix.
- Range: 3 docs commits on 2026-05-05
- Validation: skipped (docs only).
- Next: review proposed SLOs; decide whether vLLM Semantic Router is hard or optional.

### 2026-05-03 - Efficient LLM Serving Survey paper note

- Why: foundational Phase 1 paper required before benchmark methodology.
- Did: added `docs/papers-notes/efficient-llm-serving-survey.md` (full template), updated `docs/reading-list.md`.
- Validation: ruff/pytest OK (32 passed).
- Next: when vLLM is up, run `request_once` → `measure_ttft_once` → sequential benchmark.

### 2026-05-03 - paper reading workflow + Keshav alignment

- Why: standardize 3-pass paper reading + lite/full note templates.
- Did: added `docs/paper-reading-guide.md`, `docs/templates/paper-note-{template,lite}.md`; refined guide per Keshav review.
- Validation: ruff/pytest OK (32 passed).
- Next: use lite template by default for new papers; full template only for foundational works.
