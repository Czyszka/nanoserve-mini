---
name: sync-state
description: Append-only sync of docs/operations/agent-state.md from commits since the last Summary cursor — classify commits, update sections, prepend one compressed handoff entry, commit and push. Canonical rules live in docs/templates/sync-state-agent.md.
---

Run the project state sync routine.

The full prompt — hard rules, file allowlist, edit procedure, compressed
handoff entry template, early-exit conditions, and the final report format —
is defined in **`docs/templates/sync-state-agent.md`**.

Execution contract:

1. Read that template first and execute it exactly. Do not improvise outside
   its hard rules — the same template drives Codex's equivalent routine, so
   cross-agent consistency matters more than local style.
2. Honor the early-exit conditions (empty range, sync-only commits,
   all-skipped): report the reason and stop without editing anything.
3. Doc-only routine: never run `ruff` / `pytest`, never touch files outside
   the template's allowlist.
4. Finish with the template's report format (LAST_SYNC SHA + how it was
   found, logged vs skipped commit counts, sections touched, handoff-log
   entry count with the tidy-docs hint when over cap, new commit SHA, push
   result).
