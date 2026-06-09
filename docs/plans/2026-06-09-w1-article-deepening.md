# W1 article deepening — plan (approved 2026-06-09)

> **For agentic workers:** laptop tasks (Etap 1, Etap 3) can be executed by an
> agent task-by-task; Etap 2 is a human-operated server slot
> (`docs/plans/2026-06-10-server-session.md`). Steps use checkbox syntax.

**Goal:** raise the scientific-engineering and recruiting depth of
`docs/writeups/w1-article.md` without changing its narrative spine.

**Diagnosis (approved):** the article is honest and well-evidenced but purely
post-hoc — every investigation observes a number, then explains it from logs.
Missing: the predictive move (compute what the number *should* be, compare),
figures, primary literature, practiced statistics, and a skimmable summary
layer.

**Decisions taken by the user (2026-06-09):**

- Improvements A–F approved.
- New evidence: **only P0 (GPU counters / DCGM) and P2 (R1 hop attribution)**.
  **P1 (Eagle3 n=20 clean A/B) and P3 (concurrency sweep) rejected** — out of
  this effort. `num_speculative_tokens` tuning stays out per roadmap
  ("beyond the documented Eagle3 baseline").
- Structure: deepen in place; keep the "five numbers that lied" narrative.
- Outline below approved.

---

## Approved outline (~4000–4500 words)

```
0. TL;DR / Results at a glance                         [NEW]
   - system one-liner, 5-row table (number → truth → mechanism → evidence level),
     headline baseline numbers
1. Thesis: a first number is a claim about its preconditions   [kept]
   + F1 serving-layer map with the five investigations pinned
2. The machine and the method                          [NEW, ~400 words]
   - PCIe-only topology and its implications; the 140.40 GiB partition
   - protocol: ABBA, temp 0, TTFT channels, direct-vs-proxy, n and percentile policy
3. Inv 1 — the engine that crashed after the weights fit      [+ F2, + MLA KV check]
4. Inv 2 — the benchmark that returned n/a and was right      [+ F4]
5. Inv 3 — the proxy that returned nothing                    [+ R1 hop attribution (P2)]
6. Inv 4 — the 3.8× that was partly a lie                     [+ F3 embed,
                                                               + acceptance-model box]
7. Inv 5 — 100% utilization on an idle GPU                    [+ roofline/all-reduce box,
                                                               + Little's law,
                                                               + DCGM counters (P0) → L2]
8. Synthesis: one model of the node                    [NEW]
   - capacity model + latency model + throughput model; predictions for W2
9. Scope, limitations, promotions ledger               [kept, updated]
10. References                                         [upgraded to primary]
```

---

## Etap 1 — laptop-only analysis layer (no GPU needed; can start before the slot)

All edits target `docs/writeups/w1-article.md` only. Thread files in
`docs/writeups/w1/` stay the evidence record — the article links, never forks,
their numbers. Validation per change: `git diff --check` (docs-only).

### Task 1.1 — quantitative boxes ("predict → measure → compare")

- [ ] **Roofline / all-reduce box (section 7).** Inputs: H200 HBM3e ≈ 4.8 TB/s/GPU
  (NVIDIA datasheet); Kimi active-parameter bytes per decoded token (4-bit routed
  experts + bf16 dense backbone, derived from the T1 decomposition table);
  measured OFF TPOT 16.55 ms/tok (T6). Compute the bandwidth-only TPOT bound,
  show measured is ~30× above it, then bound the per-layer PCIe all-reduce
  latency term (layer count × all-reduces/layer × PCIe round-trip estimate) and
  show it brackets the measured TPOT. State every assumption inline. Conclusion
  framed as a *quantitative hypothesis* that the P0 counters test.
- [ ] **MLA KV bytes/token check (section 3).** 6.5 GiB ÷ 426,640 tok ≈ 16 KiB/tok;
  decompose against `fp8_ds_mla` latent dims + Lightning Indexer cache using
  DeepSeek-V4-Flash public `config.json` (cite). Independent verification of the
  vLLM concurrency line from T3.
- [ ] **Eagle3 acceptance-model box (section 6).** Expected tokens/pass from
  per-position rates: 1 + 0.802 + 0.802·0.551 + 0.802·0.551·0.415 ≈ 2.43 vs
  logged mean acceptance length 2.77; discuss the gap (bonus token semantics,
  window mismatch). Source: T6 acceptance log lines.
- [ ] **Little's-law cross-check (section 7).** λ ≈ running/E2E_p50 ≈ 32/45.6 ≈
  0.70 req/s; implied queue wait ≈ waiting/λ ≈ 64 s vs measured TTFT p50 11.2 s /
  p95 59.7 s; state the gauge-peak-vs-mean caveats. Source: T5 table.

### Task 1.2 — figures (mermaid, GitHub-native; one existing PNG)

- [ ] **F1** (section 1): serving-path layer map (client → proxy → scheduler →
  prefill → decode → KV → hardware) with Inv 1–5 pinned to their layer.
- [ ] **F2** (section 3): per-GPU memory partition, two stacked bars — healthy
  steady state (Kimi 71.92 weights + 9.44 KV + 1.46 graphs vs 84.24 budget;
  DeepSeek 28.9; free ≈ 26.6) vs DEP crash arithmetic (88.44 → −19.08). Sources:
  T1/T3/T6.
- [ ] **F3** (section 6): embed existing
  `results/runs/2026-06-05_w1_evidence/eagle3_horizontal_flow.png`
  (relative path from `docs/writeups/`).
- [ ] **F4** (section 4): TTFT channel timeline — reasoning vs content vs
  proxy-stripped stream.

### Task 1.3 — statistics, TL;DR, methods, synthesis, references

- [ ] State `n` next to every aggregate; where n=5, report min/median/max and
  drop or caveat p95 ("p95 of n=5 ≈ sample max"). ABBA ordering moves from T8
  into section 2 as protocol.
- [ ] Write section 0 (TL;DR) and section 2 (The machine and the method).
- [ ] Write section 8 (Synthesis): capacity model (memory partition), latency
  model (TTFT decomposition incl. channel term), throughput model (roofline +
  queueing); each ends with one falsifiable W2 prediction.
- [ ] Upgrade references: Leviathan et al. (arXiv:2211.17192), Chen et al.
  (arXiv:2302.01318), Li et al. EAGLE-3 (arXiv:2503.01840), Kwon et al.
  PagedAttention (arXiv:2309.06180), Pope et al. (arXiv:2211.05102),
  DeepSeek-V2 for MLA (arXiv:2405.04434), NVIDIA H200 datasheet; keep Miao et
  al., vLLM #40691, LiteLLM docs; JarvisLabs blog becomes secondary next to the
  EAGLE-3 paper.

## Etap 2 — server slot 2026-06-10 (separate plan)

`docs/plans/2026-06-10-server-session.md` — P0 GPU counters (idle /
single-stream / batched windows) + P2 hop attribution (R1, `metrics_delta.py`).
Maps to: section 7 (P0 promotes HBM-vs-PCIe from L1 toward L2, #34 core) and
sections 4–5 (P2 closes the client-vs-server deferred item, #44 R1).

## Etap 3 — integration (laptop, after the slot)

- [ ] Analyze P0 counters against the Task 1.1 roofline box predictions; write
  the verdict into section 7 and update the claim ledger / promotions table.
- [ ] Analyze P2 deltas (server-side identical vs client-side divergent); write
  into sections 4–5; update T2/T8 cross-references if the threads gain new
  evidence rows.
- [ ] Final pass: claim ledgers and section 9 promotions list reflect the new
  evidence levels; `git diff --check`; commit.

## Acceptance criteria

- Every quantitative box states inputs, assumptions, and artifact/datasheet
  sources inline; no claim rises above its evidence level.
- TL;DR fits one screen; all mermaid figures render on GitHub.
- Thread files remain the provenance record; the article introduces no number
  that lacks a source in `docs/writeups/w1/` or a cited public document.
- Docs-only validation (`git status` + `git diff --check`) per commit.
