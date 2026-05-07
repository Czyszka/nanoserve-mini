# Task 03 — C++ buffer and hot path

Difficulty: B

Goal: fix correctness and safety issues in a token buffering component, then improve hot-path behavior without breaking the intended public API.

This task is intentionally synthetic. It should be solved in a temporary task repository, not in `nanoserve-mini`.

---

## Agent prompt

You are given a small C++ project with a partially broken `TokenBuffer` used to collect generated token IDs.

Your job is to:

1. Fix correctness bugs.
2. Eliminate memory-safety issues.
3. Improve hot-path append performance.
4. Preserve the public API shape where possible.

You may edit source files and add minimal tests/helpers if needed. You may run build/test/benchmark commands.

---

## Starter repository layout

```text
03_cpp_buffer_and_hotpath/
  README.md
  CMakeLists.txt
  src/
    token_buffer.h
    token_buffer.cpp
    main.cpp
  tests/
    public/
      test_token_buffer.cpp
    hidden/
      test_token_buffer_hidden.cpp # not visible to agent during run
  benchmarks/
    bench_append.cpp
```

---

## Required behavior

### Stage 1 — correctness fixes

Ensure `TokenBuffer` behavior is correct for common usage:

- appending token sequences,
- preserving append order,
- clear/reset behavior,
- handling empty input,
- handling repeated append calls.

### Stage 2 — memory safety and ownership

Fix allocator/ownership hazards such as:

- use-after-free,
- invalid references/iterators after resize,
- out-of-bounds writes,
- incorrect copy/move behavior (if custom semantics exist).

Implementation should be ASan-friendly and avoid undefined behavior.

### Stage 3 — hot path improvement

Improve append-path efficiency:

- avoid per-token heap allocation,
- reduce unnecessary copying,
- support practical `reserve`/capacity behavior,
- maintain reasonable complexity for large append workloads.

Performance work can be justified by benchmark results or by clear complexity/memory reasoning.

### Stage 4 — API stability and minimalism

- Preserve existing public API surface where possible.
- If a signature must change, justify it briefly in task notes.
- Keep changes focused; do not over-engineer.

---

## Public tests

Public tests should verify:

- basic append/read behavior,
- clear and reuse behavior,
- reserve/capacity behavior,
- a simple stress append scenario.

---

## Hidden tests

Hidden tests should verify:

- large append sequences,
- move/copy edge cases,
- append after clear/reset,
- performance-regression guardrails,
- ASan-friendly behavior when sanitizers are enabled.

---

## Quality review checklist

LLM-as-judge should inspect:

- idiomatic modern C++17/C++20 style,
- RAII usage,
- no raw owning pointers unless strongly justified,
- readable control flow and data ownership,
- no premature overengineering,
- credible hot-path improvement rationale.
