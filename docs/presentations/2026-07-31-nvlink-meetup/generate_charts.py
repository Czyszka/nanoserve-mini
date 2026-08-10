"""Wykresy W0-W5 i W7 prezentacji meetupowej — z commitowanych danych repo.

Uruchomienie (laptop, bez dodawania matplotlib do projektu):

    uv run --with matplotlib python docs/presentations/2026-07-31-nvlink-meetup/generate_charts.py

Mapowanie wykres -> slajd -> zrodla danych:
docs/plans/2026-07-31-nvlink-meetup-prezentacja.md (sekcja "Wykresy").
Wartosci, ktorych nie da sie policzyc z plikow (plateau PCIe, GPU-Util 100%),
sa stalymi z notatki decyzyjnej i maja komentarz przy definicji.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUNS = ROOT / "results" / "runs"
OUT = HERE / "charts"

# Paleta referencyjna (skill dataviz, tryb jasny) — sloty w stalej kolejnosci.
BLUE = "#2a78d6"  # slot 1
ORANGE = "#eb6834"  # slot 2
AQUA = "#1baf7a"  # slot 3
BLUE_LIGHT = "#86b6ef"  # sequential step 250 — wariant "przed"
CRITICAL = "#d03b3b"  # status: prog falsyfikacji / limit mocy
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
SURFACE = "#fcfcfb"

plt.rcParams.update(
    {
        "svg.fonttype": "none",
        "font.family": "sans-serif",
        "font.sans-serif": ["Segoe UI", "DejaVu Sans", "Arial", "sans-serif"],
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.titleweight": "600",
        "axes.titlecolor": INK,
        "axes.labelcolor": INK2,
        "axes.edgecolor": BASELINE,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "text.color": INK,
    }
)


def new_ax(width: float = 9.0, height: float = 4.2, grid_axis: str = "y"):
    fig, ax = plt.subplots(figsize=(width, height), dpi=100)
    fig.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    if grid_axis:
        ax.grid(True, axis=grid_axis, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    return fig, ax


def save(fig, name: str) -> None:
    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / name, format="svg", bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    print(f"OK  {name}")


def read_dcgmi(path: Path) -> list[list[tuple[int, float, float, float]]]:
    """Parsuje dump `dcgmi dmon` na probki; wiersz GPU -> (id, power, smact, drama)."""
    samples: list[list[tuple[int, float, float, float]]] = []
    current: list[tuple[int, float, float, float]] = []
    first_id: int | None = None
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) < 6 or parts[0] != "GPU":
            continue
        gpu_id = int(parts[1])
        if first_id is None:
            first_id = gpu_id
        if gpu_id == first_id and current:
            samples.append(current)
            current = []
        try:
            row = (gpu_id, float(parts[2]), float(parts[3]), float(parts[5]))
        except ValueError:  # wiersze N/A
            continue
        current.append(row)
    if current:
        samples.append(current)
    return samples


def bench_throughput(path: Path) -> float:
    return json.loads(path.read_text())["output_throughput"]


# ---------------------------------------------------------------- W0 (slajd 3)
def w0_moc_w_czasie() -> None:
    samples = read_dcgmi(RUNS / "2026-06-11_nvlink_boundary" / "kimi_ramp" / "kimi_c32_dcgmi.txt")
    gpu_ids = sorted({gid for s in samples for gid, *_ in s})
    fig, ax = new_ax()
    for gid in gpu_ids:
        series = [next((p for g, p, *_ in s if g == gid), None) for s in samples]
        xs = [i for i, v in enumerate(series) if v is not None]
        ys = [v for v in series if v is not None]
        ax.plot(xs, ys, color=BLUE, lw=1.4, alpha=0.55)
    ax.axhline(600, color=CRITICAL, lw=1.6, ls="--")
    ax.text(0.5, 588, "limit karty: 600 W", color=CRITICAL, fontsize=10, va="top")
    mid_y = samples[len(samples) // 2][0][1]
    ax.annotate(
        "8 × H200 (osobna linia na kartę)",
        xy=(len(samples) * 0.55, mid_y),
        xytext=(len(samples) * 0.55, 320),
        color=INK2,
        fontsize=10,
        arrowprops={"arrowstyle": "-", "color": BASELINE, "lw": 1.0},
    )
    ax.set_ylim(0, 650)
    ax.set_xlim(0, len(samples) - 1)
    ax.set_xlabel("czas okna benchmarku [s]")
    ax.set_ylabel("pobór mocy na kartę [W]")
    ax.set_title("Pobór mocy pod obciążeniem — Kimi TP=8, c=32 (era PCIe)")
    save(fig, "w0_moc_w_czasie.svg")


# ---------------------------------------------------------------- W1 (slajd 12)
def w1_krzywa_tp() -> None:
    tp1 = bench_throughput(
        RUNS / "2026-06-10_extra" / "p0_gpu_counters" / "bench" / "batched_c64.json"
    )
    curve = ROOT / "results" / "runs" / "2026-06-11_bottleneck" / "qwen_tp_curve"
    values = {1: tp1}
    for tp in (2, 4, 8):
        values[tp] = bench_throughput(curve / f"bench_tp{tp}" / f"tp{tp}_c64.json")
    tps = [1, 2, 4, 8]
    fig, ax = new_ax()
    bars = ax.bar(range(len(tps)), [values[t] for t in tps], width=0.62, color=BLUE)
    for rect, tp in zip(bars, tps, strict=True):
        ax.text(
            rect.get_x() + rect.get_width() / 2,
            rect.get_height() + 25,
            f"{values[tp]:.0f}",
            ha="center",
            color=INK,
            fontsize=11,
            fontweight="600",
        )
    labels = []
    for tp in tps:
        eff = values[tp] / (values[1] * tp) * 100
        eff_txt = f"{eff:.1f}".replace(".", ",") if eff < 10 else f"{eff:.0f}"
        labels.append(f"TP={tp}\nefektywność {eff_txt}%")
    ax.set_xticks(range(len(tps)), labels)
    ax.tick_params(axis="x", labelcolor=INK2)
    ax.set_ylim(0, 1650)
    ax.set_ylabel("przepustowość [tok/s]")
    ax.set_title("Więcej kart = wolniej — Qwen, c=64, era PCIe")
    save(fig, "w1_krzywa_tp.svg")


# ---------------------------------------------------------------- W2 (slajd 5)
def w2_util_vs_liczniki() -> None:
    p0 = RUNS / "2026-06-10_w1_article_evidence" / "p0_gpu_counters"

    def window_stats(name: str) -> tuple[float, float, float]:
        samples = read_dcgmi(p0 / name)
        rows = [r for s in samples for r in s if r[2] >= 0.10]  # filtr probek aktywnych (§6.1)
        power = sum(r[1] for r in rows) / len(rows)
        smact = sum(r[2] for r in rows) / len(rows)
        drama = sum(r[3] for r in rows) / len(rows)
        return power, smact, drama

    p1, s1, d1 = window_stats("single_c1_dcgmi.txt")
    p64, s64, d64 = window_stats("batched_c64_dcgmi.txt")
    cats = [
        "GPU-Util (nvidia-smi)",
        "moc (% limitu 600 W)",
        "SM_ACTIVE",
        "DRAM_ACTIVE",
    ]
    # GPU-Util = 100% w obu oknach: odczyt nvidia-smi (notatka §2), nie licznik DCGM.
    c1_vals = [100.0, p1 / 600 * 100, s1 * 100, d1 * 100]
    c64_vals = [100.0, p64 / 600 * 100, s64 * 100, d64 * 100]
    ys = range(len(cats))
    fig, ax = new_ax(9.0, 3.8, grid_axis="x")
    h = 0.34
    ax.barh([y + h / 2 for y in ys], c1_vals, height=h, color=BLUE, label="c=1")
    ax.barh([y - h / 2 for y in ys], c64_vals, height=h, color=ORANGE, label="c=64")
    for y, v1, v64 in zip(ys, c1_vals, c64_vals, strict=True):
        ax.text(v1 + 1.5, y + h / 2, f"{v1:.0f}%", va="center", color=INK2, fontsize=10)
        ax.text(v64 + 1.5, y - h / 2, f"{v64:.0f}%", va="center", color=INK2, fontsize=10)
    ax.set_yticks(list(ys), cats)
    ax.tick_params(axis="y", labelcolor=INK)
    ax.invert_yaxis()
    ax.set_xlim(0, 112)
    ax.set_xlabel("% czasu / % limitu")
    ax.set_title("100% zajętości, a żaden zasób nie jest nasycony — Kimi TP=8")
    ax.legend(frameon=False, loc="lower right", labelcolor=INK2)
    save(fig, "w2_util_vs_liczniki.svg")


# ---------------------------------------------------------------- W3 (slajd 10)
def w3_profil() -> None:
    # Udzialy z profili czasowych kroku (notatka §6.4; tabela trace w
    # docs/writeups/w1/t9-bottleneck-nvlink.md) — Kimi TP=8, rank 0.
    names = ["przerwy — bez operacji GPU", "komunikacja NCCL", "obliczenia", "inne operacje GPU"]
    colors = [MUTED, ORANGE, BLUE, AQUA]
    rows = [
        ("c=1\njedno zapytanie", [63.0, 22.5, 9.1, 5.6]),
        ("c=16\npod obciążeniem", [10.0, 83.9, 4.6, 1.5]),
    ]
    fig, ax = new_ax(9.0, 3.0, grid_axis="")
    for y, (_, shares) in enumerate(rows):
        left = 0.0
        for share, color in zip(shares, colors, strict=True):
            ax.barh(y, share, left=left, height=0.52, color=color, edgecolor=SURFACE, lw=2)
            if share >= 5:  # ponizej ~5% etykieta nie miesci sie w segmencie
                pct = f"{share:.1f}".replace(".", ",")
                ax.text(left + share / 2, y, f"{pct}%", ha="center", va="center",
                        color=SURFACE, fontsize=11 if share >= 20 else 9)
            left += share
    ax.set_yticks(range(len(rows)), [label for label, _ in rows])
    ax.tick_params(axis="y", labelcolor=INK)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("udział w czasie profilu [%]")
    ax.set_title("Rozkład czasu kroku — Kimi TP=8: pojedyncze zapytanie vs obciążenie")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in colors]
    ax.legend(handles, names, frameon=False, labelcolor=INK2, fontsize=10, ncol=4,
              loc="upper center", bbox_to_anchor=(0.5, -0.24), handlelength=1.2,
              columnspacing=1.6, handletextpad=0.5)
    save(fig, "w3_profil.svg")


# ---------------------------------------------------------------- W4 (slajd 16)
def w4_p2p_busbw() -> None:
    nvl = RUNS / "2026-07-31_nvlink_install" / "nvlink"
    p2p = json.loads((nvl / "p2p_bw.json").read_text())
    intra = max(
        e["uni_GBps"] for e in p2p if e["dst"] - e["src"] < 4 and e["src"] // 4 == e["dst"] // 4
    )
    cross = max(e["uni_GBps"] for e in p2p if e["src"] // 4 != e["dst"] // 4)
    two_islands = json.loads((nvl / "nccl_allreduce.json").read_text())
    ti_vals = [v["busbw_GBps"] for v in two_islands.values()]
    island_txt = (nvl / "nccl_allreduce_island0.txt").read_text()
    isl_vals = [float(m) for m in re.findall(r"busbw\s+([0-9.]+)\s+GB/s", island_txt)]
    # Plateau ruchu all-reduce na PCIe sprzed montazu: pasmo 7,2-7,9 GB/s (notatka §6.3/6.4).
    plateau = 7.9
    items = [
        ("NCCL busbw — 4 karty w wyspie", max(isl_vals), BLUE,
         f"{min(isl_vals):.0f}–{max(isl_vals):.0f} GB/s wg rozmiaru komunikatu"),
        ("P2P — para kart w wyspie", intra, BLUE, f"{intra:.1f} GB/s".replace(".", ",")),
        ("NCCL busbw — grupa 2+2 przez wyspy", max(ti_vals), ORANGE,
         f"{min(ti_vals):.1f}–{max(ti_vals):.1f} GB/s".replace(".", ",")),
        ("P2P — para między wyspami", cross, ORANGE, f"{cross:.1f} GB/s".replace(".", ",")),
        ("all-reduce na PCIe (przed montażem)", plateau, MUTED,
         "plateau 7,2–7,9 GB/s"),
    ]
    fig, ax = new_ax(9.0, 3.9, grid_axis="x")
    ys = range(len(items))
    ax.barh(ys, [v for _, v, *_ in items], height=0.55, color=[c for *_, c, _ in items])
    for y, (_, val, _, label) in zip(ys, items, strict=True):
        ax.text(val * 1.12, y, label, va="center", color=INK2, fontsize=10)
    ax.set_yticks(list(ys), [name for name, *_ in items])
    ax.tick_params(axis="y", labelcolor=INK)
    ax.invert_yaxis()
    ax.set_xscale("log")
    ax.set_xlim(1, 3000)
    ax.set_xticks([1, 10, 100, 1000], ["1", "10", "100", "1000"])
    ax.set_xlabel("przepustowość [GB/s, skala log]")
    ax.set_title("Warstwa mikro po montażu — wyspa vs między wyspami vs era PCIe")
    save(fig, "w4_p2p_busbw.svg")


# ---------------------------------------------------------------- W5 (slajd 17)
def w5_przed_po() -> None:
    qwen_before = bench_throughput(
        RUNS / "2026-06-11_bottleneck" / "qwen_tp_curve" / "bench_tp4" / "tp4_c64.json"
    )
    qwen_after = bench_throughput(
        RUNS / "2026-07-31_nvlink_install" / "qwen" / "bench_tp4_nvlink" / "tp4_nvlink_c64.json"
    )
    kimi_before = bench_throughput(
        RUNS / "2026-06-11_nvlink_boundary" / "kimi_ramp" / "bench" / "kimi_c32.json"
    )
    kimi_after = bench_throughput(
        RUNS / "2026-07-31_nvlink_install" / "kimi" / "bench" / "kimi_c32.json"
    )
    # Progi falsyfikacji: plan instalacji 07-31 §1 (pre-rejestrowane). Linia predykcji =
    # model S_nvlink ze slajdu 14 (1,84x na 680 tok/s; 2,18x na 285 tok/s).
    panels = [
        ("Qwen TP=4, c=64", qwen_before, qwen_after, 1250, 850),
        ("Kimi TP=8, c=32", kimi_before, kimi_after, 620, 400),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 4.0), dpi=100)
    fig.set_facecolor(SURFACE)
    for ax, (title, before, after, pred, threshold) in zip(axes, panels, strict=True):
        ax.set_facecolor(SURFACE)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.grid(True, axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        bars = ax.bar([0, 1], [before, after], width=0.55, color=[BLUE_LIGHT, BLUE])
        for rect, val in zip(bars, (before, after), strict=True):
            ax.text(rect.get_x() + rect.get_width() / 2, rect.get_height() + 28,
                    f"{val:.0f}", ha="center", color=INK, fontsize=11, fontweight="600")
        ax.axhline(pred, color=INK2, lw=1.4, ls="--")
        ax.text(2.55, pred + 12, f"predykcja S_nvlink\n~{pred}", ha="right", va="bottom",
                color=INK2, fontsize=9.5)
        ax.axhline(threshold, color=CRITICAL, lw=1.4, ls=":")
        ax.text(2.55, threshold + 12, f"próg falsyfikacji {threshold}", ha="right",
                va="bottom", color=CRITICAL, fontsize=9.5)
        gain = after / before
        ax.set_xticks([0, 1], ["przed\n(PCIe)", f"po NVLink\n({gain:.2f}×)".replace(".", ",")])
        ax.tick_params(axis="x", labelcolor=INK2, labelsize=10)
        ax.set_xlim(-0.55, 2.6)
        ax.set_ylim(0, max(after, pred) * 1.18)
        ax.set_title(title, fontsize=12)
    axes[0].set_ylabel("przepustowość [tok/s]")
    fig.suptitle("Te same benchmarki przed i po montażu NVLink", fontsize=13,
                 fontweight="600", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save(fig, "w5_przed_po.svg")


# ---------------------------------------------------------------- W7 (slajd 7)
def w7_dram_active() -> None:
    p0 = RUNS / "2026-06-10_w1_article_evidence" / "p0_gpu_counters"
    fig, ax = new_ax()
    for name, color, label in [
        ("single_c1_dcgmi.txt", BLUE, "c=1"),
        ("batched_c64_dcgmi.txt", ORANGE, "c=64"),
    ]:
        samples = read_dcgmi(p0 / name)
        means = [sum(r[3] for r in s) / len(s) for s in samples if s]
        active = [i for i, v in enumerate(means) if v >= 0.01]
        if active:  # przytnij bezczynny ogon po zakonczeniu benchu
            means = means[: min(active[-1] + 5, len(means))]
        ax.plot(range(len(means)), means, color=color, lw=2.0, label=label)
    ax.axhspan(0.70, 0.90, color=CRITICAL, alpha=0.10)
    ax.text(2, 0.80, "oczekiwane, gdyby krok ograniczała pamięć HBM (0,70–0,90)",
            color=CRITICAL, fontsize=10, va="center")
    ax.set_ylim(0, 1.0)
    ax.set_xlabel("czas okna pomiaru [s]")
    ax.set_ylabel("DRAM_ACTIVE (0–1)")
    ax.set_title("Aktywność interfejsu pamięci HBM — Kimi TP=8 (średnia z 8 GPU)")
    ax.legend(frameon=False, loc="center right", labelcolor=INK2)
    save(fig, "w7_dram_active.svg")


if __name__ == "__main__":
    w0_moc_w_czasie()
    w1_krzywa_tp()
    w2_util_vs_liczniki()
    w3_profil()
    w4_p2p_busbw()
    w5_przed_po()
    w7_dram_active()
