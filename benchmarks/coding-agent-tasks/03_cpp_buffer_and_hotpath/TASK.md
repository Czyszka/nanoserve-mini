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

## C++ standard baseline

C++17 is the required baseline. C++20 features may be used only if the starter project is explicitly configured for C++20.

- Do not require `std::span` unless the starter is configured for C++20.
- If the starter is C++17, batch append should use a C++17-compatible interface already present in the starter (for example: `std::vector<TokenId>`, pointer/size pair, iterator pair).
- Do not silently change the project standard just to use a newer feature.

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

## Public API contract and token type

Preserve the starter public API unless there is a strong reason to change it.

Example contract (shape-level reference, not required verbatim implementation):

```cpp
using TokenId = int32_t;

class TokenBuffer {
public:
    TokenBuffer();
    explicit TokenBuffer(std::size_t initial_capacity);

    void append(TokenId token);
    void append_many(const std::vector<TokenId>& tokens);
    void clear();
    void reserve(std::size_t capacity);

    std::size_t size() const noexcept;
    std::size_t capacity() const noexcept;
    bool empty() const noexcept;

    TokenId operator[](std::size_t index) const;
    std::vector<TokenId> to_vector() const;
};
```

Rules:

- If the starter defines `TokenId`, preserve that alias.
- Token IDs are signed 32-bit integers unless the starter defines a `TokenId` alias.
- Do not invent a validation policy for negative token IDs unless starter tests or README explicitly require it.
- Treat token values as data; this task is about buffer correctness/safety/performance, not token validation.
- If a public signature must change, justify it briefly in `SOLUTION_NOTES.md`.
- Hidden tests may rely on the documented public API.
- Do not over-constrain private implementation details.

---

## Required behavior

### Stage 1 — correctness fixes

Ensure `TokenBuffer` behavior is correct for common usage:

- appending token sequences,
- preserving append order,
- clear/reset behavior,
- handling empty input,
- handling repeated append calls.

Additional semantic requirements:

- `clear()` must set size to zero but should not shrink capacity.
- `reserve(n)` must ensure `capacity() >= n` and must not change `size()`.
- `reserve(n)` with `n <= current_capacity` must not shrink or corrupt existing data.
- append after `clear()` should reuse allocated storage where practical.
- empty batch append is a no-op.
- repeated append calls must behave the same as appending the concatenated sequence once.
- append/read methods (including `to_vector()` or equivalent) must preserve logical token order.

### Stage 2 — memory safety and ownership

Fix allocator/ownership hazards such as:

- use-after-free,
- invalid references/iterators after resize,
- out-of-bounds writes,
- incorrect copy/move behavior (if custom semantics exist).

Ownership/view/access rules:

- If the starter has checked accessors such as `at(index)`, out-of-range access should throw `std::out_of_range`.
- If the starter only has `operator[]`, hidden tests will not require adding `at()`, but valid indexed access must not introduce undefined behavior.
- Do not change documented accessor semantics without justification.
- Do not return references or pointers to temporary storage.
- If the starter exposes raw pointers/references/iterators/spans/views, preserve their lifetime semantics.
- Do not keep stale pointers after reallocation.
- Do not perform shallow copies of owning buffers.
- Moved-from objects must remain destructible and safe to assign to or clear.

Likely starter bug categories include one or more of:

- size/capacity confusion,
- off-by-one write during growth,
- shallow copy of an owning buffer,
- stale pointer after reallocation,
- `clear()` freeing storage unexpectedly,
- `append_many()` corrupting data during growth,
- `reserve()` shrinking or corrupting existing data.

If the public API allows appending from data that may overlap internal storage, handle it safely.

- Overlapping append should behave as if input was copied before mutation, or the API must explicitly guard and reject unsupported overlap.
- Example scenario: `buffer.append_many(buffer.to_vector());`

### Stage 3 — hot path improvement

Improve append-path efficiency:

- avoid per-token heap allocation,
- reduce unnecessary copying,
- support practical `reserve`/capacity behavior,
- maintain reasonable complexity for large append workloads.

Performance expectations:

- appending `N` tokens should be amortized `O(N)`.
- `append_many` must not allocate once per appended token.
- repeated small appends should use vector-like growth behavior, not repeated full-buffer copies.
- `clear()` should preserve reusable capacity.
- `reserve()` should allow callers to reduce repeated growth.

Hidden validation will use varying sizes and operation sequences. Do not optimize only for one benchmark case while breaking correctness.

### Stage 4 — API stability and minimalism

- Preserve existing public API surface where possible.
- If a signature must change, justify it briefly in `SOLUTION_NOTES.md`.
- Keep changes focused; do not over-engineer.
- A simple `std::vector<TokenId>`-backed solution is acceptable if it satisfies correctness, API, and performance requirements.
- Do not introduce custom allocators or manual memory management unless clearly justified.

---

## Sanitizer contract

Validation may run with AddressSanitizer and UndefinedBehaviorSanitizer if the toolchain supports them.

Expected sanitizer cleanliness:

- no use-after-free,
- no out-of-bounds read/write,
- no double free,
- no invalid iterator/reference use,
- no undefined behavior reported by UBSan.

Example commands (if supported by starter/CMake setup):

```bash
cmake -S . -B build-asan -DCMAKE_BUILD_TYPE=Debug -DENABLE_SANITIZERS=ON
cmake --build build-asan
ctest --test-dir build-asan --output-on-failure
```

If sanitizers are unavailable, correctness tests should still run.

---

## Build, test, and benchmark commands

Baseline commands:

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build
ctest --test-dir build --output-on-failure
```

Optional benchmark command:

```bash
cmake --build build --target bench_append
./build/benchmarks/bench_append
```

Notes:

- Exact executable paths may vary by platform/CMake generator.
- If starter README commands differ, follow the starter README.
- The agent may run tests and benchmarks.

---

## Public tests

Public tests should verify:

- append single token,
- append batch/vector,
- preserve order after growth,
- empty append is no-op,
- repeated append calls,
- `clear()` resets size but does not shrink capacity,
- `reserve()` increases capacity without changing size,
- `reserve(smaller)` does not shrink or corrupt data,
- append after clear works,
- `to_vector()` (or equivalent read path) returns expected tokens.

---

## Hidden tests

Hidden tests should verify:

- large append sequence (for example: 100k-1M tokens),
- capacity boundary cases (`append` at exactly capacity, then capacity + 1),
- random operation sequences compared against `std::vector<TokenId>` as oracle,
- deep-copy behavior for copy constructor/assignment (if copyable),
- move constructor/assignment leaves moved-from object valid,
- append after clear/reset,
- `reserve(smaller_than_current)` behavior,
- self-append/overlapping append behavior when API allows it,
- ASan/UBSan validation when available,
- performance-regression guardrails for `append_many` and repeated appends,
- no per-token heap allocation behavior in batch append if detectable.

---

## Benchmark expectations

`bench_append.cpp` is a lightweight diagnostic, not the only judge.

It should exercise:

- one large `append_many` workload,
- repeated small appends,
- append after reserve,
- append after clear.

Do not hard-code benchmark sizes or special-case known patterns.

Performance claims should be justified by complexity and allocation behavior, not a single timing run.

---

## Solution notes requirement

The coding agent should create or update `SOLUTION_NOTES.md` and briefly describe:

- what was broken,
- what changed,
- API compatibility decisions,
- safety fixes,
- expected complexity/allocation behavior,
- whether public tests, sanitizer tests, or benchmarks were run.

---

## Quality review checklist

LLM-as-judge should inspect:

- public API compatibility,
- correctness against vector-like behavior,
- memory safety and ownership discipline,
- appropriate RAII usage,
- copy/move correctness,
- clear/reserve/capacity semantics,
- amortized `O(N)` append behavior,
- no per-token allocation in batch append,
- simple implementation preferred over unnecessary custom allocator,
- quality of `SOLUTION_NOTES.md`,
- whether relevant tests/sanitizers/benchmarks were run.

---

## Anti-hardcoding guidance

- Do not hard-code public or hidden test cases.
- Do not special-case benchmark sizes.
- Do not weaken tests or change expected behavior to match a broken implementation.
- Hidden tests will use different sizes and operation sequences.

---

## Harness invocation

> Layout note: the actual scaffold lives at the task-dir level (`<task>/public/` and `<task>/hidden/`), not under `<task>/starter/tests/public/` and `<task>/starter/tests/hidden/`. The harness runs them outside the agent's work-dir.

This task is run by `scripts/run_coding_agent_task.py`. Example:

    uv run python -m scripts.run_coding_agent_task \
      --task-id 03_cpp_buffer_and_hotpath \
      --agent claude_code \
      --agent-command "claude -p {prompt_file}" \
      --model <model-id> \
      --base-url http://127.0.0.1:8001 \
      --run-id 2026-05-13_smoke

Layout:

- `starter/` — code the agent edits in the temp work-dir.
- `public/run.{sh|ps1}` — tests visible to the agent.
- `hidden/run.{sh|ps1}` — tests run by the harness only; not copied into the agent's work-dir.

Each invocation appends one row to `results/runs/<run_id>/coding_agent_eval/results.jsonl`
(schema `nanoserve-mini.coding-agent-eval-row.v1`).
