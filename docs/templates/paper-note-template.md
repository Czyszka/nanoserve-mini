# Paper note: <title>

- **Status:** unread / pass 1 / pass 2 / pass 3 / done / skipped
- **Date read:** YYYY-MM-DD
- **Authors / venue / year:** <authors>, <venue>, <year>
- **URL / DOI / local PDF:** <link or docs/papers/...>
- **Project phase:** Phase 1 / Phase 2 / Phase 3 / Phase 4
- **Why now:** <one sentence>
- **Verdict:** must-read / useful background / maybe later / out of scope

## One-paragraph summary

<Problem, method, strongest result, and why it matters for nanoserve-mini.>

## Pass 1: qualification

### Five Cs

- **Category:** <measurement / system / scheduling / kernel / survey / analysis / prototype>
- **Context:** <related work, prerequisites, adjacent systems>
- **Correctness:** <do assumptions look valid?>
- **Contributions:** <main claimed contributions>
- **Clarity:** <clear enough to reproduce argument?>

### Decision after pass 1

- **Next action:** skip / background only / pass 2 / pass 3 later
- **Reason:** <why>

## Pass 2: argument and evidence

### Problem

<What problem do the authors solve?>

### Method

<Core idea, system design, algorithm, scheduling rule, cache policy, kernel trick, or measurement method.>

### Evidence

- **Baselines:** <what they compare against>
- **Workload:** <prompt lengths, output lengths, concurrency, arrival process, models>
- **Hardware/software:** <GPU, CPU, framework, precision, serving stack>
- **Metrics:** <TTFT, TPOT, throughput, latency percentiles, memory, cost, utilization>
- **Strongest result:** <specific number and condition>
- **Weakest result or missing evidence:** <specific gap>

### Assumptions

- <assumption 1>
- <assumption 2>
- <assumption 3>

## Pass 3: reconstruction

Use this section only for papers that matter enough to deeply understand.

### Reconstructed mechanism

<Explain the mechanism as if implementing or reproducing it. Add pseudocode if useful.>

### Hidden assumptions and failure modes

- <hidden assumption or failure mode>
- <hidden assumption or failure mode>

### What I would reproduce

<Minimal reproduction target, even if it only measures the same bottleneck rather than implementing the paper.>

## LLM inference lens

### Which phase does it optimize?

- [ ] prefill
- [ ] decode
- [ ] both
- [ ] scheduling around them
- [ ] memory around them
- [ ] kernel-level operation
- [ ] observability / measurement methodology

### Primary optimization target

- [ ] lower TTFT
- [ ] lower TPOT
- [ ] higher throughput
- [ ] lower memory
- [ ] lower cost
- [ ] better SLO/tail latency
- [ ] better utilization

### Bottleneck claimed by authors

Jaki bottleneck autorzy uznają za najważniejszy?

<Answer.>

### Bottleneck evidence

Czy pokazali liczby/profiling, czy tylko twierdzą?

<Answer with concrete figures, profiling outputs, ablations, or missing evidence.>

### Trade-off

Co poświęcają?

- [ ] jakość
- [ ] latency
- [ ] throughput
- [ ] pamięć
- [ ] prostotę systemu
- [ ] fairness
- [ ] koszt infrastruktury
- [ ] inne: <what>

<Explain the trade-off in one paragraph.>

### Interaction with vLLM

Czy to jest:

- [ ] używane przez vLLM
- [ ] alternatywa dla vLLM
- [ ] warstwa nad vLLM
- [ ] coś, czego nie implementujemy, ale mierzymy objawy
- [ ] niejasne / requires follow-up

<Explain the relationship.>

### Experiment I could run

Jaki minimalny eksperyment mogę zrobić w `nanoserve-mini`?

- **Hypothesis:** <what should change?>
- **Script or harness:** <scripts/measure_ttft_once.py, scripts/run_sequential_benchmark.py, future harness, manual vLLM metric scrape>
- **Workload:** <model, prompt shape, output length, request count, concurrency, cache pattern>
- **Metrics:** <TTFT, TPOT, E2E, throughput, p50/p95/p99, memory/cache utilization>
- **Controls:** <seed, model, server args, hardware, git commit, env snapshot>
- **Expected signal:** <what result would support or reject the paper's claim?>

## Nanoserve-mini mapping

- **vLLM baseline relevance:** <how it affects baseline interpretation>
- **Observability relevance:** <which metrics/logs would expose it>
- **Benchmark harness relevance:** <what scenario should the harness cover>
- **Workload/cache relevance:** <prefix reuse, KV pressure, prompt/output shape, concurrency>
- **Kernel/profiling relevance:** <whether later Triton/profiling work should care>
- **Out-of-scope boundary:** <what not to implement in this project>

## Follow-up references

- <paper or system name> - <why it matters>
- <paper or system name> - <why it matters>

## Final takeaway

<Two or three sentences: what stays in the project, what is rejected, and what to measure next.>
