# sync-state agent template

Canonical prompt and rules for the `sync-state` routine. Both Claude Code's
`/project:sync-state` and Codex's equivalent invoke this same logic. Edit this
file to evolve the routine; the slash commands point at it.

## Goal

Update `docs/agent-state.md` to reflect commits made since the last summary
cursor. Move expired handoff entries to the monthly archive. Do nothing else.

## Hard rules

1. **Allowlist of editable files** (anything else = forbidden without explicit
   user request):
   - `docs/agent-state.md` (always)
   - `docs/handoff-archive/YYYY-MM.md` (only when archiving expired entries)
2. **Forbidden files** unless the user explicitly asks: `docs/ROADMAP_v_1_0.md`,
   `CLAUDE.md`, `AGENTS.md`, `docs/infrastructure_v_1_0.md`, anything in
   `scripts/`, `infra/`, `results/`, `tests/`, `benchmarks/`.
3. **No code changes**: do not run `ruff` / `pytest`; this routine is doc-only.
4. **Branch**: stay on the current branch. Do not create or switch.
5. **Commit message**: must start with `docs: sync project state - <topic>`.
6. **Push**: only after the commit is successfully created.

## Procedure

### 1. Find the last sync point

Read `docs/agent-state.md` and look for the `## Summary cursor` block:

```
## Summary cursor
- Last summarized commit: <SHA>
- Last summarized at: <YYYY-MM-DD>
```

If found, use that SHA as `LAST_SYNC`.

If missing or unparseable, fall back in this order:
1. `git log --grep='^docs: sync project state' -n 1 --format=%H`
2. `git log --diff-filter=A --format=%H -- docs/agent-state.md | tail -1`

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
| **Logged** | infra changes, new scripts, decisions, results, infra/compose changes, new docs sections, server runs |
| **Skipped** | typo fixes, formatting-only diffs, single-line whitespace, .gitignore tweaks, sync-state commits |

If no commits are `Logged`, early-exit per step 3.

### 5. Edit `docs/agent-state.md`

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
   Then enforce the rolling window: if the handoff log has more than 5 entries,
   move the oldest entry to `docs/handoff-archive/YYYY-MM.md` (use the entry's
   own date for the YYYY-MM). Repeat until ≤5 entries remain.

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

### 7. Archive expired entries

When moving an entry out of `agent-state.md`:
1. Open or create `docs/handoff-archive/YYYY-MM.md` matching the entry's date.
2. If the file is new, start it with: `# Handoff archive YYYY-MM\n\n`.
3. Append the entry verbatim under that header (chronological order, oldest
   first within the file).

### 8. Commit and push

```bash
git add docs/agent-state.md docs/handoff-archive/
git -c commit.gpgsign=false commit -m "docs: sync project state - <topic from new entry>"
git push
```

### 9. Report

Single concise message to the user:
- LAST_SYNC SHA used, source (cursor / grep fallback / first commit).
- Commits processed: N logged, M skipped.
- Sections updated.
- Entries archived (if any).
- New commit SHA, push result.

## Section length budget

Whole `docs/agent-state.md` should fit in roughly 4-6 KB / ~5 K tokens. If a
sync would push it past that, prune harder:
- Tighten existing handoff entries (must obey 8-line cap).
- Remove "skipped" steps from technical direction.
- Reduce "Current known status" toward 6-8 bullets.
