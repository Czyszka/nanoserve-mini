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

## Example input domain

The parser should support query strings such as:

- `level:error service:api text:"timeout while reading"`
- `user:123 action:login`
- quoted values,
- escaped quotes,
- whitespace normalization.

---

## Required behavior

### Stage 1 — correctness with API preservation

- Preserve current public API signatures and return-shape behavior.
- Fix parsing correctness issues.
- Add or adjust tests to document expected behavior.

### Stage 2 — edge case handling

Handle at least:

- empty query,
- repeated spaces,
- quoted values,
- escaped quotes,
- malformed/unclosed quotes,
- duplicate keys (with explicit, consistent policy).

### Stage 3 — allocation-aware refactor

Refactor parser internals to reduce allocations:

- avoid excessive `Split`/temporary arrays,
- avoid unnecessary intermediate strings,
- use spans or careful indexing where appropriate,
- keep logic readable and maintainable.

### Stage 4 — performance stability

- Public tests must still pass.
- No major wall-clock regression in parser hot paths.
- Allocation behavior should improve or remain bounded relative to baseline.

---

## Public tests

Public tests should verify:

- basic parsing correctness,
- quoted value parsing,
- invalid input behavior,
- public API compatibility.

---

## Hidden tests

Hidden tests should verify:

- allocation-sensitive cases,
- large query strings,
- many-token queries,
- malformed quoting,
- duplicate-key policy consistency,
- culture-invariant behavior.

---

## Quality review checklist

LLM-as-judge should inspect:

- idiomatic C# (.NET 8/.NET 9 compatible),
- explicit API-preservation discipline,
- real allocation improvements (not cosmetic),
- no unsafe code unless strongly justified,
- readable parser logic,
- no broad try/catch blocks that swallow defects.
