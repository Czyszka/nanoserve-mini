# 2026-05-27 W1 evidence server session

## Scope

This session was intended to collect W1 evidence for:

- T8 — LiteLLM Proxy overhead, paired direct/proxy measurements for Kimi and DeepSeek.
- T3 — DeepSeek VRAM cap justification.
- T6 — Kimi Eagle3 ON/OFF comparison.
- T1 — Kimi DEP startup failure capture.
- T5 — Prometheus/Grafana validation as stretch only.

## Completed

### T8 — proxy overhead

Completed for both models:

- Kimi direct `:8000` vs LiteLLM Proxy `:4000`, 10 paired A/B measurements.
- DeepSeek direct `:8004` vs LiteLLM Proxy `:4000`, 10 paired A/B measurements.
- Post-run LiteLLM metrics snapshot captured in `t8_proxy_overhead/litellm_metrics_post.txt`.

Artifacts:

- `t8_proxy_overhead/kimi_1_A_direct.json` ... `kimi_10_A_direct.json`
- `t8_proxy_overhead/kimi_1_B_proxy.json` ... `kimi_10_B_proxy.json`
- `t8_proxy_overhead/ds_1_A_direct.json` ... `ds_10_A_direct.json`
- `t8_proxy_overhead/ds_1_B_proxy.json` ... `ds_10_B_proxy.json`
- `t8_proxy_overhead/litellm_metrics_post.txt`

### T3 — DeepSeek VRAM baseline only

Captured only one DeepSeek baseline run/log:

- `t3_deepseek_vram/log_cap020_baseline.txt`
- `t3_deepseek_vram/ttft_cap020.json`

Important caveat: despite the `cap020` filename, the committed vLLM log shows `gpu_memory_utilization: 0.25`. Treat these artifacts as a `0.25` baseline unless the runtime environment proves otherwise. The full 0.15/0.25 sweep was not completed.

### Session start snapshot

Captured:

- `session/start_commit.txt`
- `session/docker_ps_start.txt`
- `session/nvidia_smi_start.txt`

The start snapshot showed:

- `vllm` healthy on `:8000`.
- `litellm-proxy` healthy on `:4000`.
- `prometheus` and `grafana` running.
- `open-webui` unhealthy.
- `vllm-small` still in `health: starting` at snapshot time.

## Not completed

- T3 full sweep at `DEEPSEEK_GPU_MEM_UTIL=0.15` and `0.25` was not completed as planned.
- T6 Kimi Eagle3 ON/OFF benchmark was not completed.
- T1 Kimi DEP startup failure capture was not completed.
- T5 dashboard/Prometheus validation was not completed beyond the LiteLLM metrics snapshot.
- End-of-session snapshots (`docker_ps_end.txt`, `nvidia_smi_end.txt`) were not captured in this commit.

## Repository hygiene notes

- The run directory was committed as `results/runs/2026-05-27_w1_ewidence` with a typo in `ewidence`.
- Prefer renaming it to `results/runs/2026-05-27_w1_evidence` in a dedicated cleanup commit from a local git checkout, because this is a many-file path move.
- The commit also added older `2026-05-19_deepseek-v4-flash_run-03..06` benchmark artifacts. Treat them as recovered historical artifacts, not as evidence produced during the 2026-05-27 server session.

## Next recommended work

1. Do a repo hygiene commit from local git:
   - rename `2026-05-27_w1_ewidence` to `2026-05-27_w1_evidence`,
   - update any references if needed.
2. Analyze T8 paired direct/proxy deltas on the laptop.
3. Re-run the missing T3/T1/T6 pieces in a separate server slot:
   - T3: explicit `0.15`, `0.20`, `0.25` with file names matching actual runtime caps,
   - T1: DEP startup failure capture,
   - T6: Kimi Eagle3 ON/OFF benchmark.
4. Only after T8/T3/T1/T6 evidence is coherent, continue the W1 write-up.
