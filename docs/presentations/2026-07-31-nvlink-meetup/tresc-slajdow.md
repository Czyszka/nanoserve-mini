# Treść slajdów — „100% GPU-Util, a tylko 1/3 mocy"

Plik roboczy etapu 2 (treść) planu
`docs/plans/2026-07-31-nvlink-meetup-prezentacja.md`. Tworzony
iteracyjnie z użytkownikiem, slajd po slajdzie:
plan → pytania → odpowiedzi → tekst → poprawki → **AKCEPTACJA** →
następny slajd.

Konwencja wpisu na slajd:

- **Na slajdzie** — dokładny tekst widoczny dla sali (nagłówek, punkty,
  podpisy elementów graficznych).
- **Speaker notes** — pełna narracja prelegenta (3–6 zdań), w tym zasady
  metodyczne wypowiadane ustnie.
- **Status** — SZKIC / W ITERACJI / ZAAKCEPTOWANY.

Reguła tonu (od slajdu 1): speaker notes w tonie naukowym — referujemy
wyniki badań, bez retoryki sprzedażowej, bez obiecywania korzyści
słuchaczom.

Konwencja tytułów (od slajdu 3): slajdy protokołu mają nagłówek
„Krok N: nazwa kroku" (numeracja z protokołu badania w planie).

---

## Slajd 1 — Tytuł

Status: ZAAKCEPTOWANY (2026-08-09)

Decyzje: bez danych prelegenta (przedstawia się ustnie), bez nazwy
wydarzenia i daty, bez linków do GitHub (na żadnym slajdzie).

### Na slajdzie

> # 100% GPU-Util, a tylko 1/3 mocy —
> # jak badać wydajność inferencji LLM?
>
> Studium przypadku: vLLM, Kimi-K2.6 (1T), 8×H200, prawo Amdahla

### Speaker notes

Cześć — zanim zaczniemy, dwa słowa o mnie. [przedstawienie ustne,
poza slajdem]. Ten tytuł to nie metafora, tylko prawdziwy odczyt z
naszego serwera: osiem kart H200 raportowało 100% zajętości, a
pobierało ledwie jedną trzecią dostępnej mocy. Sytuację tę
zaplanowałem przedstawić w formie studium przypadku, aby teoria mogła
spotkać się z praktyką i pokazać kompletny, powtarzalny protokół
badania wydajności: od zauważenia anomalii, przez hipotezy i
eksperymenty, po decyzję sprzętową zweryfikowaną pomiarem.

---

## Slajd 2 — Kontekst studium przypadku

Status: ZAAKCEPTOWANY (2026-08-09, z poprawkami użytkownika)

Decyzje: bez nazwy projektu — „serwer badawczy / laboratoryjny";
tylko elementy sprzętu istotne dla badania z istotnymi parametrami;
czysto technicznie, bez kontekstu biznesowego; rola Qwen wyjaśniona
w speaker notes (w tym zastrzeżenie o TP=4).

### Na slajdzie

> ## Studium przypadku: serwer badawczy
>
> **CPU:** 2× Intel Xeon Gold 6530 (dwa sockety)
>
> **GPU:** 8× NVIDIA H200 NVL — PCIe 5.0, 143 GB
>
> **Modele:**
> - Kimi-K2.6 — 1T parametrów, 554 GB wag, TP=8
> - Qwen3.6-35B — model testowy (pomiary TP=1/2/4/8)

### Speaker notes

Środowisko badania: serwer laboratoryjny z dwoma procesorami Xeon
Gold 6530 i ośmioma kartami H200 NVL po 143 GB, połączonymi magistralą PCIe 5.0. Inferencję serwuje vLLM w kontenerach Docker. Model główny to Kimi-K2.6: bilion
parametrów, 554 GB wag — nie mieści się na mniej niż ośmiu kartach,
więc pracuje wyłącznie w konfiguracji TP=8, z dekodowaniem
spekulacyjnym Eagle3. Drugim modelem jest Qwen3.6-35B w roli narzędzia
badawczego: mieści się na pojedynczej karcie, dzięki czemu umożliwia
pomiary przy TP=1, 2 i 4 (w badaniu także TP=8). Należy zaznaczyć, że
TP=4/8 dla modelu tej wielkości nie jest poprawną konfiguracją
produkcyjną.

---

## Slajd 3 — Krok 1: Zauważ anomalię

Status: ZAAKCEPTOWANY (2026-08-09, z poprawkami użytkownika)

Decyzje: screen bez adnotacji (kontekst rekonstrukcji tylko w speaker
notes); pytanie do sali wyświetlone na slajdzie; bez liczb w podpisach
— obserwacja wizualna; do screena dochodzi wykres W0 (moc w czasie z
oryginalnych badań ery PCIe).

### Na slajdzie

> ## Krok 1: Zauważ anomalię
>
> [ZRZUT: nvidia-smi — 8× H200, kolumny GPU-Util i moc]
>
> [WYKRES W0: pobór mocy wszystkich GPU w czasie okna benchmarku,
> pozioma linia limitu 600 W]
>
> **Kto spotkał się z taką sytuacją i zastanawiał się, dlaczego przy
> 100% GPU-Util karty zużywają tylko ~30% dostępnej mocy?**

### Speaker notes

Punkt wyjścia badania: podczas benchmarków obciążających wszystkie
osiem kart nvidia-smi raportował 100% GPU-Util, a jednocześnie pobór
mocy pozostawał w okolicach 111-185 W na kartę, przy limicie 600 W.
Wykres pokazuje przebieg mocy w całym oknie pomiarowym z oryginalnych
badań — to stan trwały, a nie chwilowy przestój między zadaniami.
Pierwszy krok protokołu: nie przechodzić obok takiej obserwacji —
zanotować ją, zanim cokolwiek zaczniemy zmieniać.

---

## Slajd 4 — Krok 2: Zrozum, co mierzy Twoja metryka

Status: ZAAKCEPTOWANY (2026-08-09)

Decyzje: na slajdzie hasło (nie pełna definicja); definicja formalna +
wyjaśnienie pojęcia „kernel" + źródło (NVML) w speaker notes; grafika
osi czasu (GRAFIKA D2); na slajdzie lista elementów składowych
zajętości.

### Na slajdzie

> ## Krok 2: Zrozum, co mierzy Twoja metryka
>
> **GPU-Util mierzy: „czy coś się dzieje" — nie: „ile krzemu pracuje"**
>
> [GRAFIKA D2: oś czasu jednego kroku dekodowania — kolejne odcinki:
> kernel obliczeniowy | kernel NCCL (czeka na inne GPU) | kernel
> memory-bound | przerwa (host); klamra nad wszystkimi odcinkami z
> kernelami: „dla GPU-Util wszystko to = zajęte"]
>
> Elementy składowe zajętości:
> - kernele obliczeniowe (compute)
> - kernele komunikacyjne NCCL — w tym czekanie (spin-wait) na inne GPU
> - operacje ograniczone pamięcią (memory-bound)
> - drobne kernele orkiestracji

### Speaker notes

Definicja formalna, za dokumentacją NVIDIA NVML (pole
`utilization.gpu`): GPU-Util to procent czasu w oknie próbkowania, w
którym na karcie wykonywał się co najmniej jeden kernel. Kernel to
pojedynczy program uruchamiany na GPU — na przykład jedno mnożenie
macierzy, jedna operacja na pamięci albo jedna operacja komunikacji
zbiorowej. Metryka nie rozróżnia, co ten kernel robi: kernel NCCL,
który w pętli czeka na dane od innej karty, podnosi zajętość dokładnie
tak samo jak kernel liczący mnożenie macierzy. W konsekwencji 100%
GPU-Util informuje jedynie, że kolejka karty nie była pusta — kolejka
to bufor zadań (strumienie CUDA), z którego GPU pobiera kolejne
kernele do wykonania; dopóki czeka w niej choć jeden kernel, karta
raportuje zajętość. Nic to nie mówi o nasyceniu jednostek
obliczeniowych ani interfejsu pamięci.

---

## Slajd 5 — Kroki 3–4: Zmierz nasycenie właściwymi licznikami

Status: ZAAKCEPTOWANY (2026-08-09)

Decyzje: tabelka + wykres W2 (oba); krótkie nazwy liczników na
slajdzie (pełne identyfikatory w notes); krok 4 („zapisz wyniki")
tylko ustnie; na slajdzie komenda `dcgmi dmon`; wyjaśnienie SM/HBM w
speaker notes.

### Na slajdzie

> ## Kroki 3–4: Zmierz nasycenie właściwymi licznikami
>
> Narzędzie: **DCGM** — `dcgmi dmon` (pomiar z hosta, bez zmian w
> kontenerach)
>
> Pomiar: **Kimi-K2.6, TP=8 — okna c=1 i c=64 (c = liczba
> równoległych zapytań)**
>
> | Licznik | Co mierzy | Wynik u nas (c=1 / c=64) |
> |---|---|---|
> | moc | pobór względem limitu 600 W | **170 / 199 W ≈ 30% limitu** |
> | SM_ACTIVE | % czasu, w którym jednostki obliczeniowe (SM) pracują | **0,21 / 0,20 (~20%)** |
> | DRAM_ACTIVE | % czasu aktywności interfejsu pamięci HBM | **0,093 / 0,070 (7–9%)** |
> | PCIe RX/TX | ruch na magistrali GPU↔reszta systemu | **~10% przepustowości łącza** (6–8 GB/s) |
>
> [WYKRES W2: GPU-Util 100% zestawione słupkami z mocą, SM_ACTIVE i
> DRAM_ACTIVE]
>
> **GPU-Util: 100%. Nasycenie: żadnego zasobu.**

### Speaker notes

DCGM (Data Center GPU Manager) to narzędzie NVIDIA do monitoringu
GPU; `dcgmi dmon` próbkuje liczniki profilowania na żywo z poziomu
hosta, bez modyfikowania kontenerów z inferencją. SM (streaming
multiprocessor) to podstawowy blok obliczeniowy GPU — karta zawiera
ich ponad sto, a SM_ACTIVE podaje, przez jaki procent czasu bloki te
wykonywały jakiekolwiek instrukcje. DRAM_ACTIVE analogicznie mierzy
procent czasu, w którym pracował interfejs pamięci HBM — czyli jak
mocno wykorzystujemy przepustowość pamięci karty. Wyniki dotyczą
modelu produkcyjnego Kimi-K2.6 na TP=8, w dwóch oknach pomiarowych:
jeden klient (c=1) i 64 klientów (c=64); trzecie okno — stan
spoczynkowy — dało 0,000 na obu licznikach aktywności, co potwierdza
poprawne odseparowanie obciążenia od tła. Przy stałym 100% GPU-Util
moc to 170–199 W, czyli około 30% limitu, jednostki obliczeniowe
pracują przez ~20% czasu, interfejs pamięci przez 7–9%, a magistrala
PCIe przenosi 6–8 GB/s, czyli ~10% swojej przepustowości — żaden
zasób nie zbliża się do nasycenia. Zastrzeżenie: profil zależy od
modelu i
konfiguracji — testowy Qwen przy TP=1 i c=64 osiągał SMACT 0,68 i
DRAM_ACTIVE 0,39 na swojej jedynej karcie; anomalia dotyczy właśnie
konfiguracji wielokartowych. Zgodnie z krokiem 4 protokołu wszystkie
odczyty zapisujemy liczbowo, z datą i pełną konfiguracją — będą
podstawą porównań w kolejnych krokach. (Pełne identyfikatory:
`DCGM_FI_DEV_POWER_USAGE`, `DCGM_FI_PROF_SM_ACTIVE`,
`DCGM_FI_PROF_DRAM_ACTIVE`, `DCGM_FI_PROF_PCIE_RX_BYTES` /
`_TX_BYTES`.)

---

## Slajd 6 — Kroki 5–6: Postaw hipotezy z przewidywaniami

Status: ZAAKCEPTOWANY (2026-08-09; uzupełniony o wzór T(krok) na
życzenie użytkownika — decyzja: wzór debiutuje tu, slajd 11 odwołuje
się do składnika N_rounds × r, slajd 14 tylko kalibruje wzór
liczbami)

Źródło metodyczne: `docs/writeups/w1/nvlink-4way-notatka-decyzyjna.md`
§4 (składniki czasu kroku i ich ślady) + §5 (metodyka interwencji).
Hipotezy wyprowadzone z rozkładu czasu kroku — przestrzeń hipotez
pokrywa cały krok z konstrukcji, nie ze zgadywania.

### Na slajdzie

> ## Kroki 5–6: Postaw hipotezy z przewidywaniami
>
> Czas kroku generowania rozkłada się na trzy składniki:
>
> **T(krok) = F_host + N_rounds × r(łącze, liczba kart) + W_silicon**
>
> stały narzut silnika | komunikacja: rundy × czas rundy | obliczenia
> i pamięć
>
> | Hipoteza (składnik) | Mechanizm | Przewidywany ślad w danych |
> |---|---|---|
> | **H1: pamięć HBM** (`W_silicon`) | karta czeka na odczyt wag z pamięci | wysoki DRAM_ACTIVE (0,70–0,90) |
> | **H2: komunikacja GPU↔GPU** (`N_rounds × r`) | krok czeka na scalenia (all-reduce) po PCIe | czas kroku rośnie z liczbą kart; w profilu przeważa komunikacja |
> | **H3: narzut hosta** (`F_host`) | silnik obciąża każdy krok: wybór zapytań, spekulacja, wymiana poleceń CPU↔GPU | krok drogi nawet na 1 karcie; w profilu przeważają przerwy |
> | **H4: topologia (UPI)** (wariant `r(łącze)`) | trasa między gniazdami CPU wolniejsza niż przez switch PCIe | ta sama liczba kart, gorszy wynik na trasie przez UPI |

### Speaker notes

Hipotezy nie są dowolne — wynikają z rozkładu czasu kroku generowania
na trzy składniki wzoru: stały narzut silnika `F_host`, komunikację
`N_rounds × r` (liczba synchronicznych rund scalania razy czas jednej
rundy, zależny od łącza i liczby kart) oraz obliczenia i pamięć
`W_silicon`. Suma składników to cały krok, więc
przestrzeń hipotez jest z konstrukcji kompletna; H4 to wariant
topologiczny H2 — pytanie nie „czy komunikacja", ale „która trasa".
Dwa pojęcia: all-reduce to synchroniczne scalanie wyników częściowych
z wszystkich kart — przy podziale modelu (tensor parallelism) trzeba
scalać ~2 razy na warstwę, co dla 61 warstw Kimi daje ~122 scalenia
na każdy krok, a żadna karta nie rusza dalej, dopóki nie skończy
ostatnia. UPI to łącze między dwoma procesorami serwera — karty
podpięte pod różne CPU komunikują się właśnie przez nie. Kluczowy
element kroku 6: do każdej hipotezy z góry zapisujemy ślad, jaki
musiałaby zostawić w danych — dzięki temu wynik pomiaru będzie
rozstrzygał, a nie ilustrował.

---

## Slajd 7 — Krok 7: Szybkie eliminacje

Status: ZAAKCEPTOWANY (2026-08-09)

Decyzje: slajd czysto o H1 (poszlaka PCIe za H2 przeniesiona do bloku
H2); wprowadzamy stały schemat „boksu werdyktu" (predykcja → pomiar →
werdykt z zakresem ważności), który wraca przy H4/H3/H2 i dalej;
wykres W7: DRAM_ACTIVE w osi czasu + pas wartości oczekiwanych przy
H1.

### Na slajdzie

> ## Krok 7: Szybkie eliminacje
>
> Zanim zaplanujesz eksperymenty — sprawdź, które hipotezy padają od
> danych, które już masz.
>
> [WYKRES W7: przebieg DRAM_ACTIVE w czasie całego okna obciążenia
> (c=1 i c=64) + zaznaczony pas 0,70–0,90 z etykietą „oczekiwane, gdyby
> krok ograniczała pamięć HBM"]
>
> ┌─ WERDYKT ──────────────────────────────────────────┐
> │ Predykcja H1: DRAM_ACTIVE 0,70–0,90                │
> │ Pomiar:       0,070–0,093                          │
> │ **H1 OBALONA** — bez żadnego eksperymentu;         │
> │ do hipotezy nie wracamy                            │
> └────────────────────────────────────────────────────┘

### Speaker notes

Krok 7 to eliminacje w kolejności kosztu: zanim uruchomimy jakikolwiek
eksperyment, konfrontujemy hipotezy z danymi już zebranymi w krokach
3–4. H1 miała z góry zapisany ślad — aktywność interfejsu pamięci na
poziomie 0,70–0,90 — a pomiar pokazuje 0,070–0,093, czyli o rząd
wielkości mniej, stabilnie przez całe okno obciążenia. Zastrzeżenie
metodyczne: próbkowanie co 1 sekundę uśrednia chwilowe skoki wewnątrz
kroku dekodowania, więc nie jest to pełna charakterystyka pamięci HBM
— ale przy różnicy rzędu wielkości wystarcza do werdyktu. Werdykt
zapisujemy w formacie, który będzie wracał do końca prezentacji:
predykcja, pomiar, rozstrzygnięcie z zakresem ważności — tu: obalona
dla badanych scenariuszy pracy serwera. Hipoteza kosztowała nas zero
dodatkowych pomiarów; zostały trzy, każda wymaga już eksperymentu.

---

## Slajd 8 — Kroki 8–10: Zaplanuj eksperymenty i skalibruj szum

Status: ZAAKCEPTOWANY (2026-08-09)

Decyzje: tabela dwukolumnowa (hipoteza → eksperyment, co robimy);
cytat kryterium przyczynowości na slajdzie; trzy źródła danych i
kalibracja szumu w speaker notes.

### Na slajdzie

> ## Kroki 8–10: Zaplanuj eksperymenty
>
> *„Jeżeli badany mechanizm rzeczywiście odpowiada za czas kroku, to
> jego pogorszenie musi ten czas mierzalnie wydłużyć, natomiast brak
> efektu wyklucza go jako przyczynę."*
>
> | Hipoteza | Eksperyment — co robimy |
> |---|---|
> | **H4: topologia (UPI)** | ta sama para kart TP=2: raz pod wspólnym switchem PCIe, raz na dwóch różnych CPU (trasa przez UPI) |
> | **H3: narzut hosta** | profil czasowy kroku przy c=1 + wyłączanie po kolei: spekulacji, CUDA Graphs, oszczędzania energii CPU |
> | **H2: komunikacja** | krzywa TP=1/2/4/8 przy niezmienionej reszcie konfiguracji + wyłączenie bezpośredniej komunikacji P2P + profil pod obciążeniem |
>
> Kolejność badań: od najtańszego sprawdzenia.

### Speaker notes

Reguła planu: każdy eksperyment zmienia dokładnie jeden element
układu, reszta konfiguracji zostaje zamrożona — inaczej wynik nie
wskaże przyczyny. Kolejność ustala koszt: H4 to jeden dodatkowy bieg,
H3 to jeden profil i trzy przełączniki silnika, H2 wymaga osobnego
startu silnika dla każdej wartości TP. Dane będą pochodzić z trzech
niezależnych źródeł: metryk po stronie klienta (`vllm bench serve` —
TPOT/ITL i przepustowość, każdy pomiar po rozgrzewce), liczników
sprzętowych DCGM (`dcgmi dmon`, próbkowanie co 1 s, uśrednianie tylko
w oknie benchmarku) oraz profilu czasowego torch profiler (rozkład
czasu kroku na komunikację, obliczenia i przerwy) — zbieżność źródeł
sprawdzimy osobno w kroku 15. Do tego kalibracja szumu: restarty
silnika, których i tak wymagały warianty eksperymentów, posłużyły do
oszacowania zmienności pomiaru — dla TP=2 wyniosła około ±0,4 ms
między niezależnymi uruchomieniami; każdą przyszłą różnicę będziemy
odnosić do tego pasma, zanim nazwiemy ją efektem.

---

## Slajd 9 — Kroki 11–14: Eksperyment H4 — kara UPI

Status: ZAAKCEPTOWANY (2026-08-09)

Decyzje: pełna topologia serwera na diagramie D1 (z wyróżnionymi
dwiema porównywanymi trasami); oba porównania z §6.3 (TP=2 c=1 i
TP=4 c=64); subtelność „UPI pozornie lepsze = szum" w speaker notes.

### Na slajdzie

> ## Kroki 11–14: Eksperyment H4 — kara UPI (najtańszy test)
>
> [DIAGRAM D1: pełna topologia — 2× CPU połączone łączem UPI, 4 switche
> PCIe 5.0 x16, pary GPU (0,1)(2,3) pod CPU0 i (4,5)(6,7) pod CPU1;
> wyróżnione dwie porównywane trasy: GPU0↔GPU1 przez wspólny switch
> oraz GPU0↔GPU4 przez UPI]
>
> | Porównanie | przez switch PCIe | trasa przez UPI |
> |---|---|---|
> | TP=2, c=1 — czas kroku | 9,91 ms | 9,13 ms |
> | TP=4, c=64 — czas kroku / przepustowość | 53,7 ms / 680 tok/s | 48,3 ms / 716 tok/s |
>
> ┌─ WERDYKT ──────────────────────────────────────────┐
> │ Predykcja H4: trasa przez UPI wyraźnie wolniejsza  │
> │ Pomiar: w żadnym porównaniu nie jest wolniejsza    │
> │ **H4 OBALONA** (dla badanych układów 2 i 4 kart)   │
> └────────────────────────────────────────────────────┘

### Speaker notes

Konstrukcja eksperymentu: ta sama liczba kart, zmieniamy wyłącznie
trasę komunikacji — rozmieszczenie wymusza `CUDA_VISIBLE_DEVICES`,
a kontrolę poprawności daje pobór mocy: karty nieuczestniczące
pozostają przy poziomie spoczynkowym ~70 W, więc obciążenie na pewno
szło na wskazane GPU. Wyniki: przy dwóch kartach wariant przez UPI
wyszedł 9,13 ms wobec 9,91 ms — pozornie szybszy, ale to pojedynczy
pomiar przy zmienności ±0,4 ms między niezależnymi startami, więc
odczytujemy go wyłącznie jako brak kary, nie jako przewagę UPI;
analogicznie przy czterech kartach pod c=64. Werdykt: H4 obalona dla
badanych układów w tym serwerze — najgroźniejsza topologicznie trasa
nie kosztuje nic mierzalnego. To ważny wynik kierunkowy: skoro rodzaj
trasy nie boli, podejrzenie przesuwa się na liczbę uczestników
komunikacji i na stały narzut — czyli dokładnie na H2 i H3, które
badamy dalej, wciąż w kolejności kosztu.

---

## Slajd 10 — Kroki 11–14: Eksperyment H3 — stały narzut hosta

Status: ZAAKCEPTOWANY (2026-08-09)

Decyzje: terminologia z notatki — „stały narzut hosta" (F_host), nie
„podłoga"; „interwencje", nie „dawki" (obowiązuje od teraz w całej
prezentacji); W3 tutaj tylko słupek c=1 (pełne porównanie wróci przy
H2); pełna tabela interwencji §6.5 z atrybucją (Qwen TP=1); kontrola
narzutu profilera w notes.

### Na slajdzie

> ## Kroki 11–14: Eksperyment H3 — stały narzut hosta
>
> Stały narzut (F_host): czas, który silnik serwujący zużywa w każdym
> kroku na czynności organizacyjne — wybór zapytań do kroku, obsługę
> spekulacji, wymianę poleceń CPU↔GPU — niezależnie od sprzętu.
>
> [WYKRES W3a: słupek skumulowany — rozkład czasu profilu, Kimi TP=8,
> c=1: **63% bez żadnej operacji GPU** | 22,5% komunikacja NCCL |
> 9,1% obliczenia | 5,6% inne]
>
> Interwencje w składniki narzutu (model testowy Qwen, TP=1 — celowo
> bez komunikacji):
>
> | Wariant | Czas kroku | TPOT |
> |---|---|---|
> | pełna konfiguracja | 8,93 ms | 3,39 ms |
> | spekulacja wyłączona | 5,36 ms | 5,36 ms |
> | CUDA Graphs wyłączone (tryb eager) | 55,1 ms | 19,6 ms |
> | governor CPU `performance` | 9,86 ms | 3,70 ms |
>
> **Krótszy krok nie znaczy szybszy token** — bez spekulacji krok
> daje 1 token zamiast ~2,6.
>
> ┌─ WERDYKT ──────────────────────────────────────────┐
> │ Predykcja H3: krok drogi nawet bez komunikacji,    │
> │ w profilu przeważają przerwy                       │
> │ Pomiar: 63% kroku bez operacji GPU; obsługa        │
> │ spekulacji 3,57 ms = 40% kroku; CUDA Graphs        │
> │ maskują ~46 ms narzutu na krok                     │
> │ **H3 POTWIERDZONA dla c=1** — szybsze łącze między │
> │ kartami tego nie naprawi                           │
> └────────────────────────────────────────────────────┘

### Speaker notes

Tu debiutuje trzecie źródło danych — profil czasowy torch profiler,
czyli pełna oś czasu operacji GPU; kontrola rzetelności: przebieg
profilowany i nieprofilowany różnią się o około 5%, więc profil nie
zniekształca obrazu. W profilu pojedynczego zapytania największym
składnikiem jest czas bez żadnej zarejestrowanej operacji GPU — 63% —
to właśnie stały narzut hosta. Interwencje wykonano na modelu
testowym przy TP=1, gdzie komunikacja nie występuje, więc wynik
przypisuje koszty wyłącznie hostowi. Dwie metryki w tabeli: czas
kroku podajemy jako medianę ITL, czyli odstępu między kolejnymi
porcjami wygenerowanych tokenów zwracanymi przez serwer; TPOT
pokazuje średni czas przypadający na jeden wygenerowany token. Przy
spekulacji MTP jeden krok może zaakceptować więcej niż jeden token,
dlatego TPOT może pozostać podobny nawet wtedy, gdy sam krok,
mierzony przez ITL, staje się dłuższy. Czytanie tabeli: wyłączenie
spekulacji skraca krok z 8,93 do 5,36 ms, ale krok bez spekulacji
daje jeden token zamiast średnio ~2,6 — na pojedynczy token spekulacja
wygrywa (TPOT 3,39 vs 5,36 ms), a jej obsługa kosztuje 3,57 ms, czyli
40% kroku. Wariant eager nie rozkłada kroku, lecz ujawnia koszt,
którego konfiguracja unika: bez CUDA Graphs (mechanizmu nagrywania
sekwencji kerneli i odtwarzania ich jednym poleceniem) krok rośnie do
55,1 ms przy SM_ACTIVE 0,009 — karta niemal wyłącznie czeka na
polecenia hosta. Governor CPU w trybie `performance` nic nie zmienia —
oszczędzanie energii zostaje uniewinnione. Werdykt: H3 potwierdzona
dla pojedynczego klienta.

---

## Slajd 11 — Kroki 11–13: Eksperyment H2 (a) — jak płynie komunikacja

Status: ZAAKCEPTOWANY (2026-08-09)

Decyzje: jedna topologia D1 z podświetlanymi grupami TP; schemat
warstwy (skąd ~122 scalenia) na slajdzie jako grafika D3; detal ring
all-reduce w notes; slajd kończy zapisane przewidywanie.

### Na slajdzie

> ## Kroki 11–13: Eksperyment H2 (a) — jak płynie komunikacja
>
> Badany składnik wzoru: **N_rounds × r(łącze, liczba kart)**
>
> [DIAGRAM D1: jedna topologia serwera, podświetlane grupy —
> **TP=1**: jedna karta, zero komunikacji (punkt odniesienia);
> **TP=2**: para pod wspólnym switchem PCIe;
> **TP=4**: cztery karty pod jednym CPU, trasa przez root;
> **TP=8**: wszystkie karty, część par przez UPI]
>
> [SCHEMAT D3: jedna warstwa modelu pod TP —
> blok uwagi → **SCALENIE 1 (all-reduce)** → blok FFN/MoE →
> **SCALENIE 2 (all-reduce)**; × 61 warstw Kimi →
> **~122 scalenia w każdym kroku**; scalenie jest synchroniczne —
> żadna karta nie kontynuuje, dopóki nie skończy ostatnia]
>
> **Przewidywanie (zapisane przed pomiarem):** jeśli H2 prawdziwa —
> czas kroku rośnie z liczbą kart, a w profilu pod obciążeniem
> przeważa komunikacja.

### Speaker notes

Składnik `N_rounds × r` ma dwie części o różnym pochodzeniu:
`N_rounds` wynika z architektury modelu — po bloku uwagi i po bloku
FFN/MoE wyniki częściowe trzeba scalić, czyli ~2 razy na warstwę, co
przy 61 warstwach Kimi daje ~122 obowiązkowe scalenia w każdym kroku;
`r` to czas jednej rundy, zależny od łącza i rosnący z liczbą
uczestników. Samo scalanie realizuje biblioteka NCCL; modelem
odniesienia jest ring all-reduce — karty tworzą logiczny pierścień,
redukcja i rozesłanie wyniku to 2(N−1) kroków, a każda karta czeka na
pozostałe w każdej rundzie; NCCL dobiera wariant algorytmu per
wywołanie. Istotne dla interpretacji: sprzętowo przyspieszane ścieżki
scalania były na tym serwerze nieaktywne — własny all-reduce vLLM
wyłączony (nieobsługiwany dla >2 GPU w konfiguracji wyłącznie PCIe),
multicast NVLS niedostępny — scala więc standardowe NCCL po PCIe.
Konstrukcja eksperymentu: krzywa TP na modelu testowym, gdzie TP=1
działa bez żadnej komunikacji i stanowi punkt odniesienia — każdą
dodatkową milisekundę kroku przy TP=2/4/8 można przypisać wyłącznie
zrównolegleniu. Przewidywanie zapisujemy przed pomiarem — na
następnym slajdzie skonfrontujemy je z danymi.

---

## Slajd 12 — Kroki 12–14: Eksperyment H2 (b) — wyniki i werdykt

Status: ZAAKCEPTOWANY (2026-08-09)

Decyzje: tabela c=1 na slajdzie; udziały profili jako tabela „jak w
notatce" (zamiast wykresu W3 na tym slajdzie); spadek mocy/SMACT w
notes; wynik interwencji P2P na slajdzie; bilans śledztwa zamyka
slajd.

### Na slajdzie

> ## Kroki 12–14: Eksperyment H2 (b) — wyniki i werdykt
>
> [WYKRES W1: krzywa TP przy c=64 — słupki przepustowości
> 1202 / 1404 / 680 / 257 tok/s + linia efektywności skalowania
> 100 / 58 / 14 / 2,7%]
>
> Wzrost czasu kroku przy c=1 (względem TP=1):
>
> | TP | 1 | 2 | 4 | 8 |
> |---|---:|---:|---:|---:|
> | czas kroku (ITL) | 8,98 ms | 9,91 ms | 10,54 ms | 14,16 ms |
> | wzrost | — | +0,93 ms | +1,56 ms | **+5,18 ms** |
>
> Udział składników w profilu czasowym kroku:
>
> | profil | bez operacji GPU | komunikacja NCCL | obliczenia |
> |---|---:|---:|---:|
> | Kimi TP=8, c=1 | 63% | 22,5% | 9,1% |
> | Kimi TP=8, c=16 | 10% | **83,9%** | 4,6% |
> | Qwen TP=4, c=64 | 33% | **53,3%** | 5,6% |
>
> Interwencja P2P (TP=2, c=64): wyłączenie bezpośredniej komunikacji
> GPU↔GPU: 1403,5 → 1395,6 tok/s (**−0,6%** — brak efektu)
>
> ┌─ WERDYKT ──────────────────────────────────────────┐
> │ Predykcja H2: czas kroku rośnie z liczbą kart,     │
> │ profil pod obciążeniem zdominowany komunikacją     │
> │ Pomiar: +5,18 ms przy TP=8 (13× pasmo szumu);      │
> │ NCCL 83,9% profilu pod obciążeniem; przy TP=2      │
> │ efekt ≈ 0                                          │
> │ **H2 POTWIERDZONA dla TP≥4 pod obciążeniem         │
> │ równoległym** — winowajcą liczba uczestników       │
> │ scalania, nie pojedyncza trasa                     │
> └────────────────────────────────────────────────────┘
>
> Bilans śledztwa: **c=1 → stały narzut hosta (H3)**;
> **obciążenie równoległe + TP≥4 → komunikacja (H2)**; H1, H4 obalone.

### Speaker notes

Czytanie krzywej: TP=2 daje +17% przepustowości względem jednej karty
(58% ideału), od TP=4 wynik spada poniżej pojedynczej karty, a TP=8
osiąga 21% wyniku TP=1 przy efektywności skalowania 2,7%. Przyrosty
czasu kroku odnosimy do pasma szumu ±0,4 ms: +1,56 ms przy TP=4 to
4× pasmo, +5,18 ms przy TP=8 to 13× — efekty realne; +0,93 ms przy
TP=2 ledwie wystaje z szumu. Liczniki potwierdzają mechanizm: moc na
kartę spada z 436 W (TP=1) do 111 W (TP=8), SM_ACTIVE z 0,665 do
0,053, a PCIe RX rośnie do 7,18 GB/s i we wszystkich scenariuszach
c≥8 — u Kimi i u Qwena — zatrzymuje się w paśmie 7,2–7,9 GB/s.
Ważne, jak to czytać: to NIE jest wysycenie łącza — nominalnie PCIe
Gen5 x16 przenosi ~64 GB/s w jedną stronę, używamy więc ~11%.
All-reduce składa się z wielu krótkich, synchronicznych rund, w
których dominują czas pojedynczej wymiany między kartami (na PCIe
~20 µs, na NVLink 2–9 µs) i czekanie na pozostałych uczestników —
ogranicza nas czas rundy, nie przepustowość rury. Interwencja P2P:
zgodnie z kryterium przyczynowości
brak efektu (−0,6%) wyklucza transport jako ograniczenie przy dwóch
kartach — koszt komunikacji rośnie z liczbą uczestników, nie z samego
istnienia łącza. Profile domykają obraz: przy c=1 komunikacja to
22,5% (nie dominuje — tam rządzi narzut hosta), pod obciążeniem
równoległym 83,9% — obie hipotezy prawdziwe, każda w swoim reżimie
pracy serwera.

---

## Slajd 13 — Krok 15: Sprawdź wniosek drugą, niezależną metodą

Status: ZAAKCEPTOWANY (2026-08-09)

Decyzje: rachunek jawnie na slajdzie; obie formy zbieżności; anomalia
c=16 tylko wzmianką na slajdzie, liczby w notes.

### Na slajdzie

> ## Krok 15: Sprawdź wniosek drugą, niezależną metodą
>
> Ta sama wielkość, dwie niezależne drogi pomiaru:
>
> **Droga 1 — bench po stronie klienta:** spadek przepustowości
> TP=2 → TP=4: 1 − 680/1404 = **52%**
>
> **Droga 2 — profil czasowy GPU:** udział komunikacji NCCL w kroku
> (TP=4, c=64): **53,3%**
>
> Rachunek krzyżowy: 680 ÷ (1 − 0,533) ≈ **1456 tok/s**,
> a zmierzone na TP=2: **1404 tok/s** — zgodność ~4%
>
> Dwie metody, jedna liczba → wniosek o komunikacji jest wiarygodny.
>
> Poza modelem została jedna zagadka (nietypowe zachowanie punktu
> c=16) — zarejestrowana i **zaparkowana**; poza zakresem tej
> prezentacji.

### Speaker notes

Zasada kroku 15: wniosek przyjmujemy dopiero wtedy, gdy dwie
niezależne drogi pomiarowe dają tę samą liczbę — tu metryki klienta
(`vllm bench serve`) i profil czasowy GPU (torch profiler), czyli
różne narzędzia patrzące na różne warstwy systemu. Logika rachunku
krzyżowego: jeżeli komunikacja zabiera 53,3% czasu kroku, to jej
usunięcie powinno podnieść przepustowość TP=4 do 680 ÷ (1−0,533) ≈
1456 tok/s; na TP=2, gdzie interwencja P2P pokazała koszt komunikacji
bliski zera, zmierzono 1404 tok/s — różnica ~4%. Zagadka c=16:
ITL 512 ms wobec 127 ms przy c=32 — cztery razy wolniej przy
mniejszym obciążeniu; powtórka daje 525 ms (±3%), więc to nie błąd
pomiaru, a żaden zmierzony zasób tego nie tłumaczy. Wartość
metodyczna parkowania: nie wszystko trzeba wyjaśnić natychmiast —
anomalię rejestrujemy z liczbami i datą, żeby nie zgubić jej z oczu;
jej wyjaśnienie wykracza poza zakres tej prezentacji.

---

## Slajd 14 — Kroki 16–17: Zbuduj model i policz zysk

Status: ZAAKCEPTOWANY (2026-08-09)

Decyzje: analogia furgonetki wycięta całkowicie; obie tabele (wejścia
i wyniki) na slajdzie; na slajdzie tylko wzór S_nvlink (S_ideal w
notes, w tabeli wyników kolumna zostaje); zastrzeżenie o s=0,839
z nietypowego punktu c=16 w notes.

### Na slajdzie

> ## Kroki 16–17: Zbuduj model i policz zysk
>
> Model z kroku 5 — teraz z liczbami z eksperymentów.
>
> Wejścia (zmierzone):
>
> | scenariusz | s — udział komunikacji | capture | podstawa pomiarowa |
> |---|---:|---:|---|
> | TP=2 | 0 | 1,0 | brak efektu interwencji P2P |
> | TP=4, c=1 | 0,148 | 1,0 | 1,56 / 10,54 ms (krzywa TP) |
> | TP=4, c=64 | 0,533 | 1,0 | profil czasowy Qwen |
> | TP=8, c=1 | 0,225 | 0,75 | profil czasowy Kimi |
> | TP=8, wysoka współbieżność | 0,839 | 0,75 | profil czasowy Kimi |
>
> capture = część komunikacji, którą przejmie NVLink (mostek 4-way
> łączy 4 karty w „wyspę"; przy 8 kartach część scaleń zostaje na PCIe)
>
> Prawo Amdahla dla NVLink o skończonej przepustowości:
>
> **S_nvlink = 1 / (1 − s × capture × (1 − 128/900))**
>
> (PCIe 128 → NVLink 900 GB/s: objęty składnik krótszy o ~86%,
> nie usunięty)
>
> Przewidywany zysk:
>
> | scenariusz | S_ideal (łącze idealne) | S_nvlink |
> |---|---:|---:|
> | TP=2 | 1,00× | 1,00× |
> | TP=4, c=1 | 1,17× | 1,15× |
> | TP=4, c=64 | 2,14× | **1,84×** |
> | TP=8, c=1 | 1,20× | 1,17× |
> | TP=8, wysoka współbieżność | 2,70× | **2,18×** |

### Speaker notes

Krok 16 w tym śledztwie to nie budowa nowego modelu, lecz kalibracja
wzoru, który prowadził nas od postawienia hipotez: każde `s` w tabeli
wejść pochodzi z konkretnego pomiaru — z krzywej TP albo z profilu
czasowego — i ma wskazaną podstawę. Współczynnik `capture` wynika
z geometrii mostków: grupa do czterech kart mieści się w jednej
wyspie NVLink (capture 1,0), przy ośmiu kartach część scaleń nadal
przechodzi między wyspami po PCIe — przyjęto 0,75. Wariant idealny,
`S_ideal = 1/(1 − s·capture)`, to górna granica dla łącza, które
usuwa całą objętą komunikację; wariant realny dodaje czynnik
1 − 128/900 = 0,858, bo NVLink nie zeruje czasu rund, tylko go skraca
proporcjonalnie do przepustowości (wartości nominalne z kart
katalogowych: 128 wobec 900 GB/s dwukierunkowo). Uczciwe zastrzeżenie
do konstrukcji modelu: stosunek przepustowości to uproszczenie —
realny mechanizm zysku to skrócenie czasu pojedynczej rundy
(opóźnienie wymiany i czekanie na uczestników), którego ten czynnik
nie modeluje wprost; zobaczymy konsekwencje przy konfrontacji
predykcji z pomiarem. Zastrzeżenie drugie:
s = 0,839 pochodzi z profilu punktu c=16, który oznaczyliśmy jako
nietypowy — nie reprezentuje wszystkich punktów wysokiej
współbieżności, więc wynik 2,18× traktujemy ostrożnie. Odczyt
decyzyjny modelu: zysk pojawia się tylko tam, gdzie komunikacja
dominuje krok — TP≥4 pod obciążeniem równoległym (1,84–2,18×);
dla pojedynczego klienta i dla TP=2 model przewiduje wartości poniżej
1,2× — czyli brak uzasadnienia zakupu w tych scenariuszach.

---

## Slajd 15 — Krok 18: Pre-rejestruj predykcje

Status: ZAAKCEPTOWANY (2026-08-09)

Decyzje: skrócona tabela (~8 wierszy); kolumna progów falsyfikacji
jawnie na slajdzie; bez motta u góry („nie edytuj po fakcie" w
notes); para custom all-reduce dodana jako predykcja już tutaj.

### Na slajdzie

> ## Krok 18: Pre-rejestruj predykcje
>
> Zapisane przed montażem mostków, z progami falsyfikacji:
>
> | pomiar | baseline (PCIe) | predykcja | próg falsyfikacji |
> |---|---:|---|---|
> | P2P w wyspie (GPU0↔GPU1) | ~25–50 GB/s | **> 100 GB/s** | < 60 → mostek nie działa |
> | NCCL busbw, 4 karty w wyspie | plateau 7,2–7,9 GB/s | **> 100 GB/s** | < 30 → NCCL nie wybrał NVLinka |
> | Qwen TP=4, c=64 | 680 tok/s | **~1430 tok/s** (2,1×) | < 850 → model zawyżony |
> | Kimi TP=8, c=32 | 285 tok/s | **~770 tok/s** (2,7×, górne oszac.) | < 400 → capture 0,75 zawyżony |
> | c=1 (oba modele) | Qwen ITL 10,54 ms; Kimi TPOT 8,7 ms | **zysk co najwyżej mały, ≤1,3×** (rządzi narzut hosta) | Qwen ITL < 8 ms lub Kimi TPOT < 5 ms → teza o narzucie upada |
> | PCIe RX przy c≥8 | plateau 7,2–7,9 GB/s | **wyraźny spadek** | brak spadku → NCCL nie używa mostków |
> | warning custom all-reduce (log vLLM) | aktywny u obu | **Qwen TP4: znika / Kimi TP8: zostaje** | inna para → mechanizm źle zrozumiany |

### Speaker notes

Predykcje wpisano do planu sesji przed fizycznym montażem mostków,
z adnotacją „nie zmieniaj po fakcie" — dzięki temu późniejsza
konfrontacja jest uczciwa: nie da się dopasować oczekiwań do wyniku.
Istota kroku 18 to kolumna progów — każda predykcja ma z góry
określoną wartość, przy której uznamy ją za obaloną, więc model jest
falsyfikowalny w sensie ścisłym. Predykcję Kimi traktujemy jako górne
oszacowanie: s=0,839 pochodzi z nietypowego punktu c=16, a capture
0,75 jest założeniem geometrycznym, nie pomiarem. Para warningów custom
all-reduce sprawdza zrozumienie mechanizmu, nie tylko liczb: vLLM
aktywuje własny, szybszy all-reduce tylko przy pełnej siatce NVLink
w grupie TP, sprawdzając każdą parę kart — przy mostkach 4+4 grupa
TP=4 w jednej wyspie ma pełną siatkę (warning powinien zniknąć),
a TP=8 przez dwie wyspy nie ma (para GPU0↔GPU4 bez linku — warning
powinien zostać mimo poprawnie działających mostków). Wiersz o PCIe
RX jest sygnałem niezależnym od benchmarków i logów NCCL — pochodzi
wprost z liczników sprzętowych.

---

## Slajd 16 — Krok 19 (a): Interwencja i weryfikacja mikro

Status: ZAAKCEPTOWANY (2026-08-09)

Decyzje: topologia PO (D1-PO) na slajdzie; weryfikacja mikro jako
wykres W4 (skala log); predykcje mikro pokazane jako odhaczenia.

### Na slajdzie

> ## Krok 19 (a): Interwencja — montaż i weryfikacja mikro
>
> Interwencja: mostki NVLink 4-way — dwie wyspy: GPU 0–3 i GPU 4–7
>
> [DIAGRAM D1-PO: topologia po montażu — pełna siatka NVLink wewnątrz
> każdej wyspy; między wyspami nadal PCIe/UPI]
>
> [WYKRES W4, skala log: P2P i NCCL busbw — w wyspie po montażu
> (132,8 oraz 185–333 GB/s) vs między wyspami (29,1 oraz
> 24,8–31,3 GB/s) vs plateau ery PCIe (7,2–7,9 GB/s)]
>
> Pierwsze odhaczenia tabeli predykcji:
>
> - ✓ P2P w wyspie: **132,8 GB/s** (predykcja: >100)
> - ✓ NCCL busbw w wyspie: **185–333 GB/s** (predykcja: >100)
> - ✓ kontrola cross-island: **29,1 GB/s — bez zmian** (predykcja:
>   bez zmian)
> - ✓ warning custom all-reduce: **Qwen TP4 zniknął / Kimi TP8
>   został** — para zgodna z predykcją

### Speaker notes

Krok 19 protokołu mówi: wykonaj zmianę i zmierz dokładnie to samo, co
przed nią — ale zanim uruchomimy benchmarki end-to-end, sprawdzamy
warstwę mikro: czy łącze fizycznie działa i czy system je widzi.
P2P w wyspie skacze z ~25–50 do 132,8 GB/s; kontrola negatywna — para
między wyspami zostaje przy 29,1 GB/s, co potwierdza, że mapa wysp
jest poprawna (wzrost na tej parze oznaczałby błąd w rozpoznaniu
topologii). NCCL busbw wewnątrz wyspy osiąga 185–333 GB/s wobec
plateau 7,2–7,9 z ery PCIe — dwa rzędy wielkości; grupa 2+2 rozpięta
przez obie wyspy daje tylko 24,8–31,3 GB/s, co pokazuje, że kolektyw
działa hierarchicznie, a nie płaskim pierścieniem — to empiryczne
wsparcie dla założenia capture z modelu. Bramka custom all-reduce
zamknęła się dokładnie po przewidzianej parze: warning zniknął u
Qwena (pełna siatka w wyspie przy TP=4; log potwierdza aktywację
kernela), a został u Kimi (TP=8 przez dwie wyspy — siatka niepełna,
mimo poprawnie działających mostków). Wszystkie predykcje warstwy
mikro zaliczone — dopiero teraz przechodzimy do pomiaru end-to-end.

---

## Slajd 17 — Krok 19 (b): Zmierz dokładnie to samo

Status: ZAAKCEPTOWANY (2026-08-09)

Decyzje: W5 z dwiema liniami odniesienia (predykcja + próg
falsyfikacji); c=1 jako osobny wiersz odhaczenia; analiza odchyleń od
predykcji w całości na slajdzie 18.

### Na slajdzie

> ## Krok 19 (b): Zmierz dokładnie to samo
>
> Te same benchmarki, ta sama konfiguracja — jedyna zmiana: mostki.
>
> [WYKRES W5: słupki przed/po — Qwen TP=4 c=64: 680 → 2022 tok/s;
> Kimi TP=8 c=32: 285 → 594 tok/s; na każdym słupku „po" dwie linie
> odniesienia: predykcja (~1430 / ~770) i próg falsyfikacji
> (850 / 400)]
>
> Odhaczenia progów:
>
> - ✓ Qwen TP=4, c=64: **2022 tok/s (2,97×)** — próg 850 przekroczony
> - ✓ Kimi TP=8, c=32: **594 tok/s (2,08×)** — próg 400 przekroczony
> - ✓ c=1: zysk mały — TPOT Qwen 4,00→3,21 ms (−20%), Kimi
>   8,7→7,44 ms (−15%) — w przewidzianym „≤1,3×", rządzi stały
>   narzut hosta
>
> Oba pomiary przechodzą progi. Jak dokładnie trafiły w predykcje —
> następny slajd.

### Speaker notes

Zasada kroku 19: mierzymy dokładnie te same benchmarki, na tej samej
konfiguracji silnika, którą mierzyliśmy przed interwencją — jedyną
zmienną są mostki, więc porównanie jest 1:1. Wyniki: Qwen TP=4 przy
c=64 przyspiesza z 680 do 2022 tok/s (2,97×), Kimi TP=8 przy c=32
z 285 do 594 tok/s (2,08×); przy pojedynczym kliencie TPOT spada
o ~15–20% — mieści się w przewidzianym „poniżej 1,3×" i potwierdza, że
w tym reżimie rządzi stały narzut hosta, którego szybsze łącze nie
usuwa. Wykres ma dwie linie odniesienia i czytamy go względem obu:
próg falsyfikacji mówi, czy model przeżył konfrontację, predykcja —
jak dokładnie trafił; oba słupki przechodzą progi, ocenę dokładności
robimy za chwilę. Kontekst decyzyjny wart odnotowania: optimum ery
PCIe wynosiło 1404 tok/s na TP=2 — TP=4 z NVLink (2022) przebija tę
wartość, więc konfiguracja czterokartowa przestała być karą.

---

## Slajd 18 — Krok 20: Analizuj błędy modelu — w obie strony

Status: ZAAKCEPTOWANY (2026-08-09; dopisane pochodzenie 0,75 i 0,62
na życzenie użytkownika)

Decyzje: układ sekwencyjny (Qwen, potem Kimi); oba wyjaśnienia Qwen
na slajdzie; profil 08-03 (61,1%) na slajdzie jako dowód mechanizmu;
liczby rozdzielania wkładu custom-AR w notes.

### Na slajdzie

> ## Krok 20: Analizuj błędy modelu — w obie strony
>
> Oba pomiary przeszły progi — a model pomylił się w obu kierunkach.
>
> **Qwen: 2,97× — ponad sufit uproszczonego modelu transfer-only
> (S_ideal 2,14×).** Dlaczego niedoszacował:
> - udział komunikacji z profilu zawierał także czekanie na inne
>   karty (peer-wait), a ono przy szybszym łączu kurczy się
>   ponadproporcjonalnie → model był oszacowaniem **dolnym**, nie
>   górnym
> - interwencja nie była pojedyncza: mostki przy okazji odblokowały
>   kernel custom all-reduce vLLM — **ukryta druga zmiana**
>
> **Kimi: 2,08× — poniżej predykcji (2,18–2,70×):**
> - implikowany capture = **0,62** zamiast założonego 0,75
>   (0,75 = 6 z 8 odcinków pierścienia all-reduce leży w wyspach;
>   0,62 = wartość wynikająca ze zmierzonego 2,08×) — dwa odcinki
>   między wyspami kosztują więcej czasu, niż wynosi ich udział w
>   liczbie odcinków
>
> Dowód mechanizmu — profil po interwencji: udział NCCL w kroku Kimi
> **83,9% → 61,1%**; arytmetycznie **cały zysk 2,08× przyszedł ze
> skrócenia komunikacji**, a implikowany capture 0,62 potwierdza się
> niezależnie.
>
> Błędy modelu w obu kierunkach uczą więcej niż trafienia.

### Speaker notes

Krok 20 nie kończy się na „przeszło / nie przeszło" — analizujemy
odchylenia w obu kierunkach, bo to one korygują rozumienie mechanizmu.
Błąd w górę u Qwena ma dwie przyczyny: po pierwsze, model traktował
czas kerneli NCCL jako czysty transfer, a profil wlicza do NCCL także
czekanie na karty, które przy krótszej rundzie znika szybciej niż
proporcjonalnie — wniosek przenośny: udział komunikacji z profilu to
górna granica czasu transferu, więc zbudowany na nim model daje dolne
oszacowanie zysku. Po drugie, kontrola pojedynczości interwencji:
vLLM sam aktywował własny kernel all-reduce, gdy zobaczył pełną
siatkę — zmiana sprzętowa pociągnęła za sobą zmianę software'ową.
Późniejsza próba rozdzielenia tych wkładów: przy c=64 nierozstrzygnięta
(porównania dają przedział 1,0–1,2× przy szumie ±6% pojedynczego
biegu), przy c=1 wkład kernela realny, około +8% na TPOT. Błąd w dół u Kimi — skąd obie liczby: 0,75 przyjęto z geometrii
ring all-reduce (karty tworzą logiczny pierścień 0→1→…→7→0,
komunikacja rozkłada się równomiernie na odcinki; przy wyspach 0–3
i 4–7 sześć z ośmiu odcinków leży wewnątrz wysp → 6/8 = 0,75);
0,62 to wartość odwrócona z pomiaru — podstawiając zmierzone 2,08×
i s = 0,839 do wzoru, wychodzi capture ≈ 0,62. Fizyczna
interpretacja rozjazdu: runda scalenia jest synchroniczna, więc idzie
w tempie najwolniejszego ogniwa — dwa odcinki między wyspami (nadal
PCIe) zabierają większą część CZASU rundy, niż wynosi ich udział w
LICZBIE odcinków; widać to też w pomiarze busbw grupy 2+2 przez
wyspy (24,8–31,3 GB/s wobec 185–333 w wyspie). Pomiar end-to-end
i profil dają zgodnie 0,62 — dwie niezależne drogi znów spotykają
się na jednej liczbie, tym razem przy analizie błędu.

---

## Slajd 19 — WYCIĘTY (zagadka c=16)

Status: WYCIĘTY (2026-08-09) — decyzja użytkownika: temat zbyt śliski
(mamy atrybucję interwencyjną do warstwy transportu, ale nie mamy
wyjaśnienia mechanizmu, dlaczego patologiczny był akurat punkt c=16).
Konsekwentnie: wiersz c=16 usunięty z tabeli predykcji (slajd 15),
wątek zagadki na slajdzie 13 zamknięty jako „poza zakresem
prezentacji". Wykres W6 nieużywany. Checklista przesuwa się na
slajd 19.

---

## Slajd 19 — Protokół badania: do zabrania

Status: ZAAKCEPTOWANY (2026-08-09)

Decyzje: checklista skrócona do 10 haseł (kondensacja 20 kroków);
bez sekcji „co dalej"; prezentację kończy sama checklista +
podziękowanie; bez danych kontaktowych i linków.

### Na slajdzie

> ## Protokół badania — do zabrania
>
> 1. Zauważ anomalię i zanotuj ją, zanim cokolwiek zmienisz.
> 2. Sprawdź, co naprawdę mierzy Twoja metryka.
> 3. Nasycenie mierz właściwymi licznikami; wyniki zapisuj z datą
>    i konfiguracją.
> 4. Wypisz hipotezy — każda z przewidywanym śladem w danych.
> 5. Najpierw szybkie eliminacje: z danych, które już masz.
> 6. Eksperymenty: jedna zmiana naraz, w kolejności kosztu.
> 7. Skalibruj szum, zanim nazwiesz różnicę efektem.
> 8. Werdykt zawsze z zakresem ważności.
> 9. Wniosek sprawdź drugą, niezależną metodą.
> 10. Zbuduj model, pre-rejestruj predykcje z progami — a po zmianie
>     analizuj błędy modelu w obie strony.
>
> Dziękuję.

### Speaker notes

Klamra na koniec: te dziesięć punktów to skondensowany szkielet
całej prezentacji — każdy z nich ma za sobą pokazany dziś przykład
z pomiarów: metrykę, która nie mierzyła tego, co myśleliśmy;
hipotezę obaloną za darmo; interwencje po jednej zmianie; pasmo
szumu, do którego odnosiliśmy różnice; dwie niezależne metody
spotykające się na jednej liczbie; model, który pomylił się w obie
strony i właśnie dlatego czegoś nas nauczył. Protokół jest ogólny —
nie zależy od vLLM, NVLink ani konkretnego serwera; zmienia się
tylko treść hipotez i liczniki. Dziękuję za uwagę.
Profil pokazuje też, że komunikacja została skompresowana ~2,9×
przy praktycznie stałej reszcie kroku — stąd „cały zysk z
komunikacji"; skoro NCCL to nadal ~61% kroku, zostaje przestrzeń na
dalszą poprawę — wrócimy do tego w „co dalej".