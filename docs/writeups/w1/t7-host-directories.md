# T7 — Why runtime data lives in host directories

<!-- TODO: justification segment. Host directories vs Docker named
volumes for observability runtime data; local-control rationale. -->

## Planned shape

Mode: justification.

## Decision

Store runtime observability data in host directories for Phase 1 instead
of hiding it in Docker named volumes.

## Reasoning to develop

Host directories make the benchmark and observability artifacts easier to
inspect, back up, copy into `results/`, and attach to write-ups. For W1,
local control and reproducibility matter more than volume abstraction.

## Rejected alternative

| Alternative | Why rejected for W1 |
|---|---|
| Docker named volumes | Operationally clean, but less transparent when collecting evidence from a short server session. |

## Evidence / examples to include

- compose paths,
- Prometheus/Grafana runtime directories,
- artifact collection path,
- backup or cleanup command.
