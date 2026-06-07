# T7 - Why runtime data lives in host directories

## Decision

Store runtime observability state in explicit host bind mounts for Phase 1, not
in Docker named volumes.

## Configuration evidence

The observability compose file (`serving/compose/docker-compose.observability.yml`)
binds Prometheus and Grafana runtime data to machine-visible directories
(lines 11, 34):

```yaml
      - /home/ubuntusrv2/working/nanoserve-observability/prometheus-data:/prometheus
```

```yaml
      - /home/ubuntusrv2/working/nanoserve-observability/grafana-data:/var/lib/grafana
```

The same file keeps configuration and provisioning as repo-visible, read-only
files (lines 10, 35):

```yaml
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
```

This matches the current operational decision in
`docs/operations/agent-state.md`: observability runtime data should use explicit
host paths when local control matters.

## Reasoning

The server is available in short experimental slots, roughly two days per week.
During those slots, observability artifacts need to be easy to inspect and copy
with normal shell tools (`ls`, `cat`, `cp`) without first asking Docker where a
named volume lives.

That matters for this project because W1 is not only about running Prometheus and
Grafana. It also needs evidence that can be triaged after the server slot,
summarized on the laptop, and copied into `results/` when the artifact is small
and sanitized enough to commit. The repository policy keeps config,
documentation, scripts, and small result summaries in Git, while excluding
secrets, model weights, large logs, database dumps, and large benchmark
artifacts. Host directories make that boundary practical: runtime state stays
local by default, and selected snapshots can be copied into `results/` when they
are useful and safe. This is exactly what T5's evidence collection relied on: the
2026-06-05 metric dumps and Grafana dashboard screenshots were inspected on the
server and copied into `results/` for the write-up.

The split also keeps provisioning-as-code in Git. Prometheus config and Grafana
provisioning live under `serving/compose/`, while runtime databases and TSDB data
live under `/home/ubuntusrv2/working/nanoserve-observability/`.

## Trade-off

This decision intentionally favors local control over portability. The compose
file is tied to the server path `/home/ubuntusrv2`, so it is weaker for a
different machine or a clean Docker-only environment. It can also expose UID/GID
and permission problems: Grafana's container runs as a non-root user and
Prometheus as `nobody`, so the host directory must be writable by that UID or the
container fails to start or write. In practice this did not bite here — the
2026-06-05 load test ran and the dashboard populated normally — but it is the
first thing to check when moving these paths to another host.

For Phase 1, that is acceptable because the primary need is fast evidence
collection on one known server. A later portability pass could parameterize
these paths or add a named-volume variant.

## Rejected alternative

| Alternative | Why rejected for W1 |
|---|---|
| Docker named volumes | Operationally clean, but too opaque for short evidence sessions: the data location is discovered through Docker metadata, lifecycle is coupled to Docker volume management, and raw state is harder to inspect, copy into `results/`, or explain in a commit. |

## Evidence

| Claim | Source |
|---|---|
| Prometheus TSDB + Grafana data on explicit host bind mounts | `serving/compose/docker-compose.observability.yml:11,34` |
| Config + provisioning kept repo-visible, read-only | `serving/compose/docker-compose.observability.yml:10,35` |
| Operational decision recorded as shared state | `docs/operations/agent-state.md` ("observability runtime data should use explicit host paths") |
| Realized payoff: T5 evidence triaged on the server and copied into `results/` | `results/runs/2026-06-05_w1_evidence/t5_metrics/`, `…/2026-06-05_grafana_dashboard-max_num_seqs_{1,32}.png` |

> Out of T7 scope but tracked separately: the observability images
> (`grafana/grafana:latest`, `grafana-image-renderer:latest`, `prom/prometheus:v3`)
> are not pinned to exact versions like the serving compose is — tracked in #49.
