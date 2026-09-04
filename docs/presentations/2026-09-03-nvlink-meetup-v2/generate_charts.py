"""Wykresy W0'-W3' i W5a/W5b prezentacji meetupowej v2 — z commitowanych danych repo.

Uruchomienie (laptop, bez dodawania matplotlib do projektu):

    uv run --with matplotlib python docs/presentations/2026-09-03-nvlink-meetup-v2/generate_charts.py

Mapowanie wykres -> slajd -> zrodla: tresc-slajdow-v2.md (sekcje "Zrodlo").
Wartosci, ktorych nie da sie policzyc z plikow (GPU-Util 100%, udzialy
z profilu, liczniki DCGM z podsumowan), sa stalymi z komentarzem przy definicji.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUNS = ROOT / "results" / "runs"
OUT = HERE / "charts"

# Paleta (decyzje 2026-09-03): niebieski = Kimi, ciemnozielony = Qwen,
# czerwony przerywany = limit mocy; skladniki kroku: obliczenia ciemnoszary,
# komunikacja pomaranczowy, przerwy jasnoszary; "przed" = szary.
BLUE = "#2a78d6"
GREEN = "#1e7d4f"
ORANGE = "#eb6834"
CRITICAL = "#d03b3b"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
SURFACE = "#fcfcfb"
BEFORE = "#b9b8b0"

plt.rcParams.update(
    {
        "svg.fonttype": "none",
        "font.family": "sans-serif",
        "font.sans-serif": ["Segoe UI", "DejaVu Sans", "Arial", "sans-serif"],
        "font.size": 12,
        "axes.titlesize": 14,
        "axes.titleweight": "600",
        "axes.titlecolor": INK,
        "axes.labelcolor": INK2,
        "axes.edgecolor": BASELINE,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "text.color": INK,
        "hatch.linewidth": 1.2,
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
    # matplotlib zostawia spacje na koncach linii w sciezkach -> git diff --check
    path = OUT / name
    path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
    print(f"OK  {name}")


def pl(x: float, nd: int = 0) -> str:
    return f"{x:.{nd}f}".replace(".", ",")


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


def bar_labels(ax, bars, values, dy, fmt=lambda v: f"{v:.0f}", size=12):
    for rect, val in zip(bars, values, strict=True):
        ax.text(rect.get_x() + rect.get_width() / 2, rect.get_height() + dy, fmt(val),
                ha="center", va="bottom", color=INK, fontsize=size, fontweight="600")


# ---------------------------------------------------------------- W0' (slajd 2)
def w0_moc_w_czasie() -> None:
    kimi = read_dcgmi(RUNS / "2026-06-11_nvlink_boundary" / "kimi_ramp" / "kimi_c32_dcgmi.txt")
    qwen = read_dcgmi(RUNS / "2026-09-04_qwen_tp1_okno_mocy" / "qwen" / "tp1_c64_long_dcgmi.txt")
    n = len(kimi)
    fig, ax = new_ax(9.0, 4.0)
    gpu_ids = sorted({gid for s in kimi for gid, *_ in s})
    for gid in gpu_ids:
        series = [next((p for g, p, *_ in s if g == gid), None) for s in kimi]
        xs = [i for i, v in enumerate(series) if v is not None]
        ys = [v for v in series if v is not None]
        ax.plot(xs, ys, color=BLUE, lw=1.3, alpha=0.6)
    # Qwen TP1: GPU0, tylko aktywna czesc okna (moc > 300 W), przycieta do dlugosci
    # okna Kimi. Sesja 2026-09-04: 2400 promptow SWE c=64 -> 307 s pracy (wczesniej 81 s).
    q = [s[0][1] for s in qwen if s and s[0][0] == 0]
    active = [i for i, v in enumerate(q) if v > 300]
    q = q[active[0]: active[-1] + 1][:n] if active else q[:n]
    ax.plot(range(len(q)), q, color=GREEN, lw=2.2)
    ax.axhline(600, color=CRITICAL, lw=1.6, ls="--")
    ax.text(1, 610, "limit karty: 600 W", color=CRITICAL, fontsize=11, va="bottom")
    ax.text(n * 0.99, max(q) * 0.93 if q else 500, "Qwen - 1 x H200", color=GREEN,
            fontsize=12, fontweight="600", ha="right", va="top")
    ax.text(n * 0.99, 268, "Kimi - 8 x H200, po jednej linii na kartę", color=BLUE,
            fontsize=12, fontweight="600", ha="right", va="bottom")
    ax.set_ylim(0, 680)
    ax.set_xlim(0, n - 1)
    ax.set_xlabel("czas okna benchmarku [s]")
    ax.set_ylabel("pobór mocy na kartę [W]")
    ax.set_title("Pobór mocy pod pełnym obciążeniem")
    save(fig, "w0_moc_w_czasie.svg")


# ---------------------------------------------------------------- W1' (slajd 3)
def w1_krzywa_tp() -> None:
    tp1 = bench_throughput(RUNS / "2026-06-10_extra" / "p0_gpu_counters" / "bench" / "batched_c64.json")
    curve = RUNS / "2026-06-11_bottleneck" / "qwen_tp_curve"
    values = {1: tp1}
    for tp in (2, 4, 8):
        values[tp] = bench_throughput(curve / f"bench_tp{tp}" / f"tp{tp}_c64.json")
    tps = [1, 2, 4, 8]
    fig, ax = new_ax(8.4, 4.0)
    bars = ax.bar(range(4), [values[t] for t in tps], width=0.6, color=GREEN)
    bar_labels(ax, bars, [values[t] for t in tps], 20, size=14)
    ax.set_xticks(range(4), ["1 karta\nTP=1", "2 karty\nTP=2", "4 karty\nTP=4", "8 kart\nTP=8"])
    ax.tick_params(axis="x", labelcolor=INK, labelsize=13)
    ax.set_ylim(0, 1650)
    ax.set_ylabel("tokeny/s łącznie")
    ax.set_title("Qwen - zapytania od 64 użytkowników naraz")
    save(fig, "w1_krzywa_tp.svg")


# ---------------------------------------------------------------- W2' (slajd 4)
def w2_zasoby() -> None:
    # Liczby czerwcowe z podsumowan (decyzja 2026-09-03; zrodla w tresc-slajdow-v2.md, slajd 4):
    # GPU-Util 100% = odczyt nvidia-smi; moc = % limitu 600 W; SM_ACTIVE; DRAM_ACTIVE.
    # PCIe: sredni odbior (RX) w GB/s / 64 GB/s (PCIe 5.0 x16, jeden kierunek):
    # Qwen TP1 0,07; Qwen TP8 7,18 (qwen-tp-curve, czerwiec); Kimi 8,0 (kimi_c32_dcgmi, okno stabilne).
    cats = ["GPU-Util\n(nvidia-smi)", "pobór mocy\n(z limitu 600 W)",
            "jednostki liczące (SM)\n% czasu aktywne", "pamięć HBM\n% czasu aktywna",
            "łącze PCIe\n% przepustowości"]
    series = [
        ("Qwen, 1 karta", [100, 73, 67, 39, 0], GREEN, True),
        ("Qwen, 8 kart", [100, 19, 5, 3, 11], GREEN, False),
        ("Kimi, 8 kart", [100, 30, 20, 8, 13], BLUE, False),
    ]
    fig, ax = new_ax(11.4, 4.2, grid_axis="")
    w = 0.26
    for k, (name, vals, color, hatched) in enumerate(series):
        xs = [i + (k - 1) * w for i in range(5)]
        if hatched:
            bars = ax.bar(xs, vals, width=w - 0.03, facecolor=SURFACE, edgecolor=color,
                          hatch="//", lw=1.5, label=name)
        else:
            bars = ax.bar(xs, vals, width=w - 0.03, color=color, label=name)
        bar_labels(ax, bars, vals, 1.5, fmt=lambda v: f"{v:.0f}%", size=9)
    ax.set_xticks(range(5), cats)
    ax.tick_params(axis="x", labelcolor=INK, labelsize=12)
    ax.set_ylim(0, 118)
    ax.set_yticks([0, 25, 50, 75, 100], ["0", "25", "50", "75", "100%"])
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.12), ncol=3,
              labelcolor=INK2, fontsize=12, handlelength=1.4)
    save(fig, "w2_zasoby.svg")


# ---------------------------------------------------------------- W3' (slajd 6)
def w3_profil() -> None:
    # Udzialy z profilu torch: Kimi TP=8 pod obciazeniem (c=16, 06-11), rank 0:
    # przerwy 10,0 / komunikacja 83,9 / obliczenia 4,6 / inne 1,5 (verdict K2).
    shares = [("przerwy (silnik na CPU)", 10.0, BASELINE, INK),
              ("komunikacja", 83.9, ORANGE, SURFACE),
              ("obliczenia", 4.6, BLUE, SURFACE),
              ("inne", 1.5, MUTED, SURFACE)]
    fig, ax = new_ax(9.4, 2.4, grid_axis="")
    left = 0.0
    for name, share, color, txt in shares:
        ax.barh(0, share, left=left, height=0.6, color=color, edgecolor=SURFACE, lw=2)
        if share >= 4:
            label = f"{name}\n{pl(round(share))}%" if share > 15 else (f"{pl(round(share))}%" if share >= 8 else "")
            ax.text(left + share / 2, 0, label, ha="center", va="center", color=txt,
                    fontsize=13 if share > 15 else 12, fontweight="600")
        left += share
    ax.annotate("", xy=(5, -0.3), xytext=(5, -0.5), arrowprops={"arrowstyle": "-", "color": INK2})
    ax.text(5, -0.52, "przerwy (silnik na CPU)", color=INK2, fontsize=11, ha="center", va="top")
    ax.annotate("", xy=(96.2, -0.3), xytext=(93.0, -0.5), arrowprops={"arrowstyle": "-", "color": INK2})
    ax.text(93.0, -0.52, "obliczenia 5%", color=INK2, fontsize=11, ha="right", va="top")
    ax.annotate("", xy=(99.3, -0.3), xytext=(99.3, -0.78), arrowprops={"arrowstyle": "-", "color": INK2})
    ax.text(99.3, -0.8, "inne", color=INK2, fontsize=11, ha="center", va="top")
    ax.set_yticks([])
    ax.set_xlim(0, 100)
    ax.set_ylim(-1.05, 0.5)
    ax.set_xticks([0, 25, 50, 75, 100], ["0", "25", "50", "75", "100% czasu pomiaru"])
    for side in ("left",):
        ax.spines[side].set_visible(False)
    ax.set_title("Kimi, 8 kart, serwer pod obciążeniem", loc="left")
    save(fig, "w3_profil.svg")


# ---------------------------------------------------------------- W5a / W5b (slajd 10)
def _przed_po(ax, groups, color_after, ymax, title):
    """groups: [(label, before, after)]; przed = szary, po = kolor modelu."""
    x = 0.0
    ticks, labels = [], []
    for label, before, after in groups:
        b = ax.bar([x, x + 0.7], [before, after], width=0.62, color=[BEFORE, color_after])
        bar_labels(ax, b, [before, after], ymax * 0.015, size=13)
        ticks += [x, x + 0.7]
        labels += ["przed", "po"]
        ax.text(x + 0.35, -ymax * 0.2, label, ha="center", va="top", color=INK, fontsize=13,
                fontweight="600")
        x += 2.0
    ax.set_xticks(ticks, labels)
    ax.tick_params(axis="x", labelcolor=INK2, labelsize=12, length=0)
    ax.set_xlim(-0.6, x - 0.7)
    ax.set_ylim(0, ymax)
    ax.set_ylabel("tokeny/s łącznie")
    ax.set_title(title, loc="left")


def w5a_qwen() -> None:
    q = RUNS / "2026-08-31_latencja_dostepu" / "qwen"
    curve = RUNS / "2026-06-11_bottleneck" / "qwen_tp_curve"
    tp4_before = bench_throughput(curve / "bench_tp4" / "tp4_c64.json")
    tp4_after = bench_throughput(q / "bench_tp4isl" / "tp4isl_c64.json")
    fig, ax = new_ax(4.6, 3.3)
    _przed_po(ax, [("4 karty", tp4_before, tp4_after)], GREEN, 2500,
              "Qwen - 64 użytkowników naraz")
    save(fig, "w5a_qwen.svg")


def w5b_kimi() -> None:
    before = bench_throughput(RUNS / "2026-06-11_nvlink_boundary" / "kimi_ramp" / "bench" / "kimi_c32.json")
    after = bench_throughput(RUNS / "2026-08-03_nvlink_gap_fill" / "kimi" / "bench" / "kimi_c32.json")
    fig, ax = new_ax(4.6, 3.3)
    _przed_po(ax, [("8 kart", before, after)], BLUE, 720, "Kimi - 32 użytkowników naraz")
    save(fig, "w5b_kimi.svg")


# ---------------------------------------------------------------- W6 (zapas Z2)
def w6_qwen_tp_nvlink() -> None:
    q = RUNS / "2026-08-31_latencja_dostepu" / "qwen"
    files = [("1 karta", "bench_tp1/tp1_c32.json"), ("2 karty", "bench_tp2isl/tp2isl_c32.json"),
             ("4 karty", "bench_tp4isl/tp4isl_c32.json"), ("8 kart", "bench_tp8/tp8_c32.json")]
    vals = [bench_throughput(q / f) for _, f in files]
    fig, ax = new_ax(8.4, 3.2)
    bars = ax.bar(range(4), vals, width=0.6, color=GREEN)
    bar_labels(ax, bars, vals, 30, size=13)
    ax.set_xticks(range(4), [n for n, _ in files])
    ax.tick_params(axis="x", labelcolor=INK, labelsize=13)
    ax.set_ylim(0, 3400)
    ax.set_ylabel("tokeny/s łącznie")
    ax.set_title("Qwen po mostkach - 32 użytkowników naraz", loc="left")
    save(fig, "w6_qwen_tp_nvlink.svg")


# ---------------------------------------------------------------- W7 (zapas Z1)
def w7_kimi_moc_przed_po() -> None:
    """Kimi TP8 c=32, pobor mocy w czasie: era PCIe (06-11) vs po mostkach (08-03).

    Okna maja rozna dlugosc (361 vs 168 probek) — linie "po" konczą się wczesniej.
    """
    before = read_dcgmi(RUNS / "2026-06-11_nvlink_boundary" / "kimi_ramp" / "kimi_c32_dcgmi.txt")
    after = read_dcgmi(RUNS / "2026-08-03_nvlink_gap_fill" / "kimi" / "kimi_c32_dcgmi.txt")
    fig, ax = new_ax(9.0, 3.4)
    for samples, color in ((before, BEFORE), (after, BLUE)):
        for gid in sorted({g for smp in samples for g, *_ in smp}):
            series = [next((pw for g, pw, *_ in smp if g == gid), None) for smp in samples]
            xs = [i for i, v in enumerate(series) if v is not None]
            ys = [v for v in series if v is not None]
            ax.plot(xs, ys, color=color, lw=1.3, alpha=0.65)
    ax.axhline(600, color=CRITICAL, lw=1.6, ls="--")
    ax.text(2, 610, "limit karty: 600 W", color=CRITICAL, fontsize=11, va="bottom")
    ax.text(len(after) - 6, 372, "po mostkach - średnio 303 W", color=BLUE, fontsize=12,
            fontweight="600", ha="right", va="bottom")
    ax.text(len(before) - 4, 118, "era PCIe - średnio 192 W", color=INK2, fontsize=12,
            fontweight="600", ha="right", va="top")
    ax.set_ylim(0, 680)
    ax.set_xlim(0, len(before) - 1)
    ax.set_xlabel("czas okna benchmarku [s] - okna: era PCIe 361 s, po mostkach 168 s")
    ax.set_ylabel("pobór mocy na kartę [W]")
    ax.set_title("Kimi, 8 kart, 32 użytkowników - po jednej linii na kartę", loc="left")
    save(fig, "w7_kimi_moc_przed_po.svg")


# ---------------------------------------------------------------- W8 (zapas Z3)
def w8_qwen_tp4_moc_przed_po() -> None:
    """Qwen TP4 w wyspie (karty 0-3), c=64: pobor mocy w czasie, PCIe vs mostki.

    Tylko karty pracujace — pozostale cztery stoja na ~72 W idle i zanizalyby obraz.
    Okna maja rozna dlugosc (236 vs 78 probek).
    """
    before = read_dcgmi(RUNS / "2026-06-11_bottleneck" / "qwen_tp_curve" / "qwen_tp4_c64_dcgmi.txt")
    after = read_dcgmi(RUNS / "2026-08-31_latencja_dostepu" / "qwen" / "tp4isl_c64_dcgmi.txt")
    fig, ax = new_ax(9.0, 3.4)
    for samples, color in ((before, BEFORE), (after, GREEN)):
        for gid in (0, 1, 2, 3):
            series = [next((pw for g, pw, *_ in smp if g == gid), None) for smp in samples]
            xs = [i for i, v in enumerate(series) if v is not None]
            ys = [v for v in series if v is not None]
            ax.plot(xs, ys, color=color, lw=1.3, alpha=0.7)
    ax.axhline(600, color=CRITICAL, lw=1.6, ls="--")
    ax.text(2, 610, "limit karty: 600 W", color=CRITICAL, fontsize=11, va="bottom")
    ax.text(len(after) + 4, 300, "po mostkach - średnio 271 W", color=GREEN, fontsize=12,
            fontweight="600", ha="left", va="bottom")
    ax.text(len(before) - 4, 130, "era PCIe - średnio 143 W", color=INK2, fontsize=12,
            fontweight="600", ha="right", va="top")
    ax.set_ylim(0, 680)
    ax.set_xlim(0, len(before) - 1)
    ax.set_xlabel("czas okna benchmarku [s] - okna: era PCIe 236 s, po mostkach 78 s")
    ax.margins(x=0)
    ax.set_ylabel("pobór mocy na kartę [W]")
    ax.set_title("Qwen na 4 kartach w jednej wyspie (karty 0-3), 64 użytkowników", loc="left")
    save(fig, "w8_qwen_tp4_moc_przed_po.svg")


if __name__ == "__main__":
    w0_moc_w_czasie()
    w1_krzywa_tp()
    w2_zasoby()
    w3_profil()
    w5a_qwen()
    w5b_kimi()
    w6_qwen_tp_nvlink()
    w7_kimi_moc_przed_po()
    w8_qwen_tp4_moc_przed_po()
