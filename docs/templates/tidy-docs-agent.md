# tidy-docs agent template

Canonical prompt and rules for the `tidy-docs` routine. Both Claude Code's
`/tidy-docs` and Codex's equivalent invoke this same logic. Edit this file
to evolve the routine.

`tidy-docs` is the **occasional** hygiene routine. It compacts and
deduplicates. The frequent counterpart is `sync-state` (see
`docs/templates/sync-state-agent.md`), which only appends.

## Goal

Reduce documentation surface area in the repo. Specifically:

1. Remove answered (`[x]`) entries from "Open questions" in `docs/operations/agent-state.md`.
2. Remove crossed-off (`~~done~~`) steps from "Current technical direction"
   when they are older than the Summary cursor.
3. Compact handoff log in-place when it exceeds 5 entries (Git is the archive).
4. Remove dynamic-state duplication (phase, status) from `CLAUDE.md` and
   `AGENTS.md`, replacing with a link to `docs/operations/agent-state.md`.
5. Report cap violations and drift that require human judgment. Never
   auto-prune to satisfy a counter.

## Hard rules

1. **Two modes**:
   - No argument → `audit` mode: read-only, produce report, exit.
   - `apply` argument → `apply` mode: perform mechanical edits, then exit.
   - `apply` **never** runs `git add`, `git commit`, or `git push`. The
     user reviews and commits manually.

2. **Allowlist** (apply mode only):
   - `docs/operations/agent-state.md`
   - `CLAUDE.md` (only operation d)
   - `AGENTS.md` (only operation d)

3. **Forbidden** unless the user explicitly asks: `docs/project/roadmap.md`,
   `docs/operations/infrastructure.md`, `docs/templates/**`, `docs/learning/paper-notes/**`,
   `benchmarks/scripts/**`, `serving/**`, `benchmarks/scripts_tests/**`, `results/**`, application code,
   anything under `.claude/`.

4. **Clean tree gate (apply only)**: before any edit, run
   `git status --short -- <allowlist files>`. If any allowlist file is
   modified, abort with: "apply requires clean tracked tree for target
   files; commit or stash first". No partial apply. Audit ignores tree state.

5. **No new files**: `tidy-docs` does not create `docs/handoff-archive/**`
   or any other file. Compaction is in-place.

6. **No counter-driven deletion**: cap violations are reported, never
   auto-fixed. Mechanical operations (a-d below) are deterministic and
   safe; trimming to fit a cap is human judgment.

7. **Branch**: stay on the current branch. Do not create or switch.

8. **Recompute counts at runtime**: never use hardcoded numbers from
   prior reports. Re-parse the files every run.

## Procedure

### 1. Detect mode

```
if argv contains "apply": mode = apply
else: mode = audit
```

### 2. Load state

Read `docs/operations/agent-state.md`, `CLAUDE.md`, `AGENTS.md`. Parse sections by
markdown headings. Resolve Summary cursor SHA from `docs/operations/agent-state.md`.

### 3. Detection passes (always run, both modes)

For each, record path, line range, and a short note. Use this checklist:

- **Section sizes** vs caps from `docs/templates/sync-state-agent.md`:
  - Current known status: cap 10 bullets.
  - Current technical direction: cap 10 steps.
  - Open questions: cap 10 active.
  - Handoff log: cap 5 entries.
- **`[x]` items** in Open questions block.
- **`~~strikethrough~~` items** in Current technical direction.
- **Handoff log entry count**.
- **Dynamic-state duplication** in `CLAUDE.md` / `AGENTS.md`: scan for
  phrases naming a phase, status, or commit SHA that should live only in
  `agent-state.md`. Match patterns: `bootstrap`, `Phase \d`, `vLLM run`,
  explicit SHA, "current phase".
- **Phase mismatch**: compare any phase phrase found in `CLAUDE.md` or
  `AGENTS.md` against the "Current phase" section in `agent-state.md`.
- **Sizes**: byte size of `docs/operations/agent-state.md`. Flag if > 6 KB.
- **Doc files > 10 KB** under `docs/` (excluding `docs/learning/paper-notes/`).

### 4. Print audit report

Always print, in this order, with counts and locations:

```
tidy-docs audit report

Cap violations:
- <section>: <current>/<cap> at <path>:<line>
- ...

Mechanical fix candidates:
- [x] items: N at <path>:<line>, ...
- ~~strikethrough~~ steps past cursor: N at <path>:<line>, ...
- handoff log: N entries (cap 5)
- CLAUDE.md/AGENTS.md dynamic-state phrases: N at ...

Drift / review needed:
- phase mismatch: <details>
- agent-state.md size: <bytes>
- doc files > 10 KB: <list>
```

### 5. Audit mode → stop here

No edits. No further commands.

### 6. Apply mode → clean-tree gate

Run `git status --short -- docs/operations/agent-state.md CLAUDE.md AGENTS.md`. If
output is non-empty, abort:

```
apply requires clean tracked tree for target files; commit or stash first.
```

Exit. Do not edit anything.

### 7. Apply mode → mechanical operations

Perform these in order. Each is idempotent.

**a. Remove `[x]` items from Open questions** in `docs/operations/agent-state.md`.
Strip the entire bullet line.

**b. Remove `~~strikethrough~~` steps** from "Current technical direction"
in `docs/operations/agent-state.md` when the step is wholly wrapped in `~~ ~~`. Keep
steps with partial strikethrough untouched (those usually carry context).

**c. Compact handoff log in-place** when entry count > 5. Keep the 5
newest entries verbatim. Replace older entries with one block:

```
> Pre-<DATE> handoff entries compacted. Source: `<sha>`.
> Full history: `git show <sha>:docs/operations/agent-state.md`.
```

`<DATE>` = the date of the oldest *kept* entry.
`<sha>` = current `HEAD` SHA at start of this apply (run `git rev-parse HEAD`).

If a compaction block already exists and entry count is ≤5, this is a no-op.

**d. Replace dynamic-state phrases** in `CLAUDE.md` / `AGENTS.md` that
duplicate `agent-state.md`. Only replace whole sentences or sub-bullets
that name a phase/status; **do not touch** scope-boundaries lists,
validation-command blocks, file-roles blocks, or agent-specific rules.
Replacement text: `For current phase, see docs/operations/agent-state.md.`

If the file already contains an equivalent link and no offending phrase
remains, this is a no-op.

### 8. Print diff stat and final report

```
git diff --stat -- docs/operations/agent-state.md CLAUDE.md AGENTS.md
```

Then print:

```
tidy-docs apply complete.

Mechanical edits applied: <list>.
Review needed (not auto-fixed): <list>.

No commit, no push. Review the diff and commit yourself, e.g.:
  git add -p docs/operations/agent-state.md CLAUDE.md AGENTS.md
  git commit -m "docs: tidy docs - <topic>"
  git push origin HEAD:main
```

## Section length budget

Same target as `sync-state-agent.md`: `docs/operations/agent-state.md` should fit in
roughly 4-6 KB / ~5 K tokens. `tidy-docs` reports when over budget but
does not prune to satisfy the budget.

## Frequency

This routine is on-demand. Recommended triggers:
- handoff log > 5 entries,
- `docs/operations/agent-state.md` > 6 KB,
- after a phase change,
- otherwise every ~2 weeks.

No timer enforces this. The user invokes the routine manually.
