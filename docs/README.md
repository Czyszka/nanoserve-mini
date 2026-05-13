# Documentation

This directory is the documentation map for `nanoserve-mini`.

Use this file as the first stop when looking for project direction, operating
state, learning notes, or reusable templates. Current work status lives in
`operations/agent-state.md`; long-term scope lives in `project/roadmap.md`.

## Project

Stable project direction, scope boundaries, and decision-level planning.

- [Roadmap](project/roadmap.md) - project scope, definition of done, phases, decision points, and out-of-scope boundaries.
- [Company AI support H200 plan](project/company-ai-support-h200-plan.md) - company-facing AI support plan around H200 infrastructure.

## Operations

Current execution context, infrastructure notes, benchmark methodology, and runbooks.

- [Agent state](operations/agent-state.md) - current working context, repo state, next actions, and AI-agent coordination notes.
- [Benchmark methodology](operations/benchmark-methodology.md) - benchmark rules, required measurements, workload conventions, and reproducibility expectations.
- [Infrastructure](operations/infrastructure.md) - laptop/server/cloud workflow, GitHub process, secrets policy, and results policy.
- [Runbooks](operations/runbooks/README.md) - practical operational instructions for server and vLLM work.

## Learning

Reading workflow, paper notes, and learning resources that support the lab.

- [Reading list](learning/reading-list.md) - papers mapped to project phases.
- [NVIDIA self-paced courses](learning/nvidia-self-paced-courses.md) - relevant NVIDIA courses for AI infrastructure and LLM inference.
- [Paper reading guide](learning/paper-reading-guide.md) - practical method for reading technical papers.
- [Paper notes](learning/paper-notes/) - notes extracted from selected papers.
- `learning/papers/` - ignored local PDF storage; source PDFs are not tracked in Git.

## Plans

Time-bound work plans and session notes. These are operational snapshots, not the roadmap.

- [Server work plan 2026-05-11](plans/2026-05-11-server-work-plan.md) - next server-session plan and post-session notes.

## Templates

Reusable Markdown templates and agent routines.

- [Paper note lite](templates/paper-note-lite.md)
- [Paper note template](templates/paper-note-template.md)
- [Sync state agent](templates/sync-state-agent.md)
- [Tidy docs agent](templates/tidy-docs-agent.md)

## Weekly Notes

Weekly progress notes. The directory may be empty early in the project.

- [Weekly notes](weekly/) - weekly progress notes.
