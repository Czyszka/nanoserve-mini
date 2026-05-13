# Task 04 — C# allocation-aware refactor

Difficulty: C

Goal: refactor a small log-query parser to improve correctness and reduce allocations while preserving public API behavior.

This task is intentionally synthetic. It should be solved in a temporary task repository, not in `nanoserve-mini`.

---

## Agent prompt

You are given a small .NET parser library that parses simple log query expressions.

Your job is to:

1. Preserve the public API.
2. Fix correctness issues in parsing behavior.
3. Handle malformed/edge inputs robustly.
4. Refactor parser internals to reduce allocations without making code unreadable.

You may edit source files, tests, and benchmark-like checks.

---

## .NET baseline and dependency expectations

- .NET 8 is the baseline target. Code should remain compatible with .NET 9 unless the starter project explicitly requires otherwise.
- Do not change the target framework unless the starter project already allows it.
- Do not add heavy dependencies just to solve parsing.
- Benchmark project dependencies may exist in the starter, but the parser library should remain lightweight.

---

## Starter repository layout

```text
04_csharp_allocation_aware_refactor/
  README.md
  src/
    LogQueryParser/
      LogQueryParser.csproj
      QueryParser.cs
      QueryToken.cs
      QueryParseResult.cs
  tests/
    LogQueryParser.Tests/
      LogQueryParser.Tests.csproj
      QueryParserPublicTests.cs
      QueryParserHiddenTests.cs # not visible to agent during run
  benchmarks/
    LogQueryParser.Benchmarks/
      LogQueryParser.Benchmarks.csproj
      ParserBenchmarks.cs
```

---

## Public API contract and preservation rules

The starter public API is the source of truth. Treat the shape below as a behavioral contract example:

```csharp
public static class QueryParser
{
    public static QueryParseResult Parse(string query);
}

public sealed class QueryParseResult
{
    public bool Success { get; }
    public IReadOnlyList<QueryToken> Tokens { get; }
    public IReadOnlyList<QueryParseError> Errors { get; }
}

public sealed class QueryToken
{
    public string Key { get; }
    public string Value { get; }
}
```

Rules:

- Do not rename public classes, methods, or properties.
- Do not change public method signatures unless absolutely necessary.
- Internal/private parser implementation may be refactored freely.
- New internal helpers are allowed.
- New public overloads are allowed only if they do not break existing API.
- If any public API change is made, justify it in `SOLUTION_NOTES.md`.

---

## Query grammar and parsing semantics

Formal grammar:

```text
query        := whitespace* pair (whitespace+ pair)* whitespace*
pair         := key ":" value
key          := one or more non-whitespace characters excluding ":"
value        := quoted_value | bare_value
bare_value   := one or more non-whitespace characters
quoted_value := '"' characters_or_escapes '"'
```

Whitespace rules:

- Leading and trailing whitespace is ignored.
- Spaces, tabs, and newlines outside quotes are separators.
- Repeated whitespace outside quotes is treated as a single separator.
- Whitespace inside quoted values is preserved.

Example:

```text
level:error    text:"timeout while reading"
```

Produces:

- `level = error`
- `text = timeout while reading`

---

## Duplicate keys policy

Duplicate keys are allowed and preserved in input order.

Example:

```text
tag:api tag:slow
```

Produces tokens in order:

1. `tag = api`
2. `tag = slow`

Clarifications:

- Do not silently collapse duplicate keys.
- Do not use “last value wins” unless the starter API already explicitly requires a dictionary-like result.
- If the starter API is dictionary-like, document the conflict and preserve existing public API behavior.

---

## Malformed input behavior

Malformed user input should not crash the parser. It should return a failed `QueryParseResult` with errors.

Examples of malformed input:

- `level:`
- `:error`
- `level error`
- `text:"unterminated`
- `text:"bad \q escape"` (when unsupported escapes are invalid)

Policy:

- Empty query is valid and returns zero tokens.
- Malformed query returns `Success = false`.
- Malformed query includes at least one error object/message.
- The parser should not broadly catch and swallow unexpected defects.
- Exceptions are acceptable for programmer errors only (for example null input per policy below).

---

## Null input policy

`Parse(null)` should throw `ArgumentNullException`.

Clarifications:

- Null input is a programmer error.
- Empty string or whitespace-only string is valid user input and should return success with zero tokens.

---

## Quoted values and escape semantics

Required behavior examples:

- `text:"timeout while reading"` -> `text = timeout while reading`
- `text:"he said \"hello\""` -> `text = he said "hello"`
- `path:"C:\\Temp"` -> `path = C:\Temp`

Escapes to support inside quoted values:

- `\"` means literal `"`
- `\\` means literal `\`

Rules:

- Escapes are interpreted only inside quoted values.
- Unsupported escape sequences are malformed input.
- Unclosed quotes are malformed input.
- Quoted values may be empty (`text:""` is valid and yields empty value).

---

## Case sensitivity and culture behavior

- Keys and values are preserved exactly as written.
- The parser should not perform culture-sensitive casing or normalization.
- Any internal comparisons should use ordinal semantics.
- Behavior should be stable under different current cultures, including `tr-TR`.
- Do not lower-case or upper-case keys unless the starter API already requires it.

---

## Allocation-aware refactor expectations

- Avoid a `Split`-heavy implementation as the main strategy.
- Prefer a single-pass parser using indexing or `ReadOnlySpan<char>` where it improves allocation behavior without harming readability.
- Final string allocations for public `Key`/`Value` outputs are acceptable (public API exposes strings).
- Goal is not zero allocation; goal is removing unnecessary intermediate arrays/substrings.
- Correctness and API compatibility are more important than allocation reduction.

Guardrails:

- Do not introduce unsafe code.
- Do not make parser unreadable just to reduce small allocations.
- Avoid broad try/catch blocks that hide parser defects.
- Avoid regex-heavy implementation unless clearly justified and benchmarked.

---

## Performance and benchmark expectations

Use benchmark-like checks for representative workloads:

- many small queries,
- one large query,
- many-token query,
- quoted values with spaces and escaped characters,
- malformed inputs.

Track where possible:

- allocated bytes,
- elapsed time,
- optionally Gen0 collections.

Interpretation:

- Do not require a fixed percentage improvement (environment dependent).
- Allocation behavior should improve or at least remain bounded for representative valid queries.
- No major wall-clock regression in parser hot paths.
- Benchmark-like checks are diagnostic, not the only judge.
- Correctness must not be sacrificed for benchmark results.

---

## Build, test, and benchmark commands

Expected commands:

```bash
dotnet restore
dotnet test
dotnet run --project benchmarks/LogQueryParser.Benchmarks -c Release
```

If BenchmarkDotNet exists in the starter, targeted run may be used:

```bash
dotnet run --project benchmarks/LogQueryParser.Benchmarks -c Release -- --filter '*Parser*'
```

Notes:

- Exact benchmark command may vary by starter `README.md`.
- The agent may run tests and benchmarks.
- Public tests must pass after refactor.

---

## SOLUTION_NOTES.md requirement

Agent should create or update `SOLUTION_NOTES.md` describing briefly:

- what was broken,
- parsing policy,
- duplicate key policy,
- malformed input policy,
- API compatibility decisions,
- allocation/performance rationale,
- tests run,
- benchmarks run (if any).

This supports later LLM-as-judge review and commit comparison.

---

## Public tests

Public tests should verify:

- empty query returns success with zero tokens,
- whitespace-only query returns success with zero tokens,
- null input throws `ArgumentNullException`,
- basic `key:value`,
- multiple pairs,
- quoted value with spaces,
- escaped quote,
- escaped backslash,
- repeated spaces/tabs/newlines outside quotes,
- malformed unclosed quote returns failure,
- missing key or missing value returns failure,
- duplicate keys preserved in input order,
- public API compatibility.

---

## Hidden tests

Hidden tests should verify:

- very long query,
- many-token query,
- duplicate keys with order verification,
- tabs and newlines as separators,
- culture-sensitive behavior under non-invariant culture (such as `tr-TR`),
- malformed missing key,
- malformed missing value,
- malformed unsupported escape,
- escaped backslash,
- large quoted string,
- allocation-sensitive cases,
- no broad catch swallowing errors,
- public API reflection check,
- benchmark-like allocation regression check where feasible.

---

## Expected examples

| Input | Success | Tokens / Error |
|---|---|---|
| `level:error` | true | `(level, error)` |
| `level:error service:api` | true | `(level, error), (service, api)` |
| `text:"timeout while reading"` | true | `(text, timeout while reading)` |
| `tag:api tag:slow` | true | `(tag, api), (tag, slow)` |
| `text:"he said \"hello\""` | true | `(text, he said "hello")` |
| `""` | true | zero tokens |
| `"   "` | true | zero tokens |
| `text:"unterminated` | false | parse error |
| `level error` | false | parse error |

---

## Anti-hardcoding guidance

- Do not hard-code public test examples.
- Hidden tests will use different keys, values, whitespace, quotes, cultures, and query sizes.
- Do not weaken tests or change expected behavior to match a broken implementation.

---

## Quality review checklist

LLM-as-judge should inspect:

- public API compatibility,
- correctness against documented grammar,
- duplicate key behavior,
- malformed input behavior,
- clear null input policy,
- culture-invariant behavior,
- allocation-aware implementation with readable code,
- no unnecessary unsafe code,
- no regex-heavy or Split-heavy implementation unless justified,
- quality of `SOLUTION_NOTES.md`,
- whether tests and benchmark-like checks were run,
- whether correctness was prioritized over micro-optimization.

---

## Harness invocation

> Layout note: the actual scaffold lives at the task-dir level (`<task>/public/` and `<task>/hidden/`), not under `<task>/starter/tests/public/` and `<task>/starter/tests/hidden/`. The harness runs them outside the agent's work-dir.

This task is run by `scripts/run_coding_agent_task.py`. Example:

    uv run python -m scripts.run_coding_agent_task \
      --task-id 04_csharp_allocation_aware_refactor \
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
