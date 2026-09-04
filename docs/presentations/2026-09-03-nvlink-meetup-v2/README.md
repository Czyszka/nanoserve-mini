# Prezentacja meetupowa NVLink — wersja 2 (katalog roboczy)

Status: **SZKIC — omawianie struktury** (od 2026-09-03).

Wersja 1 (`docs/presentations/2026-07-31-nvlink-meetup/`, 19 slajdów,
~30 min, szkielet = 20-krokowy protokół badania) po pierwszym czytaniu
okazała się zbyt skomplikowana nawet dla odbiorców znających tematykę AI.
Wersja 2 powstaje od nowa: **~20 min, 10–11 slajdów, od ogółu do szczegółu**.
Z v1 bierzemy wyłącznie liczby, wykresy, linki i pojedyncze zdania — nie
strukturę.

## Pliki

| plik | rola |
|---|---|
| `README.md` | ten plik: rama, zasady, materiał z v1 do ponownego użycia |
| `slajdy-v2.md` | szkielet slajdów (tytuły użytkownika) + uwagi krytyczne + pytania do rozstrzygnięcia; później: treść i speaker notes slajd po slajdzie |

Później (po zamknięciu treści): `generate_charts.py` (kopia/redukcja z v1),
`charts/`, `index_src.html` + `build_index.py` (pipeline HTML z v1 działa —
do przeniesienia bez zmian).

## Zasady v2 (propozycja — do akceptacji)

1. **Jeden komunikat na slajd**, wypowiedziany jednym zdaniem na górze
   slajdu. Jeśli slajd potrzebuje dwóch zdań-komunikatów, to są dwa slajdy
   albo jeden z nich idzie do speaker notes.
2. **Maksymalnie jeden wykres lub jedna tabela na slajd**; na slajdzie
   nie więcej niż ~5 liczb. Reszta liczb w speaker notes.
3. **Każdy termin techniczny definiowany raz, jednym zdaniem, w momencie
   pierwszego użycia** — i potem używany konsekwentnie tą samą nazwą.
   Lista terminów i miejsce definicji: `slajdy-v2.md` §B.
4. **Wzory tylko słownie** na slajdzie („czas kroku = narzut silnika +
   komunikacja + obliczenia"); wersja symboliczna co najwyżej w notes.
5. **Bez protokołu badania jako szkieletu** — kolejność narracji jest
   chronologiczna: anomalia → co mierzymy → dlaczego → jak naprawiliśmy →
   ile to dało → ile kosztowało.
6. Tempo: 20 min / 11 slajdów ≈ **1,8 min na slajd**; slajdy pojęciowe
   (5–7) dostają po ~2,5 min, slajdy „obrazkowe" (1, 8) po ~1 min.
   Budżet czasu per slajd w `slajdy-v2.md` §C.

## Materiał z v1 do ponownego użycia

### Liczby (zweryfikowane w v1; źródła w `docs/plans/2026-07-31-nvlink-meetup-prezentacja.md` §„Kluczowe liczby")

- Anomalia: nvidia-smi 100% GPU-Util przy 111 W (Qwen) / ~175–185 W (Kimi)
  na kartę, limit 600 W. Zrzut: `../2026-07-31-nvlink-meetup/nvidia_smi_crop.png`
  (rekonstrukcja nop2p z 08-03, 172–181 W).
- DCGM, Kimi TP8 (c=1 / c=64): moc 170 / 199 W; SM_ACTIVE 0,21 / 0,20;
  DRAM_ACTIVE 0,093 / 0,070; PCIe RX/TX 6–8 GB/s (~10% łącza).
  Kontrast Qwen TP1 c=64: SM_ACTIVE ~0,68, DRAM_ACTIVE ~0,39, 436 W.
- Krzywa TP Qwen, era PCIe, c=64: 1202 / 1404 / 680 / 257 tok/s
  (efektywność 100 / 58 / 14 / 2,7%). c=1 ITL: 8,98 / 9,91 / 10,54 / 14,16 ms.
  Sufit PCIe RX 7,2–7,9 GB/s przy każdym c≥8 (Kimi i Qwen).
- Profile (torch profiler, udział w spanie): Kimi TP8 c=1: 63% bez operacji
  GPU / 22,5% NCCL / 9,1% compute; Kimi TP8 c=16 (PCIe): 83,9% NCCL;
  Qwen TP4 c=64 (PCIe): 53,3% NCCL / 33% gaps / 5,6% compute;
  Kimi TP8 c=32 (NVLink, 08-03): 61,1% NCCL / 30,2% compute.
- All-reduce: ~2 scalenia na warstwę × 61 warstw Kimi ≈ 122 rundy na krok;
  wiadomość ≈ c × hidden(7168) × 2 B ≈ 14 KiB przy c=1.
- Łącza (nominalne): PCIe Gen5 x16 128 GB/s dwukierunkowo, ~20 µs/wymianę
  (literatura); NVLink Bridge H200 NVL 900 GB/s, 2–9 µs (literatura, A100 /
  V100 — **nie H200**; pomiar własny: sesja 2026-08-31).
- Po montażu (07-31/08-03): P2P w wyspie 132,8 GB/s (cross 29,1); NCCL
  busbw w wyspie 185–333, cross 2+2: 24,8–31,3 GB/s.
  Qwen TP4 c64: 680 → 2022 tok/s (2,97×); Kimi TP8 c32: 285 → 594 (2,08×);
  c=1: Qwen TPOT 4,00 → 3,21 ms (−20%), Kimi 8,7 → 7,44 ms (−15%).
- Custom all-reduce vLLM: aktywny przy TP≤4 w wyspie (pełna siatka),
  nieaktywny przy TP8 (4+4). Wkład @c64: 1,0–1,2× (nierozstrzygnięty),
  @c1 ~+8%.
- Reguła wygrzewki (kara zimnego startu 10–15%) i szum ±0,4 ms (TP2) —
  do speaker notes, nie na slajdy.

### Wykresy v1 (`../2026-07-31-nvlink-meetup/charts/`, generator `generate_charts.py`)

W0 moc w czasie · W1 krzywa TP · W2 util vs liczniki · W3 profil (słupki
skumulowane) · W4 P2P/busbw (log) · W5 przed/po · W7 DRAM_ACTIVE.
Do v2 kandydują W0, W2, W1, W3, W5 — każdy do uproszczenia (mniej serii,
większe fonty, jeden komunikat). W4 i W7 raczej wypadają.

### Linki do badań i źródeł (z v1 / notatki decyzyjnej / reading listy)

- Karta katalogowa H200 NVL (PCIe 128 GB/s, NVLink 900 GB/s):
  <https://www.pny.com/file%20library/company/support/linecards/data-center-gpus/h200-nvl-datasheet.pdf>
- Latencje P2P NVLink vs PCIe (A100: 2 µs vs 20 µs):
  <https://intuitionlabs.ai/articles/nvidia-nvlink-gpu-interconnect>
- Li et al., *Evaluating Modern GPU Interconnect: PCIe, NVLink, NV-SLI,
  NVSwitch and GPUDirect* (P100/V100: 9 µs vs 20 µs): <https://arxiv.org/abs/1903.04611>
- *Scaling LLM Inference Beyond Amdahl's Limits via Eliminating Non-Scalable
  Overheads* (Amdahl dla TP): <https://arxiv.org/abs/2606.01927>
- Megatron-LM (skąd 2 all-reduce na warstwę): <https://arxiv.org/abs/1909.08053>
- Pope et al., *Efficiently Scaling Transformer Inference* (roofline dla
  transformerów): <https://arxiv.org/abs/2211.05102>
- Konfiguracja Kimi K2 (hidden 7168, 61 warstw):
  <https://huggingface.co/moonshotai/Kimi-K2-Instruct-0905/resolve/main/config.json>
- Implementacja modelu w vLLM (miejsca all-reduce):
  <https://github.com/vllm-project/vllm/blob/v0.20.0/vllm/model_executor/models/deepseek_v2.py>
- Kontekst dydaktyczny (Stanford CS349D): <https://web.stanford.edu/class/cs349d/>

### Dokumenty źródłowe w repo

- `docs/writeups/w1/nvlink-4way-notatka-decyzyjna.md` — pełna notatka
  decyzyjna (po polsku; §4 mechanizm kroku, §7 model Amdahla, zał. A słowniczek,
  zał. B topologia).
- `docs/writeups/w1/t9-bottleneck-nvlink.md` §14 — pomiar po interwencji.
- `results/summaries/2026-06-11-nvlink-boundary-verdict.md` — werdykt PCIe-era.
- `results/summaries/2026-08-03-nvlink-day-summary.md` — dzień po montażu.
- `docs/operations/infrastructure.md` §2.2 — topologia (macierz `topo -m`,
  schemat CPU/switch/GPU).
- `docs/plans/2026-08-31-latencja-dostepu-nvlink.md` — sesja mierząca
  latencję all-reduce + grid Qwen TP×c×łącze + profile TP1–TP8 (dane do
  slajdów 4, 6, 9 — **wyniki jeszcze nie w repo**).

## Budowanie (2026-09-04)

```bash
uv run --with matplotlib python docs/presentations/2026-09-03-nvlink-meetup-v2/generate_charts.py
uv run python docs/presentations/2026-09-03-nvlink-meetup-v2/build_index.py
```

Wynik: `index.html` (samodzielny, 11 slajdów + 4 zapasowe Z1–Z4, bez
notatek — nawigacja ← →, motyw T). Zrzut nvidia-smi wspólny z v1. Treść
i notatki prelegenta: `tresc-slajdow-v2.md`.
