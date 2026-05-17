# sync-state agent template

Canonical prompt and rules for the `sync-state` routine. Both Claude Code's
`/sync-state` and Codex's equivalent invoke this same logic. Edit this
file to evolve the routine; the slash commands point at it.

## Goal

Update `docs/operations/agent-state.md` to reflect commits made since the last summary
cursor. Append, do not compact. Compaction lives in
`docs/templates/tidy-docs-agent.md`.

## Hard rules

1. **Allowlist of editable files** (anything else = forbidden without explicit
   user request):
   - `docs/operations/agent-state.md` (always)
2. **Forbidden files** unless the user explicitly asks: `docs/project/roadmap.md`,
   `CLAUDE.md`, `AGENTS.md`, `docs/operations/infrastructure.md`, anything in
   `benchmarks/scripts/`, `serving/`, `results/`, `tests/`, `benchmarks/`.
3. **No code changes**: do not run `ruff` / `pytest`; this routine is doc-only.
4. **Branch**: stay on the current branch. Do not create or switch.
5. **Commit message**: must start with `docs: sync project state - <topic>`.
6. **Push**: only after the commit is successfully created.

## Procedure

### 1. Find the last sync point

Read `docs/operations/agent-state.md` and look for the `## Summary cursor` block:

```
## Summary cursor
- Last summarized commit: <SHA>
- Last summarized at: <YYYY-MM-DD>
```

If found, use that SHA as `LAST_SYNC`.

If missing or unparseable, fall back in this order:
1. `git log --grep='^docs: sync project state' -n 1 --format=%H`
2. `git log --diff-filter=A --format=%H -- docs/operations/agent-state.md | tail -1`

### 2. List changes since LAST_SYNC

```bash
git log --oneline --no-merges LAST_SYNC..HEAD
git diff --stat LAST_SYNC..HEAD
```

### 3. Early exit conditions

Stop without editing anything if any holds:
- `LAST_SYNC..HEAD` is empty.
- All commits in range are `docs: sync project state - ...` themselves.
- All commits classify as **skipped** (see step 4).

Report the reason and stop.

### 4. Classify commits

For each commit in range:

| Classification | Examples |
|---|---|
| **Logged** | serving/infra changes, new benchmark scripts, decisions, results, serving/compose changes, new docs sections, server runs |
| **Skipped** | typo fixes, formatting-only diffs, single-line whitespace, .gitignore tweaks, sync-state commits |

If no commits are `Logged`, early-exit per step 3.

### 5. Edit `docs/operations/agent-state.md`

Touch only these sections, in this order:

a. **Summary cursor** — update to current `HEAD` SHA and today's date.

b. **Current phase** — rewrite ONLY if the milestone materially advanced
   (e.g. "preparation" → "first vLLM run" → "benchmarking"). Otherwise leave.

c. **Current known status** — bullet-list reality check. Add new facts, mark
   old assumptions done, remove stale entries. **Hard cap: 10 bullets.**

d. **Current technical direction** — cross off completed steps, add up to 3
   new ones. **Hard cap: 10 steps total.** Remove fully-completed steps older
   than 2 weeks.

e. **Current decisions** — append rows ONLY for newly captured decisions.
   This table is append-only history; do not delete rows.

f. **Open questions** — close answered ones by **removing** them (not marking
   green); add new ones discovered. **Hard cap: 10 active.**

g. **Last validation** — update only if commits include actual validation
   results. Keep only the most recent block.

h. **Handoff log** — prepend ONE entry using the compressed template below.
   Do not delete or compact older entries. If the log has more than 5 entries
   after prepending, leave them in place and add a one-line note in the final
   report: `Handoff log has N entries (cap 5); consider running tidy-docs.`
   Compaction is the responsibility of `docs/templates/tidy-docs-agent.md`.

### 6. Compressed handoff entry template

```markdown
### YYYY-MM-DD - <one-line topic>

- Why: <single sentence intent>
- Did: <single sentence outcome>
- Range: `<short-SHA>..<short-SHA>` (N commits)
- Validation: <OK | failed: ... | skipped>
- Next: <single sentence next action>
```

**Hard rules for entries:**
- Maximum 8 lines per entry, including the heading and blank lines.
- No file lists. Reader can run `git diff --stat <range>`.
- No command quotes. Reader can run `git log <range>`.
- No session IDs.
- "Validation: OK" if all green; do not list every check.

### 7. Commit and push

```bash
git add docs/operations/agent-state.md
git -c commit.gpgsign=false commit -m "docs: sync project state - <topic from new entry>"
git push origin HEAD:main
```

Always push to `main`. Worktree branches (`claude/...`) track `main`
upstream, so a plain `git push` fails on name mismatch. The routine is
doc-only, so a direct push to `main` is acceptable.

### 8. Report

Single concise message to the user:
- LAST_SYNC SHA used, source (cursor / grep fallback / first commit).
- Commits processed: N logged, M skipped.
- Sections updated.
- Handoff log entry count (with `consider tidy-docs` note if > 5).
- New commit SHA, push result.

## Section length budget

Whole `docs/operations/agent-state.md` should fit in roughly 4-6 KB / ~5 K tokens. If a
sync would push it past that, prune harder:
- Tighten existing handoff entries (must obey 8-line cap).
- Remove "skipped" steps from technical direction.
- Reduce "Current known status" toward 6-8 bullets.
