# A Trustworthy First Measurement of a Co-Resident Multi-Model LLM Serving Stack on 8×H200: Phase 1 (W1) Scientific Note

| Field | Value |
|---|---|
| Project | `nanoserve-mini` — LLM inference performance lab |
| Phase | W1 (Phase 1): serving baseline, observability, and multi-model proxy |
| Date range | 2026-05-19 (first stream-debug capture) through 2026-06-12 (bottleneck close-out) |
| Hardware under test | Supermicro SYS-521GE-TNRT; 2× Intel Xeon Gold 6530 (128 CPUs, governor `schedutil`, NUMA/SNC-2); 8× NVIDIA H200 NVL, 143,771 MiB (140.40 GiB) per GPU; **PCIe Gen5-only interconnect, no NVLink / no NVSwitch** |
| Software under test | vLLM v0.20.0 (v0.20-series); CUDA 13.2; driver 595.58.03; NCCL 2.28.9; LiteLLM Proxy `main-v1.66.0-stable`; Prometheus v3 + Grafana; Docker Compose; Ubuntu 24 |
| Models | Kimi-K2.6 (~1T-parameter MoE, 4-bit Marlin WNA16 experts, EAGLE-3 speculative decoding) and DeepSeek-V4-Flash (FP8 MLA, MTP speculative decoding), co-resident |
| Primary evidence | `results/runs/2026-06-05_w1_evidence/` (commit `d0bb634`); `results/runs/2026-06-10_w1_article_evidence/` (DCGM counters + hop attribution); `results/runs/2026-06-11_bottleneck/`, `results/runs/2026-06-11_nvlink_boundary/` (TP-scaling + NVLink) |
| Source threads | [`docs/writeups/w1/`](w1/) (T1–T9) |
| Tracking issues | #31, #34, #37, #39, #44, #48, #49, #50 (repo `Czyszka/nanoserve-mini`) |

---

## Abstract

This note consolidates Phase 1 of the `nanoserve-mini` inference performance
lab: the bring-up, instrumentation, and first serving baseline of two
co-resident large language models (Kimi-K2.6, a ~1T-parameter MoE, and
DeepSeek-V4-Flash) on a single PCIe-only 8×H200 NVL node running vLLM v0.20.0
behind a LiteLLM Proxy. The central methodological thesis is that a first
measurement of a served LLM is a *claim about unstated preconditions*: the
number is accurate but misleading whenever one of those preconditions silently
fails. We examine nine investigation threads (T1–T9) in which prominent
first-pass observations — a startup crash, a null time-to-first-token (TTFT), a
proxy returning nothing, a 3.8× speedup, and 100% GPU utilization — each proved
to encode a hidden precondition, and we scope every claim on an explicit L0–L3
evidence ladder. The defensible W1 baseline that survives this scrutiny is a
direct-path (not proxied), single-stream, temperature-0, length-controlled
measurement of Kimi-K2.6: TTFT p50 837 ms / p95 1694 ms at 111.6 output tok/s
with EAGLE-3 enabled, versus p50 1675 ms / p95 4426 ms at 58.7 tok/s disabled
(both at identical 97-token median completion), i.e. ≈2.0× TTFT and ≈1.9×
throughput from speculative decoding rather than the 3.8× first observed.
Hardware-counter follow-up refuted an HBM-bandwidth-bound decode hypothesis
(DRAM_ACTIVE 9.3% single-stream, 7.0% batched) and isolated two
workload-dependent bottlenecks — a host-side per-step floor at low concurrency
and a PCIe-transport ceiling under batch — grounding a calibrated GO/NO-GO
verdict on NVLink 4-way bridges: buy only for batched serving of models that
genuinely require TP≥4, with a realistic finite-bandwidth projection of
≈1.8–2.2× against ideal-link ceilings of 2.1–2.7×.

---

## 1. Introduction

### 1.1 Goals of Phase 1

Phase 1 (W1) of `nanoserve-mini` had four operational goals: (i) bring up two
co-resident production-class models on a single 8×H200 NVL node under vLLM;
(ii) place a minimal, model-aware access layer (LiteLLM Proxy) in front of them;
(iii) stand up observability (Prometheus + Grafana over vLLM `/metrics` and GPU
telemetry) sufficient to *read* a serving bottleneck rather than guess at it;
and (iv) produce a first latency baseline under explicit controls. W1 is a
decision gate for a possible full `nanoserve` follow-up and a standalone
portfolio artifact; it is deliberately scoped as an engineering record, not a
success narrative.

### 1.2 Central thesis

The organizing claim of the phase is methodological rather than numerical:

> A first number from a served LLM is a claim about its preconditions. It is
> wrong not because the timer is broken, but because every measurement silently
> assumes a set of conditions, and the number lies whenever one of them does not
> hold.

The engineering skill is therefore locating *which* precondition a given number
depends on and checking it before trusting the figure. Most threads in W1
follow the same recurring move: **observe the number → distrust it → separate
symptom from cause → prove the mechanism from logs or source → scope exactly
what can now be claimed** — the investigation/measurement threads (T1, T2, T3,
T5, T6, T8, T9). The two justification-mode threads (T4, T7) instead run
decision → rationale → rejected alternative, with no distrusted first number.
The last step uses an evidence ladder borrowed from
the observability work ([T5](w1/t5-observability.md)) and applied uniformly:

| Level | Name | Meaning |
|---|---|---|
| **L0** | Observation | Read directly from a captured artifact. |
| **L1** | Diagnostic hypothesis | Best mechanistic reading of correlated signals — not yet tested. |
| **L2** | Supported causal claim | Survived a controlled, one-lever counterfactual. |
| **L3** | Robust claim | Repeated across workloads, windows, or configurations. |

W1 is by construction an **L0–L1 project** (short GPU slots, single-stream
workloads, few controlled counterfactuals); a 2026-06-10 to 2026-06-12
follow-up slot promoted a subset of claims to L2. The serving taxonomy of
Miao et al. [1] — client/proxy → scheduler → prefill → decode → KV cache →
hardware — supplies the map of *where* a precondition can hide.

### 1.3 Scope

In scope for W1: bring-up and memory budgeting, TTFT/TPOT metric definitions for
reasoning models, proxy transparency, speculative-decoding cost/benefit,
observability under load, and a bottleneck attribution feeding an NVLink
purchase decision. Explicitly out of scope (per roadmap): own inference engine,
PagedAttention/prefix-cache reimplementation, Kubernetes/Helm, TensorRT-LLM /
SGLang, and production HA/autoscaling. FP8 quantization of the compute path
(W3) and full TP-scaling throughput curves (W2) are named as future synthesis
material, not re-run here.

---

## 2. System under test

### 2.1 Hardware

The node is a Supermicro SYS-521GE-TNRT with two Intel Xeon Gold 6530 sockets
(128 logical CPUs, `schedutil` governor, four NUMA domains under SNC-2) and
eight NVIDIA H200 NVL GPUs, each exposing 143,771 MiB = **140.40 GiB** of
HBM3e. The GPU interconnect is **PCIe Gen5 only**: four 2-GPU PCIe switch pairs
({0,1}, {2,3}, {4,5}, {6,7}), with GPUs 0–3 under socket 0 and 4–7 under
socket 1; cross-socket traffic traverses UPI. There is no NVLink bridge and no
NVSwitch installed. This topology was confirmed directly from vLLM's own engine
log, which disables its custom all-reduce as *"not supported on more than two
PCIe-only GPUs"* and reports the FlashInfer all-reduce fallback failure as
*"expected on GPUs without NVSwitch"* ([T5](w1/t5-observability.md),
[T9](w1/t9-bottleneck-nvlink.md)). The datasheet lists an optional NVLink Bridge
as a purchasable upgrade, which motivates T9.

### 2.2 Software stack and topology

Two vLLM instances and one proxy run under Docker Compose
(`serving/compose/docker-compose.kimi-k2.6.yml`):

```
:8000  vllm        Kimi-K2.6          TP=8, gpu-mem-util 0.60, Eagle3 ON
:8004  vllm-small  DeepSeek-V4-Flash  TP=8, gpu-mem-util 0.20, FP8 MLA + MTP, --enforce-eager
:4000  litellm     routes {model:"kimi-k2.6"}→:8000, {model:"DeepSeek-V4-Flash"}→:8004
:9090  prometheus     :3001  grafana
```

The proxy surface is intentionally narrow: one OpenAI-compatible endpoint so a
benchmark client selects a model by changing the `model` field rather than the
base URL — no content-aware routing and no per-user keys
([T4](w1/t4-litellm-proxy.md)). Because one finite board (140.40 GiB/GPU) is
shared by both models, every `--gpu-memory-utilization` value is a partition
decision on that board.

### 2.3 Model configurations

| Parameter | Kimi-K2.6 (`:8000`) | DeepSeek-V4-Flash (`:8004`) |
|---|---|---|
| Class | ~1T-param MoE, 384 routed experts | FP8 MLA + Lightning Indexer sparse attention |
| Parallelism | TP=8 | TP=8 |
| `--gpu-memory-utilization` | 0.60 | 0.20 (0.25 documented alternative) |
| Speculative decoding | EAGLE-3, `num_speculative_tokens` 3 | MTP, `num_speculative_tokens` 1, `max_model_len` 8192 |
| Weight quantization | 4-bit Marlin WNA16 (experts) | FP8 |
| Checkpoint size | 554.30 GiB total (71.16 GiB/GPU weights at TP=8) | 20.32 GiB/GPU weights |
| `--max-model-len` | 131072 | 65536 |
| `--max-num-batched-tokens` | 4096 (ON arm) | 2048 |
| `--max-num-seqs` (baseline / prod) | 1 (baseline) / 32 (load) | 2 |
| Other | — | `--enforce-eager` (CUDA graphs off), `--kv-cache-dtype fp8`, `--block-size 256` |

Kimi-K2.6 cannot physically run at TP=4: 554.30 GiB / 4 ≈ 138.6 GiB/GPU against
a 140.40 GiB board, leaving no room for KV cache and runtime buffers, so TP=8 is
its only feasible configuration ([T9](w1/t9-bottleneck-nvlink.md)).

---

## 3. Methods

### 3.1 Benchmark harness and metric definitions

Client-side latency was measured with the project scripts
`measure_ttft_once.py` (streaming, single request), `request_once.py`
(non-streaming), and `run_sequential_benchmark.py` / `run_bench_suite`
(repeated streaming rows plus summary). The single-stream baseline used
`singlestream_lite_repeated` with `temperature 0`, `--max-num-seqs 1`, warmup 1
run plus measured runs. Throughput/latency under load and TP sweeps used
`vllm bench serve` (SWE-bench Lite dataset for batched runs; a synthetic
`random` 64-in / 512-out dataset with `--ignore-eos` for interactive floor
benches).

A central methodological result of the phase is that **TTFT for a reasoning
model is not a scalar but a (measurement point, channel) pair**
([T2](w1/t2-reasoning-ttft.md)). vLLM's server-side reasoning parser splits the
stream into `delta.reasoning` and `delta.content` channels; a reasoning model
emits reasoning tokens first, and content may arrive much later or never within
a finite token budget. The original benchmark parser timed only the
`delta.content` channel and therefore reported `TTFT: n/a` — a *correct* answer
to a too-narrow question. The fix (#31, commit `cca4022`, additive) added
`ttft_any_token_seconds` (first reasoning-or-content delta) and
`tpot_any_token_seconds` beside the content-only fields, and made an
all-reasoning response count as `completed`; the schema identifier remained
`nanoserve-mini.ttft-once.v2`. All W1 latency figures therefore name both
their measurement point (client vs server) and channel (content vs any-token).

### 3.2 Metrics collection

Server-side metrics were read from vLLM `/metrics` (v0.20.0), keyed on
`model_name`, with lifecycle-boundary mapping validated against a live dump:
`vllm:time_to_first_token_seconds`, `vllm:request_queue_time_seconds`,
`vllm:inter_token_latency_seconds`, `vllm:e2e_request_latency_seconds`,
`vllm:kv_cache_usage_perc`, and the `spec_decode_*` family (present only under
Kimi with EAGLE-3 ON). GPU hardware counters were captured with
`dcgmi dmon -e 155,1002,1004,1005,1009,1010` at 1 Hz across all eight GPUs
(SM_ACTIVE, PIPE_TENSOR_ACTIVE, DRAM_ACTIVE, PCIe TX/RX, power), averaged over
epoch-tagged windows with an activity filter (SM_ACTIVE ≥ 0.10 or a power
threshold) to exclude idle tails. Kernel-level attribution used torch-profiler
traces via the vLLM `--profiler-config` engine flag (the older
`VLLM_TORCH_PROFILER_DIR` env var was silently removed upstream in v0.20),
bucketed into comms / compute / other / gaps, with a profiler-overhead control
run for every trace. Hop attribution used vLLM's own Prometheus latency
histograms as a reference clock the proxy cannot touch: paired, ABBA-ordered,
one-request-per-delta snapshots (Δsum/Δcount) computing
`outside_vllm = client_observed − server_side`.

### 3.3 Evidence and provenance discipline

Each thread carries a per-file Evidence block mapping every headline number to
an artifact path and run-id. Primary artifacts are frozen at commit `d0bb634`
(2026-06-05 evidence freeze); the follow-up slot artifacts live under
`results/runs/2026-06-10_w1_article_evidence/`,
`results/runs/2026-06-11_bottleneck/`, and
`results/runs/2026-06-11_nvlink_boundary/`, with cross-run summaries in
`results/summaries/`. Raw profiler traces and secret-bearing environment dumps
are excluded from the repository by policy; only rank-0 text summaries and
redacted captures are committed. The controlled counterfactual ("dose-response")
method is used throughout: deliberately degrade one suspected mechanism while
holding everything else fixed, and treat a null effect as ruling that mechanism
out.

---

## 4. Results

### 4.1 T1 — Kimi bring-up: the crash after the weights fit

The first Kimi-K2.6 bring-up used data + expert parallelism
(`--data-parallel-size 8 --enable-expert-parallel`, DEP) at
`gpu-memory-utilization 0.6`. All eight engine-core processes died identically
during startup with `ValueError: No available memory for the cache blocks. Try
increasing gpu_memory_utilization`. The crash occurred *after* weights loaded
successfully (`Model loading took 88.44 GiB memory`, ~2 minutes earlier),
falsifying a naive "weights don't fit" reading. The mechanism is that
`gpu-memory-utilization` is a **post-load ceiling** checked when sizing the KV
cache, not a load-time allocation cap. Per-GPU arithmetic read directly from
`dep_full.log`:

```
budget   = 0.6 × 140.40 GiB                       =  84.24 GiB
− weights (DEP)                                   =  88.44 GiB   gpu_model_runner.py:4879
− CUDA-graph (measured)                           =   0.13 GiB   gpu_model_runner.py:6042
− activation peak (8192-tok prefill) + non-torch  ≈  14.75 GiB
──────────────────────────────────────────────────────────────
= Available KV cache memory                       = −19.08 GiB   gpu_worker.py:440
```

Kimi's non-KV footprint (103.32 GiB) already exceeds its 84.24 GiB ceiling, so
the KV budget goes negative and the engine refuses to start. The cause is
architectural: DEP replicates the dense (non-expert) backbone on every GPU,
while TP shards it.

| Weight class | Whole model | DEP /GPU | TP=8 /GPU |
|---|---:|---:|---:|
| 384 routed experts (4-bit, EP-sharded 1/8) | ~532 GiB | 66.6 | 66.6 |
| non-experts (MLA attn, norms, router, embeddings; replicated under DEP) | ~22 GiB | 21.9 | 2.7 |
| **total** | 554.30 | **88.44** | **69.3** |

The 69.3 GiB/GPU TP=8 column is a pre-TP-8 estimate (checkpoint ÷ 8, assuming
loaded ≈ on-disk size); T6's later *measured* TP=8 load is 71.16 GiB/GPU (§4.6),
the trustworthy figure — the ~1.9 GiB (~2.6%) gap is the on-disk-size
approximation.

The DEP replication penalty is `(7/8) × 21.9 ≈ 19.1 GiB/GPU` — separately
computed from, and only coincidentally near, the −19.08 GiB deficit (the deficit
also folds in activations and the graph term). The decision was to switch
parallelism to **TP=8** rather than raise the cap as the error message advised:
matching TP's KV pool under DEP would require `util ≈ 0.6 + 19.1/140.40 ≈ 0.74`,
at which Kimi alone claims ~104 GiB and, with co-resident DeepSeek at 0.2
(~28 GiB), the two reserve ~0.94 of the card, leaving only ~6% (~8 GiB) for
out-of-budget CUDA/NCCL/NIXL buffers — infeasible under co-residency. TP=8 at
0.6 leaves ~27 GiB of card headroom, and DEP's only payoff (eight independent
replica streams) is worth nothing under W1's single-stream baseline.

**Claim ledger.** Budgets, footprints (88.44 / 20.32 GiB), and the deficit are
L0; TP=8 fixing the crash is L0 (it serves every other thread); DEP-at-0.74
being infeasible is L1 (calculated, not run); no DP-vs-TP throughput comparison
exists because DEP never started.

### 4.2 T2 — Reasoning TTFT: the null that was correct

`measure_ttft_once.py` against Kimi-K2.6 returned `TTFT: n/a` and `TPOT: n/a`,
while the same script returned ordinary numbers against DeepSeek-V4-Flash. The
Kimi stream carried many non-empty `delta.reasoning` chunks but never
`delta.content`; the captured `stream_short_prompt.sse.txt` was entirely
reasoning, ending at `finish_reason: "length"` after 64 tokens. A differential
diagnosis rejected four candidate causes (broken timer, no output, crashed
stream, an invalid non-stream capture combining `stream_options` with
`stream:false`) and accepted one: the client metric definition was too narrow.
After the additive fix, the two clocks diverge on the same stream:

| Model (direct, n=10) | content TTFT | any-token TTFT | gap |
|---|---:|---:|---:|
| Kimi-K2.6 | 0.592 s | 0.209 s | **2.8×** |
| DeepSeek-V4-Flash | 0.253 s | 0.253 s | 1.0× |

Client-vs-server TTFT disagreement for the same request has four separable
causes: (1) **path scope** — the client clock spans transport, proxy, queueing,
prefill, SSE, and its own parse loop, so client ≥ server by construction;
(2) **channel** — vLLM counts the first *generated* token regardless of label,
so its number tracks the any-token view (~0.2 s), not content (~0.59 s);
(3) **component attribution** — one client number vs vLLM's queue/prefill/decode
histograms; (4) **aggregation** — one wall-clock value per request vs a
histogram over a scrape window. Factors 1 and 2 became measurement on
2026-06-10: snapshotting vLLM histograms around isolated requests put server
TTFT at **p50 93 ms** while the same requests' client clocks read 177 ms
(any-token) and 1.82 s (content), leaving a residual ~84 ms path-scope gap on
loopback.

**Claim ledger.** The channel split is L0 → robust (reproduced independently in
T6 captures, any-token ≈ 204 ms). The paired client-vs-server isolation is L0,
closed 2026-06-10 (n=5, direct path,
`results/runs/2026-06-10_w1_article_evidence/p2_hop_attribution/`). Scope is
limited to this Kimi-K2.6/vLLM build; the R2–R8 program stays in #44.

### 4.3 T3 — DeepSeek VRAM budget: the same wall, co-resident

Choosing DeepSeek's cap with Kimi co-resident reproduced T1's failure family.
DeepSeek weights are a constant 20.32 GiB/GPU; the cap only sizes the leftover
KV pool:

| Cap | Available KV | Outcome |
|---|---:|---|
| 0.15 | **−0.49 GiB** | `EngineCore failed to start` |
| 0.20 | +6.5 GiB | healthy |
| 0.25 | +13.49 GiB | healthy |

A second, nested lying number appeared in the 0.20 startup: `GPU KV cache size:
5,284 tokens` printed beside `Maximum concurrency … 6.51x`, which do not
reconcile (5,284 / 65,536 = 0.08, not 6.51×). Reading vLLM source, the two
figures come from different functions in `kv_cache_utils.py`: the size line
(`_report_kv_cache_config`) is a per-group display figure
(`num_blocks / number_of_KV_cache_groups × min_block_size`), while the
concurrency line (`get_max_concurrency_for_kv_cache_config`,
`num_blocks / blocks_per_max_len_request`) is the trustworthy capacity.
DeepSeek-V4 carries more than one KV-cache group (the `fp8_ds_mla` MLA latent
cache plus a separate FP8 cache for the Lightning Indexer sparse attention), so
the size line deflates by an identical **80.7×** at both caps — systematic, not
noise. Real capacity at 0.20 is ~427k tokens (~6.5 full 64k contexts), not
5,284; this is the still-open upstream bug vllm-project/vllm#40691 [3]. The cap
choice is a partition decision: **0.20** is the Phase 1 default (leaving
~26.6 GiB/GPU free as stability margin for the latency-critical Kimi co-tenant),
with 0.25 documented for when a real concurrent DeepSeek workload makes KV the
binding resource (~7 GiB headroom cost). A serviceability smoke at both caps
served a `"say OK"` → `"OK"` (2-token) completion to completion with equivalent
cold-start latency (0.20: TTFT 15.23 s, E2E 21.66 s; 0.25: TTFT 15.18 s,
E2E 21.65 s). Separately from this cold cap-sweep smoke, a same-methodology
single-stream *latency* baseline for DeepSeek does exist (direct `:8004`,
cap 0.20, `singlestream_lite_repeated`, temperature 0, warmup 1 + n=10,
commit `ec3df59`): TTFT p50 1.26 s / p95 1.58 s, E2E p50 1.93 s at
`max_tokens=64` (a `max_tokens=1024` rerun gives TTFT p50 1.45 s / E2E 2.18 s),
at a 3-token median completion for these prompts — a latency baseline, not a
throughput one.

**Claim ledger.** Budgets, weights (20.32 GiB), and the KV-display discrepancy
are L0; the ~6.51× / ~13.54× concurrency figures are implications of the KV
budget, not measured throughput.

### 4.4 T4 — LiteLLM Proxy: the correct minimal routing boundary

LiteLLM Proxy on `:4000` fronts both backends via explicit model-name routing
(`kimi-k2.6` → `http://vllm:8000/v1`, `DeepSeek-V4-Flash` →
`http://vllm-small:8004/v1`), with conservative settings `drop_params: true`,
`request_timeout: 600`, and a single `LITELLM_MASTER_KEY`. Smoke tests
(2026-05-19) and full benchmark runs confirmed both models reachable through the
proxy. The decision documents what LiteLLM does *not* provide in W1: per-user
virtual keys (which require PostgreSQL + Prisma migrations; a public issue
reports a Prisma-migration failure with a missing `team_member_permissions`
column on v1.66.0-stable/v1.66.1, and Prisma migrations can fail and leave
schema drift in general — so DB-backed keys on this pinned tag warrant migration
smoke-tests rather than being a confirmed silent-failure mode), structured
per-request logging, and — critically — transparency for reasoning-model
streams. LiteLLM's published "8 ms P95 at
1k RPS" figure is explicitly rejected as a reference: it was measured against a
fake endpoint on a 4 CPU / 8 GB box, and proxy performance is version-dependent
(aiohttp became the default transport only in v1.72.0, after the pinned
`main-v1.66.0-stable`). Overhead is therefore treated as an empirical question
for this path (T8), and DB-backed governance is deferred to a later maturity
stage (#39). The choice is scoped against named rejected alternatives — direct per-model vLLM
ports (no single multi-model endpoint), a generic HTTP reverse proxy (nginx,
which would require hand-rolling model-aware OpenAI routing), and heavier
AI-gateway / semantic-router platforms (Envoy/Kong/Traefik AI Gateway, vLLM
Semantic Router, OpenRouter) — each deferred as more operational change than the
W1 baseline needs. A deep-research supporting report
([T4 deep-research](w1/T4-deep-research-report.md)) confirms the architectural
fit and the PostgreSQL/logging gaps against vendor documentation.

### 4.5 T5 — Observability and the 100%-utilization illusion

Under batched load (`--max-num-seqs 32`), `nvidia-smi` reported **100%
GPU-Util** while the board drew only ~180–240 W of its 600 W limit. Scheduler
signals over a 3-hour Prometheus window:

| Signal (batched, `--max-num-seqs 32`) | Value |
|---|---|
| running / waiting (kimi) | 32 / 45 |
| generation / prompt throughput | 327 / 1039 tok/s |
| KV cache usage | 44% peak |
| TTFT p50 / p95 | 11.2 s / 59.7 s |
| E2E p50 / p95 | 45.6 s / 90.8 s |
| ITL p50 | 0.106 s |
| Eagle3 draft acceptance | 0.493 |
| preemptions | 0 |

Two independent readings follow. First, the queue: `waiting 45 > running 32`
with KV at only 44% and zero preemptions means the queue forms at the
`max-num-seqs 32` admission cap, not from KV exhaustion (which would drive KV →
~100% with preemptions > 0). The node is **scheduler-bound, not KV-bound**
(L1), and TTFT p50 rising from ~0.84 s single-stream to 11.2 s under load is
queueing time, not slower serving. A self-consistency cross-check corroborates
the decode reading: 32 streams at ITL p50 0.106 s implies 32 × 1/0.106 ≈
302 tok/s against the 327 tok/s aggregate gauge (agreement within p50-vs-mean
noise). The Grafana dashboard's metric names all resolved against the live
v0.20.0 dump and its queue/latency/KV panels demonstrably filled under load —
closing T5 for W1, with fuller DCGM panels deferred to #34.

Second, the power gap. The initially-recorded L1 diagnosis was a
**memory-bound decode signature**: decode reads whole-layer weights from HBM
with low arithmetic per byte, so SMs report busy while the card sits far from
its power ceiling. Because utilization percentage alone cannot separate an
HBM-bandwidth stall from a PCIe all-reduce stall on this PCIe-only TP=8 node, a
follow-up (2026-06-10) captured DCGM counters across three windows:

| DCGM counter (per-GPU mean, active samples) | idle | single c=1 | batched c=64 |
|---|---:|---:|---:|
| power draw | ~99 W | ~169 W | ~199 W (max 260) |
| `SM_ACTIVE` | 0.000 | 0.21 | 0.20 |
| `PIPE_TENSOR_ACTIVE` | 0.000 | 0.012 | 0.064 |
| `DRAM_ACTIVE` | 0.000 | **0.093** | **0.070** |
| PCIe TX / RX per GPU | ~0 | 1.9 / 6.0 GB/s | 6.0 / 8.0 GB/s |

`DRAM_ACTIVE` **refuted** the memory-bound hypothesis: the memory system is busy
only 9.3% of the time single-stream and 7.0% under batch — more than 90% idle
while the node serves at full tilt. (The textbook intuition missed because the
experts are 4-bit and only a fraction activate per token, so a ~1T MoE reads far
fewer bytes per token than a dense model.) This "sixth lying number" was the
document's *own* first-draft diagnosis. What the counters do show is that
nothing is saturated: SMs resident ~20% of the time, tensor pipes 1–6%, HBM
≤9%, PCIe links at 6–8 GB/s (~10–13% of a Gen5 x16's ~63 GB/s per direction) —
the signature of **latency-bound, serialized execution**, with the per-layer
PCIe all-reduce as the standing suspect. A coarse consistency check attributes
the c=1 window's per-token step time (~22.5 ms, in the poorly-drafting
~46 tok/s window) to the TP all-reduce ladder — 61 decoder layers × ~2
reduction points ≈ 122 synchronous rounds per step, a config-derived estimate
rather than a counted NCCL total — pricing each round at ≈0.2 ms, a plausible
small-message PCIe all-reduce cost on eight GPUs. (One caveat: the c=1 window used random 64-token
`--ignore-eos` prompts that draft poorly under Eagle3, decoding at ~46 tok/s vs
a 112 tok/s natural-prompt baseline; this does not change the DRAM_ACTIVE
verdict.)

**Claim ledger.** Both tables are L0. HBM-bandwidth-bound decode is **Refuted**
(2026-06-10). PCIe-comms/serialization-bound is L1, strengthened.
Scheduler-bound-not-KV-bound is L1, unchanged. Promotion to L2 needs a
concurrency sweep at fixed prompt/output and a comms-level lever — carried into
T9.

### 4.6 T6 — EAGLE-3 speculative decoding: the 3.8× that was partly a lie

A single-shot ON-vs-OFF comparison of EAGLE-3 for Kimi-K2.6 showed E2E and
content-TTFT 3.8× faster. However, at temperature 0 the two arms generated
different amounts of output (OFF 142 completion tokens vs ON 69; reasoning trace
546 vs 240 chars), because floating-point reduction order under TP=8 varies
run-to-run and generations are not token-identical (completion ranged 94–190 ON,
97–285 OFF). Controlling for length by repeating until median completion was
identical (97 tokens in both arms) isolates decode-rate effects:

| Metric (repeated, p50) | Eagle3 ON | Eagle3 OFF | ratio |
|---|---:|---:|---:|
| TTFT p50 | **837 ms** | **1675 ms** | **2.0×** |
| TTFT p95 | 1694 ms | 4426 ms | 2.6× |
| E2E p50 | 857 ms | 1724 ms | 2.0× |
| output tok/s | 111.6 | 58.7 | **1.9×** |

The honest headline is **≈2.0× p50 TTFT and ≈1.9× decode throughput**; the
single-shot 3.8× is one draw from a 2.1×–3.8× length-dependent band, and the
non-determinism is itself a finding (single-shot latency is not a stable
comparison unit here). The choice of EAGLE-3 is justified by model scale: on
Llama-3.1-8B heuristics win (EAGLE 1.43× chat, Suffix 1.45× code, EAGLE-3 only
1.03×) while on Llama-3.3-70B the learned head dominates (EAGLE-3 1.57× chat,
1.60× code) [2]; Kimi-K2.6 (~1T MoE) is far past that crossover and its measured
1.9–2.4× lands at or above the 70B numbers. The mechanism is predictable from
the server log: mean acceptance length 2.77 (Accepted 626 / Drafted 1062;
per-position acceptance 0.802, 0.551, 0.415; quieter windows 3.15 / 71.7%). Mean
acceptance ≈ 2.8 sets an ideal decode speedup of ≈2.8×; measured TPOT-any
improves 2.4× (~85% of ideal), the missing ~15% being draft + verification
overhead. any-token TTFT is unchanged (~204 ms both arms) because it is bounded
by prefill, which Eagle3 does not touch; content TTFT improves because content
arrival requires decoding the whole reasoning trace. VRAM cost is small and
measured: ON loads 71.92 GiB/GPU vs OFF 71.16, so the draft adds ≈0.76 GiB/GPU
(~1%), consistent with a 5.62 GiB TP-sharded draft checkpoint (5.62/8 ≈ 0.70)
whose embedding table is shared with the target. One flagged (not hidden)
A/B impurity — `--max-num-batched-tokens` 4096 (ON) vs the 8192 default (OFF) —
does not bind at a 15-token prompt and `--max-num-seqs 1`, but must be
controlled under concurrency.

**Claim ledger.** Acceptance rates, token counts, and the VRAM delta are L0.
The ~2× TTFT / ~1.9× throughput result is L1, robust within single-stream.
"Lossless" is a theoretical guarantee (rejection sampling), not a measured
quality eval. Concurrent-serving behavior and `num_speculative_tokens` tuning
are not shown.

### 4.7 T7 — Host directories for evidence triage

Observability runtime data (Prometheus and Grafana state) is kept in explicit
host bind mounts
(`/home/ubuntusrv2/working/nanoserve-observability/prometheus-data:/prometheus`,
`…/grafana-data:/var/lib/grafana`) rather than Docker named volumes, with
configuration/provisioning mounted read-only from the repository. The rationale
is operational: within a roughly-two-day-per-week GPU slot, evidence must be
triaged and copied off the server quickly with standard shell tools, which named
volumes make opaque. The only runtime risk is UID/GID and permission mismatch
(Grafana runs non-root, Prometheus as `nobody`), the first troubleshooting step
if containers fail to start. The decision was validated by T5's successful
2026-06-05 metric and dashboard collection. Observability image versions are
not pinned (unlike the serving compose), tracked in #49.

### 4.8 T8 — LiteLLM proxy overhead and the reasoning-strip hazard

The proxy's cost decomposes into three separable effects: (A) a per-request
processing cost, (B) a streaming-semantics change, and (C) concurrency scaling
(decisive for production, deferred as R2 in #44). The dominant W1 finding is
(B): LiteLLM `main-v1.66.0-stable` does not forward `delta.reasoning` and
collapses the reasoning channel into the final-answer stream. Under a
`max_tokens=64` budget spent entirely on reasoning, the identical prompt yields
opposite client outcomes:

| Path | chunks | reasoning_chars | any-token TTFT | completed |
|---|---:|---:|---:|---|
| direct `:8000` | 26 | 242 | 0.214 s | **true** |
| proxy `:4000` | 3 | 0 | null | **false** |

Both paths generated the same 64 tokens server-side and neither started the
final answer (`output_chars = 0` on both — a Kimi + short-`max_tokens` property,
not a proxy effect), which pins the difference on **delivery, not compute**. The
2026-06-10 attribution used vLLM histograms as the reference clock (5 pairs per
variant, ABBA-ordered, one request per delta):

| Path (n=5, medians) | server TTFT | server E2E | tokens | client outcome |
|---|---:|---:|---:|---|
| direct `:8000` | 93 ms | 0.576 s | 64 | `completed: true` — 23–24 chunks, ~245 reasoning chars |
| proxy `:4000` | 96 ms | 0.606 s | 64 | `completed: false` — 3 chunks, 0 reasoning chars, **5/5** |

The engine did identical work on both paths (first token within ~3 ms), so the
strip is pure delivery. The hop's own per-request processing cost, isolated as
`client E2E − server E2E` paired, is **~37 ms median** (36.8 ms at
`max_tokens=64`, 36.5 ms at 1024; per-pair spread −7…+81 ms); LiteLLM's own
`x-litellm-overhead-duration-ms` header self-reports 24.4 ms on a non-streaming
request. Where an answer does arrive (`max_tokens=1024`), the collapse delays
the proxy client's first token ~1.7 s after direct's, scaling with reasoning
length — a semantics problem, not a latency line-item. The decision is to
measure the W1 baseline **direct**, retaining the proxy only as the correct
minimal routing boundary.

**Claim ledger.** Strip-is-delivery-not-compute is **L2** (promoted 2026-06-10,
path as the single lever, 5/5 pairs). The ~37 ms c=1 hop cost is L0. R2/R3 are
deferred to #44; note R3's fixed-vs-per-chunk split cannot be measured through
this proxy version, which strips the stream to 3–5 chunks regardless of length.

### 4.9 T9 — Bottleneck attribution and the NVLink 4-way decision

T9 closes the observability thread's open question by identifying the actual
decode bottleneck across TP configurations and workload shapes, then converting
it into a calibrated GO/NO-GO verdict on optional NVLink 4-way bridges. A
control model (Qwen3.6-35B-A3B, which fits on one H200) enabled a clean TP curve
where Kimi (TP=8-only) could not.

At **interactive c=1**, the step is dominated by a host-side fixed floor, and
adding GPUs makes a single user *slower* because the floor is paid once while
all-reduce rounds are added:

| TP (c=1) | step / ITL med (ms) | TPOT med (ms) | comms tax vs TP1 |
|---|---:|---:|---:|
| 1 | 8.98 | 3.68 | — (comms-free anchor) |
| 2 | 9.91 | 3.65 | +0.93 ms |
| 2 cross-socket (0,4) | 9.13 | 3.51 | +0.15 ms → no UPI tax |
| 4 | 10.54 | 4.00 | +1.56 ms (4× noise band ±0.4) |
| 8 | 14.16 | 5.12 | +5.18 ms (13× noise) |

At **batch c=64**, scaling efficiency collapses with rank count; TP4 and TP8 are
absolutely slower than a single GPU, with counters showing GPUs waiting in
synchronous collectives rather than computing:

| TP (c=64) | out tok/s | scaling eff. | per-GPU power / SMACT | PCIe RX |
|---|---:|---:|---|---:|
| 1 | 1202 | 100% (def.) | 436 W / 0.665 | ~0 |
| 2 | **1404** | 58% | 255 W / 0.359 | 6.25 GB/s |
| 4 | 680 | 14% | 142 W / 0.118 | 5.65 GB/s |
| 8 | 257 | 2.7% | 111 W / 0.053 | 7.18 GB/s |

Torch-profiler traces quantify the comms share: Kimi TP8 c=1 is 63% gaps /
22.5% NCCL / 9.1% compute, while Kimi TP8 c=16 flips to 10% gaps / 83.9% NCCL /
4.6% compute, and Qwen TP4 c=64 is 33% / 53.3% / 5.6%. Two caveats attach to
these span shares and propagate into every projection below: NCCL kernel time
includes in-kernel peer-wait, so it is an *upper* bound on pure transfer
(interactive projections are optimistic); and the batched trace windows include
the prefill burst, so the pure-decode comms share is likely *higher* than the
span share (batched projections are conservative in that respect). The 53.3%
share is additionally corroborated by a converging efficiency calculation:
removing it would lift TP4's 680 tok/s to ≈1456, matching TP2's measured
1404 tok/s — two methods, one number. Every batched TP=8 config
eventually pins PCIe RX at a **~7.2–7.9 GB/s ceiling** regardless of model (Kimi
c≥8, Qwen TP8 c≥16); Qwen TP4 batched instead tops out lower (RX 5.65 GB/s),
bottlenecked by rank-coordination overhead before the transport ceiling comes
into play. Two
placement doses falsified an initial "link class / UPI-crossing" hypothesis:
cross-socket TP2 (GPUs 0,4) was no worse than same-switch, and cross-island TP4
(0,1,4,5) was actually ~5% *better* at c=64 (48.3 ms / 716 tok/s vs 53.7 ms /
680 tok/s) — so the real cause is **rank count sharing a transport ceiling**,
not which physical path traffic takes. A `NCCL_P2P_DISABLE=1` dose at TP2
produced a null effect (1396 vs 1404 tok/s), showing 2-rank comms is not
latency-sensitive. Floor decomposition (Qwen TP1 c=1) found MTP speculative
orchestration is the single largest named component (3.57 ms of an 8.93 ms
floor, 40%), CUDA graphs already mask ~46 ms/step of launch overhead (eager dose
8.93 → 55.1 ms), and the CPU governor was exonerated. (The TP1 c=1 profiler
trace itself is contaminated by first-request `torch.compile` and was used only
qualitatively; the quantitative floor attribution rests on the clean dose
series.)

The projection to NVLink 4-way bridges is a two-stage Amdahl calculation whose
reading criteria were **pre-registered in the session plans before the
measurements ran**, so the verdict could not be fitted to the data. Stage one
bounds the gain of an infinitely fast link that removes all covered
communication, `S_ideal = 1/(1 − s·capture)`. Stage two prices a real bridge:
with PCIe Gen5 x16 at 128 GB/s and the H200 NVL bridge at 900 GB/s
bidirectional, `S_nvlink = 1/(1 − s·capture·(1 − B_PCIe/B_NVL))`, where
`1 − 128/900 = 0.858` — the covered communication term is shortened by ~86%,
not removed. The comms share `s` is measured per scenario (TP4 c=1:
14.8% = 1.56 ms tax / 10.54 ms step; TP4 c=64: 53.3%; TP8 c=1: 22.5%; TP8
c=16: 83.9% — trace span shares, subject to the two caveats above). The
`capture` fraction — how much of the communication a 4-GPU island intercepts —
follows the ring all-reduce topology: 1.0 for TP≤4 (the whole group fits one
island), ≈0.75 for TP=8 (6 of 8 ring legs are intra-island):

| Scenario | Verdict | `S_ideal` (ceiling) | `S_nvlink` (realistic) | Evidence level |
|---|---|---:|---:|---|
| Model fits 1–2 GPUs (Qwen-class), any c | **NO-GO** | 1.00× | 1.00× | L2 causal (nop2p null, tax ≈ noise) |
| Running TP≥4 for a model that fits on fewer | **NO-GO** (config error, not hardware) | — | — | L2 (throughput: TP8 ramp peak 437 vs TP2 1404 tok/s) |
| Model requires TP=4, interactive c=1 | **NO-GO** | 1.17× | 1.15× | L2 (tax measured; placement dose realized ≈ 0 at c=1) |
| Model requires TP=4, **batched** | **GO** | 2.14× | **1.84×** | L2 (trace + converging efficiency calc) |
| Kimi-class TP=8, interactive c=1 | **NO-GO** | 1.20× (1.29× at capture 1) | ≤ 1.17× | L2 (trace) |
| Kimi-class TP=8, **batched** | **GO** | 2.70× (6.2× at capture 1) | **2.18×** | L2 (trace) + counters for c≥8 |

The config-error row is the only one measured by throughput rather than comms
share: the TP8 concurrency-ramp peak (437 tok/s at c=16) reaches 31% of the
TP2 optimum (1404 tok/s), so the cure is configuration, not hardware. Three
qualifications bound the remaining projections. First, the strongest row's
s=0.839 was traced inside the reproducible c=16 scheduler pathology (ITL
512 ms, reproduced at 525 ms; c=32 is ~4× better on the same hardware) and is
explicitly not representative of every high-concurrency operating point — the
c=32 share is extrapolated from identical counter signatures (RX ceiling,
SMACT), not traced. Second, the peer-wait and prefill-dilution trace caveats
push in opposite directions: interactive projections are optimistic upper
bounds, batched projections conservative in the pure-decode share. Third, the
TP=4-batched GO is conditional on TP4-class models actually entering the
serving roadmap (a W2 question).

The verdict: buy NVLink 4-way bridges only if the node's mission is
batched/throughput serving of models that genuinely require TP≥4 — realistic
projected gain ≈1.8–2.2× (`S_nvlink`), against ideal-link ceilings of
2.1–2.7× — and do not buy for interactive latency or for anything fitting on
1–2 GPUs. The decision is thus about the workload roadmap, not the hardware;
T9 delivers only the performance half of the cost-benefit (price and logistics
are a company-side input), and the free software levers — the c=16 scheduler
pathology and the MTP orchestration share of the per-step floor (40%) — must
be exhausted before attributing the batched pain to the link. The standalone
decision note
([w1/nvlink-4way-notatka-decyzyjna.md](w1/nvlink-4way-notatka-decyzyjna.md))
records the full two-stage calculation in Polish; this section reproduces its
`S_ideal`/`S_nvlink` columns and its measured `s`/`capture` inputs verbatim.

**Status.** COMPLETE, measurements closed 2026-06-12 (#50). HBM-bandwidth-bound
is refuted; the two-bottleneck attribution (host floor at c=1, PCIe transport at
batch) is L2 for the purchase-decision scenarios via trace + placement doses.

---

## 5. Discussion

### 5.1 Five (really six) numbers that lied

The phase is organized around five prominent first-pass numbers — `crash`,
`n/a`, `completed: false`, `3.8×`, `100%` — each accurate yet misleading because
it silently depended on an unstated precondition:

| Number | Hidden precondition | Corrected reading |
|---|---|---|
| `crash` (T1) | `gpu-memory-utilization` is a post-load KV ceiling, not a load cap | DEP replicates the dense backbone; TP=8 restores a positive KV budget |
| `n/a` (T2) | TTFT was defined only on the content channel | reasoning models need a (measurement point, channel) pair; any-token TTFT ≈ 0.209 s |
| `completed: false` (T8) | the proxy does not forward `delta.reasoning` | a usability/correctness hazard, not added latency; measure direct |
| `3.8×` (T6) | temperature 0 does not fix output length under TP=8 | length-controlled gain is ≈2.0× TTFT / ≈1.9× throughput |
| `100%` (T5) | GPU-Util only means some kernel was resident | nothing is saturated; latency-bound serialized execution |

A sixth number lied about the authors: the first-draft "memory-bound decode"
diagnosis (T5) was refuted by direct DCGM counters (DRAM_ACTIVE ≤ 9%). The
demonstrable point is that the same observe → distrust → verify reflex must be
turned on one's own conclusions, not only on the system under test.

### 5.2 Measurement-validity themes

Three cross-cutting validity lessons recur. First, **a printed number is an
artifact to be verified, not an oracle** — the KV-cache-size log line (T3) is
deflated 80.7× by an internal normalization bug, and vLLM's server TTFT tracks a
different channel than a naive client parser (T2). Second, **client and server
metrics for the same request legitimately disagree** through four separable
causes (path scope, channel, component attribution, aggregation); conflating
them misattributes the gap to the wrong layer. Third, **a headline ratio must be
controlled for confounds before it is trusted** — output-length variance under
non-deterministic TP decode inflated the Eagle3 speedup (T6), and utilization
percentage cannot distinguish HBM-bandwidth stalls from PCIe all-reduce stalls
without hardware counters (T5, T9).

### 5.3 KV/VRAM budgeting insights

The strongest single baseline lesson is that **the first serving failure mode is
KV-cache budget exhaustion, not weight memory**. Two independent bring-up
failures share identical root-cause arithmetic — Kimi DEP at −19.08 GiB and
DeepSeek at cap 0.15 at −0.49 GiB — both failing before serving a token. On a
shared board, every `--gpu-memory-utilization` value is a partition decision:
the cap that enables startup and the cap that leaves safe stability margin for a
co-tenant are not the same thing. This locates the binding constraint precisely
where Miao et al. [1] place the KV-cache memory-management layer at the center of
serving performance.

---

## 6. Limitations and threats to validity

- **Single-node, single-driver specificity.** All results are specific to vLLM
  v0.20.0, CUDA 13.2, driver 595.58.03, on one PCIe-only 8×H200 NVL node. They do
  not generalize to NVLink/NVSwitch topologies or other runtimes.
- **Single-stream baseline, not a throughput claim.** The headline Kimi baseline
  is single-stream, `--max-num-seqs 1`, one short prompt. The batched picture is
  queue-dominated (327 tok/s at 11.2 s TTFT) and reported separately.
- **DeepSeek has no throughput baseline.** Completions for these prompts run
  ~3 tokens, so a tok/s rate would be an artifact; the cap-sweep serviceability
  check was a 2-token smoke (`"say OK"` → `"OK"`). A same-methodology
  single-stream *latency* baseline does exist, however (TTFT p50 1.26 s / p95
  1.58 s, E2E p50 1.93 s, n=10, direct `:8004`; §4.3). A real generation workload
  is still owed (T8 R7 / #44).
- **Reasoning-TTFT finding is implementation-specific.** It applies to this
  Kimi-K2.6/vLLM OpenAI-compatible streaming build, not to all reasoning models.
- **Evidence-ladder honesty.** W1 is predominantly L0–L1. Only two claims are
  L2 (the proxy reasoning-strip and the T9 NVLink purchase scenarios via
  placement doses); the HBM-bandwidth-bound decode hypothesis is separately
  **Refuted** as a clean counterexample, not an L2 claim. No L3 claim is made.
- **Confounded cross-run comparisons.** The batched ITL vs single-stream TPOT
  comparison mixes prompt workload (SWE-bench Lite vs a 15-token synthetic
  prompt) with concurrency, so it is "consistent with" the scheduler-bound
  reading rather than a clean one-lever test.
- **T9 residuals.** The Kimi c=16 comms share (s=0.839) sits inside an
  acknowledged scheduler pathology and the c=32 share is extrapolated from
  counter signatures, not directly traced. NCCL ring-vs-tree selection was not
  logged (`NCCL_DEBUG=INFO` off), so the round-count model — 61 decoder layers
  × ~2 TP reduction points ≈ 122 synchronous rounds per step — and the ~14 KiB
  c=1 hidden-state payload are config/literature-derived estimates, not counted
  NCCL operations. The per-round NVLink-island cost `r_NVL4 ≈ 20–30 µs` is a
  labeled, unmeasured assumption (cloud NVLink rental was considered and
  rejected 2026-06-10); it is a *per-all-reduce-round* figure, distinct from the
  public single-hop P2P latencies the decision note cites (NVLink 2–9 µs vs
  PCIe ~20 µs), and the decision note's `S_nvlink` projection uses the 128/900
  bandwidth ratio instead, so the verdict does not depend on `r_NVL4`'s exact
  value.

---

## 7. Conclusions and Phase 2 outlook

Phase 1 established a defensible multi-model serving baseline through systematic
bring-up from an empty node to a two-model vLLM + LiteLLM Proxy stack, and its
lasting contribution is methodological: a repeatable discipline for asking what
must be true for a number to mean what it appears to mean, scoped on an explicit
evidence ladder. The concrete baseline is direct-path, single-stream,
temperature-0, length-controlled Kimi-K2.6: **TTFT p50 837 ms / p95 1694 ms at
111.6 tok/s (Eagle3 ON)** versus **p50 1675 ms / p95 4426 ms at 58.7 tok/s
(OFF)**, both at 97-token median completion — a ≈2.0× TTFT and ≈1.9× throughput
gain from speculative decoding. The follow-up slot promoted the proxy
reasoning-strip to a causal (L2) claim (~37 ms hop cost, delivery not compute),
refuted the HBM-bandwidth-bound decode hypothesis via DCGM counters, and
resolved the bottleneck into two workload-dependent regimes that ground a
calibrated NVLink 4-way verdict.

The results imply the following for the roadmap:

- **NVLink 4-way bridges** are worth buying only for batched/throughput serving
  of TP≥4 models — realistically ≈1.8–2.2× serving throughput for a 900 GB/s
  bridge (`S_nvlink`), with ideal-link ceilings of 2.1–2.7× and an absolute
  ceiling of ~6.2× — and not for interactive latency or 1–2-GPU models; free
  software levers (the c=16 scheduler pathology, MTP orchestration share of the
  per-step floor, and a newer vLLM step-loop) should be exhausted first (#50).
- **Proxy productionization** (per-user keys via PostgreSQL, structured logging)
  and the full R1–R8 overhead program under concurrency remain open (#39, #44).
- **DeepSeek under a real generation workload** and **speculation under
  concurrent load** are named counterfactuals for Phase 2, where acceptance
  drops (0.493 batched vs 59–72% single-stream) and the
  `max-num-batched-tokens` confound become live.
- **W2 (TP-scaling curves)** and **W3 (FP8 W8A8 compute path)** will synthesize
  from the T9 measurements and the observability contract rather than re-run
  them.

---

## References and Evidence

### Cited references

- **[1]** X. Miao, G. Oliaro, Z. Zhang, X. Cheng, H. Jin, T. Chen, Z. Jia,
  "Towards Efficient Generative Large Language Model Serving: A Survey from
  Algorithms to Systems," *ACM Computing Surveys*, 2025. arXiv:2312.15234.
- **[2]** JarvisLabs, "Speculative decoding in vLLM: faster LLM inference,"
  <https://jarvislabs.ai/blog/speculative-decoding-vllm-faster-llm-inference>.
  Method taxonomy and model-scale trend (T6).
- **[3]** vLLM, "[Bug]: KV cache size log is wrong," issue #40691,
  <https://github.com/vllm-project/vllm/issues/40691> (T3).

### Source thread files

- [T1 — Kimi bring-up](w1/t1-kimi-bringup.md)
- [T2 — Reasoning TTFT](w1/t2-reasoning-ttft.md)
- [T3 — DeepSeek VRAM budget](w1/t3-deepseek-vram-budget.md)
- [T4 — LiteLLM Proxy](w1/t4-litellm-proxy.md) · [T4 deep-research report](w1/T4-deep-research-report.md)
- [T5 — Observability](w1/t5-observability.md)
- [T6 — Eagle3 speculative decoding](w1/t6-eagle3-speculative-decoding.md)
- [T7 — Host directories](w1/t7-host-directories.md)
- [T8 — LiteLLM overhead](w1/t8-litellm-overhead.md)
- [T9 — Bottleneck & NVLink](w1/t9-bottleneck-nvlink.md) · [NVLink decision note (PL)](w1/nvlink-4way-notatka-decyzyjna.md)
- Companion narrative/index: [W1 article](w1-article.md) · [W1 multi-model serving baseline](w1-multi-model-serving-baseline.md)

### Evidence directories and commits

- `results/runs/2026-05-19_kimi-k2-6_stream-debug/` — SSE reasoning-stream captures (T2)
- `results/runs/2026-05-27_w1_evidence/t8_proxy_overhead/` — proxy overhead pilot (T8, commit `5ce0881`)
- `results/runs/2026-06-05_w1_evidence/` — primary W1 evidence freeze (**commit `d0bb634`**): `t1_dep/`, `t3_deepseek_vram/`, `t5_metrics/`, `t6_eagle3/`, `session/`
- `results/runs/2026-06-05_kimi-k2-6_run-04_eagle3-on/`, `…_run-05_eagle3-off-paired/` — Eagle3 A/B (T6; use `-paired`, recovered from `ec3df59`)
- `results/runs/2026-06-05_kimi-k2-6_run-01_t8-proxy/`, `…_run-03_t8-direct/` — proxy vs direct (T8, commits `208e0729`, `277143b`)
- `results/runs/2026-06-05_deepseek-v4-flash_run-01_baseline/`, `…_run-02_baseline/` — DeepSeek single-stream latency baseline, `singlestream_lite_repeated`, n=10 (T3; commit `ec3df59`)
- `results/runs/2026-06-08_w1_evidence_extra/t6_eagle/` — draft-model VRAM capture (T6)
- `results/runs/2026-06-10_w1_article_evidence/` — DCGM counters (`p0_gpu_counters/`), hop attribution (`p2_hop_attribution/`), `prometheus_summary.txt`
- `results/runs/2026-06-11_bottleneck/` (`qwen_tp_curve/`, `kimi_profiler/`), `results/runs/2026-06-11_nvlink_boundary/` — TP scaling, placement doses, floor doses (T9)
- `results/summaries/2026-06-11-qwen-tp-curve.md`, `…-kimi-tp8-profile.md`, `…-nvlink-boundary-verdict.md`

### Tracking issues (`Czyszka/nanoserve-mini`)

#31 (reasoning-TTFT parser fix, commit `cca4022`) · #34 (DCGM/hardware panels,
L2 counterfactuals) · #37 (cross-write-up methodology) · #39 (proxy governance
maturity) · #44 (T8 R1–R8 overhead program) · #48 (T6 methodology
reconciliation) · #49 (observability image pinning) · #50 (T9 close-out +
NVLink decision).
