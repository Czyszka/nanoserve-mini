# Paper note: Towards Efficient Generative Large Language Model Serving: A Survey from Algorithms to Systems

- **Status:** done
- **Date read:** 2026-05-03
- **Authors / venue / year:** Xupeng Miao, Gabriele Oliaro, Zhihao Zhang, Xinhao Cheng, Hongyi Jin, Tianqi Chen, Zhihao Jia; ACM Computing Surveys / arXiv:2312.15234v2; 2025
- **URL / DOI / local PDF:** https://arxiv.org/abs/2312.15234, https://doi.org/10.1145/3754448, local ignored PDF at `docs/papers/Efficient LLM Serving Survey.pdf`
- **Project phase:** Phase 1
- **Why now:** It gives the Phase 1 mental model for vLLM serving, metrics, memory pressure, scheduling, and benchmark design before the first GPU-server measurements.
- **Verdict:** must-read

## One-paragraph summary

This survey maps efficient generative LLM serving from algorithmic techniques to system-level serving engines. For `nanoserve-mini`, the useful part is not the full catalog of techniques, but the serving stack model: autoregressive generation splits into an initial prompt-processing phase and an incremental decode loop; throughput and latency are shaped by batching, KV cache memory management, request scheduling, and attention/kernel choices; and credible benchmark claims require controls for model, hardware, workload, scheduling overhead, network overhead, and generated output. The paper does not give a new benchmark result for us to reproduce; it gives the taxonomy that says what our first vLLM baseline must record.

## Pass 1: qualification

### Five Cs

- **Category:** survey / systems / LLM serving.
- **Context:** Connects vLLM/PagedAttention, Orca-style iteration-level scheduling, FasterTransformer, TensorRT-LLM, TGI, FlexGen, FlexFlow-Serve, LightLLM, MLC-LLM, low-bit quantization, parallelism, KV cache management, scheduling, and kernel optimization.
- **Correctness:** The assumptions fit `nanoserve-mini`: GPU-based serving, autoregressive decoding, variable prompt/output lengths, memory pressure from KV cache, and the latency-throughput trade-off. The survey is broad, so it should guide what to measure rather than settle any performance claim by itself.
- **Contributions:** A taxonomy of algorithmic innovations and system optimizations for LLM serving; a comparison of representative open-source GPU serving systems; a benchmark-methodology discussion; and future directions for serving research.
- **Clarity:** Clear enough to reconstruct the serving stack and taxonomy. It is less useful as evidence for numeric speedups because it mainly summarizes other systems.

### Decision after pass 1

- **Next action:** pass 3 now
- **Reason:** This is foundational Phase 1 context for interpreting vLLM metrics and designing the first benchmark records.

## Pass 2: argument and evidence

### Problem

Generative LLM serving must deliver low latency and high throughput despite large model sizes, autoregressive token generation, variable request lengths, unpredictable output lengths, and high GPU-memory pressure. The central performance problem is not one kernel or one scheduling policy in isolation; it is the interaction between the serving engine, request workload, KV cache, batching policy, and hardware backend.

### Method

The survey organizes the field into two large groups:

- algorithmic innovations: decoding algorithms, architecture design, and model compression;
- system optimizations: low-bit quantization, parallel computation, memory management, request scheduling, and kernel optimization.

For `nanoserve-mini`, the highest-value sections are memory management, request scheduling, software frameworks, and benchmarks. These sections explain why vLLM's PagedAttention matters, why continuous/iteration-level batching matters, and why TTFT and TPOT need to be treated separately.

### Evidence

- **Baselines:** The survey compares representative serving systems conceptually, including FasterTransformer, FlexFlow-Serve, vLLM, FlexGen, TGI, DeepSpeed-Inference, ZeRO-Inference, LightLLM, MLC-LLM, and TensorRT-LLM. It does not run a new controlled benchmark in the note source.
- **Workload:** Exact prompt lengths, output lengths, concurrency, and arrival processes are not specified in note source for a new experiment. The benchmark section says prior work often uses real-world traces such as BurstGPT and Azure traces, and warns that limited setting combinations are not enough for credible conclusions.
- **Hardware/software:** The survey focuses primarily on GPU-based LLM serving systems. Exact hardware/software settings for a new evaluation are not specified in note source.
- **Metrics:** Latency, response time, memory footprint, throughput, scalability, cost-efficiency, utilization, TTFT, TPOT, and output-sequence-sensitive end-to-end latency.
- **Strongest result:** not specified in note source. The paper is a survey and does not provide one new result for `nanoserve-mini` to reproduce.
- **Weakest result or missing evidence:** The benchmark section explicitly notes that the community lacks a convincing standard benchmark covering all important factors, and that fairness is hard because model configuration, hardware, request load, scheduling overhead, network overhead, and output alignment can all change conclusions.

### Assumptions

- Generative LLM serving is dominated by autoregressive decoding, where each new token depends on the previous context.
- GPU memory and HBM bandwidth matter as much as raw FLOPS for serving behavior.
- Workload shape matters: prompt length, output length, request arrival pattern, and concurrency can change which optimization wins.
- System techniques can interact badly: a memory-saving method can increase latency, and a batching method can improve throughput while hurting per-request responsiveness.

## Pass 3: reconstruction

Use this section only for papers that matter enough to deeply understand.

### Reconstructed mechanism

Conceptually, an LLM serving engine is a loop around a stateful autoregressive model:

1. A request arrives through an API layer with prompt, decoding parameters, and model choice.
2. The scheduler admits it into a batch according to capacity, fairness, priority, and memory constraints.
3. The prefill phase processes all prompt tokens in parallel and creates KV cache entries for the prompt context.
4. The decode phase iterates token by token. Each step reads the growing KV cache, computes attention and FFN work, samples/selects the next token, appends it to the sequence, and updates cache state.
5. The KV cache manager allocates, reuses, evicts, offloads, or frees memory as requests start and finish. vLLM's important idea in this taxonomy is block-level KV cache management through PagedAttention, which reduces wasted contiguous allocation and enables larger effective batches.
6. The batching policy decides whether and how prefill and decode work share GPU time. Orca-style iteration-level scheduling and vLLM continuous batching exist because request-level batching handles variable output length poorly.
7. Observability and benchmark records must sit around the whole loop: TTFT captures prompt admission plus prefill and first decode response; TPOT captures incremental decode behavior; E2E includes all emitted tokens; throughput is only meaningful with the workload and controls attached.

The serving taxonomy for this repo can be reduced to:

- algorithmic changes that alter generation behavior or model shape: out of scope for Phase 1 except as background;
- memory and scheduling changes that affect vLLM behavior: measure now;
- kernel choices and attention backends: observe now, profile later;
- benchmark methodology: implement immediately in result schemas and scripts.

### Hidden assumptions and failure modes

- A survey can hide workload-specific failures: a technique that improves high-load throughput can be harmful for short interactive requests.
- "Latency" is ambiguous unless split into TTFT, TPOT, and E2E latency with prompt/output lengths recorded.
- KV cache optimizations are not free. Fine-grained or fragmented cache management can reduce memory waste but add overhead.
- Comparing engines without aligning model, dtype, output length, scheduling policy, hardware, and network/API path can produce misleading conclusions.
- Some surveyed directions are beyond `nanoserve-mini` scope even if they are technically relevant: speculative decoding, disaggregated serving, multi-GPU parallelism, TensorRT-LLM integration, and heavy quantization work.

### What I would reproduce

Do not reproduce the survey. Reproduce one observable symptom from the taxonomy: prompt length should mostly affect TTFT through prefill, while output length should mostly affect E2E latency and future TPOT through decode. With the current repo, this starts as a sequential vLLM benchmark using fixed server controls and different prompt/output shapes. Later, add `/metrics` scraping to connect request-level timings to vLLM scheduler and KV cache metrics.

## LLM inference lens

### Which phase does it optimize?

- [x] prefill
- [x] decode
- [x] both
- [x] scheduling around them
- [x] memory around them
- [x] kernel-level operation
- [x] observability / measurement methodology

### Primary optimization target

- [x] lower TTFT
- [x] lower TPOT
- [x] higher throughput
- [x] lower memory
- [x] lower cost
- [x] better SLO/tail latency
- [x] better utilization

### Bottleneck claimed by authors

The survey does not claim a single universal bottleneck. It frames efficient serving as a multi-bottleneck systems problem: large model size, autoregressive sequential decode, KV cache memory footprint and bandwidth, variable sequence lengths, request scheduling under unknown output lengths, and GPU utilization. For Phase 1, the key bottleneck candidates to measure are prefill cost, decode cost, and KV-cache-driven batching limits.

### Bottleneck evidence

The paper provides taxonomy-level evidence and examples from existing systems, not a new controlled measurement. Concrete examples in the note source include: vLLM using block-level KV cache management/PagedAttention to enlarge batch size and throughput; Orca introducing iteration-level scheduling for variable generative outputs; Sarathi-Serve chunking prefill to reduce pipeline bubbles; and the benchmark section warning that limited combinations of model, hardware, and request load are not credible. Numeric speedups for these systems are not specified in note source.

### Trade-off

What do they sacrifice?

- [x] quality
- [x] latency
- [x] throughput
- [x] memory
- [x] system simplicity
- [x] fairness
- [x] infrastructure cost
- [x] other: benchmark comparability

The trade-off is contextual. Algorithmic methods such as quantization, pruning, attention simplification, early exit, and cascade inference can trade quality or semantics for efficiency. System methods such as batching, KV cache paging, offloading, preemption, and disaggregation preserve model semantics more directly but trade latency, throughput, memory efficiency, fairness, and implementation complexity against one another.

### Interaction with vLLM

Is this:

- [x] used by vLLM
- [ ] alternative to vLLM
- [ ] layer above vLLM
- [x] something we do not implement, but measure symptoms of
- [ ] unclear / requires follow-up

The survey places vLLM as a representative GPU serving framework whose core feature is PagedAttention/block-level KV cache management for larger batches and higher throughput. For this repo, vLLM is the baseline, not a paper to reimplement. We should measure the symptoms the survey identifies: TTFT, E2E latency, future TPOT, throughput, scheduler state, running/waiting requests, and GPU/KV cache metrics.

### Experiment I could run

What minimal experiment can I run in `nanoserve-mini`?

- **Hypothesis:** Longer prompts increase TTFT because prefill has more prompt tokens to process, while longer generated outputs mainly increase E2E latency and future TPOT-sensitive decode time. Higher cache pressure or larger batches should show up later in vLLM metrics as scheduler and KV cache changes.
- **Script or harness:** `scripts/request_once.py` for smoke validation, `scripts/measure_ttft_once.py` for one streaming TTFT/E2E record, `scripts/run_sequential_benchmark.py` for repeated sequential TTFT/E2E p50/p95, future vLLM `/metrics` scrape for scheduler/KV cache, future workload/cache experiment for prompt-prefix reuse.
- **Workload:** Use the model selected during the first server session. Run the same decoding parameters across short, medium, and long prompts with fixed `max_tokens`, then separately vary `max_tokens` while holding the prompt fixed. Concurrency is not in the current harness, so it belongs to a later benchmark extension.
- **Metrics:** Current repo: TTFT, E2E latency, chunks received, output chars, p50/p95 across sequential runs. Future repo: TPOT, request throughput, output token throughput, p50/p95/p99, GPU memory usage, vLLM GPU cache usage, running/waiting requests, and prefix cache hit rate when the cache experiment exists.
- **Controls:** model, base URL, dtype, quantization, GPU model, vLLM version, max model length, max number of sequences, max number of batched tokens, decoding parameters, warmup runs, measured runs, workload label, git commit, and server environment snapshot.
- **Expected signal:** A valid first signal is not a speedup claim. It is a clean separation of TTFT/E2E behavior by prompt and output shape, with enough controls recorded to repeat the measurement and later explain it using vLLM metrics.

## Nanoserve-mini mapping

- **vLLM baseline relevance:** Treat vLLM as the reference serving engine. The survey explains why PagedAttention, continuous batching, and KV cache metrics are central to interpreting its behavior.
- **Observability relevance:** Add or scrape metrics that expose scheduler state, running/waiting requests, GPU memory, KV cache usage, request throughput, and token throughput. TTFT/E2E from the client side should be correlated with server-side metrics later.
- **Benchmark harness relevance:** Every result needs model, hardware, dtype, request shape, decoding parameters, server args, warmups, measured runs, and output-length context. A benchmark without workload controls is not useful.
- **Workload/cache relevance:** Prompt length, output length, mixed workloads, and prefix reuse are first-class variables. Cache experiments should measure symptoms of prefix reuse and KV pressure rather than implementing a custom cache.
- **Kernel/profiling relevance:** Later Triton/profiling work should focus on memory access, attention/FFN/operator costs, HBM pressure, and prefill/decode differences, not on replacing vLLM attention kernels.
- **Out-of-scope boundary:** Do not add a custom inference engine, TensorRT-LLM integration, SGLang integration, multi-GPU parallelism, FP8, speculative decoding, disaggregated serving, or custom KV cache implementation for this Phase 1 note.

## Follow-up references

- PagedAttention / vLLM - required to understand the baseline engine and KV cache metrics.
- Orca - required to understand iteration-level scheduling and why naive request-level batching is weak for generative workloads.
- Efficiently Scaling Transformer Inference - useful for roofline and cost-model thinking around transformer inference.
- Sarathi-Serve - useful later for TTFT vs TPOT and chunked prefill trade-offs.
- DistServe - useful later as background for prefill/decode disaggregation, but out of scope for implementation.

## Final takeaway

This paper changes the work this week by turning the first vLLM run from a smoke test into a controlled measurement exercise. The next benchmark records should explicitly separate TTFT from E2E latency, preserve workload and server controls, and prepare for future TPOT and vLLM `/metrics` collection. The project should measure vLLM behavior before considering any serving optimization.
