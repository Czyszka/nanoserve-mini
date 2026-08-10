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

Ten tytuł to prawdziwy odczyt z naszego serwera. Osiem kart H200 pokazywało 100% obciążenia — a realnie pobierały jedną trzecią mocy. Chcę pokazać, jak krok po kroku doszliśmy do wyjaśnienia tej sytuacji: od pierwszego momentu, w którym było widać, że coś się nie zgadza, przez hipotezy i eksperymenty, aż po decyzję o zakupie sprzętu — popartą twardymi dowodami pomiarowymi. Prezentacja będzie miała formę studium przypadku i można ją potraktować jako przedstawienie prostego protokołu badań wydajności, który można powtórzyć we własnym środowisku.

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

Zanim przejdę do samego badania, krótko o środowisku. Pracujemy na serwerze laboratoryjnym: dwa Xeony Gold 6530 i osiem kart H200 NVL po 143 GB, spiętych magistralą PCIe 5.0. Całość działa na vLLM-ie, w kontenerach Docker. Główny model to Kimi-K2.6 — bilion parametrów, same wagi zajmują 554 GB, więc nie da się go uruchomić na mniej niż ośmiu kartach. Z tego powodu działa u nas wyłącznie na TP=8, z dekodowaniem spekulacyjnym Eagle3. Drugi model, Qwen3.6-35B, służy nam jako narzędzie badawcze: mieści się na jednej karcie, więc możemy robić pomiary przy TP=1, 2 i 4 — w badaniu uruchamialiśmy go też na TP=8. Od razu zastrzegę, że TP=4 czy TP=8 dla modelu tej wielkości to nie są poprawne konfiguracje produkcyjne — używamy ich tylko po to, żeby zbadać skalowanie.

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

Podczas benchmarków, które obciążały wszystkie osiem kart, nvidia-smi pokazywał 100% GPU-Util, a jednocześnie karty pobierały po 111–185 W, przy limicie 600 W — 111 W to średnia dla Qwena, 185 W średnia dla Kimi. Na wykresie widać przebieg mocy w całym oknie pomiarowym z oryginalnych badań — ten stan utrzymywał się przez cały czas, więc to nie był chwilowy przestój między zadaniami. I to jest pierwszy krok protokołu: nie przechodzimy obok takiej obserwacji, tylko notujemy ją, zanim cokolwiek zaczniemy zmieniać.

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

Zacznijmy od tego, co ta metryka w ogóle mierzy. Formalna definicja z dokumentacji NVIDIA — pole utilization.gpu w NVML — mówi, że GPU-Util to procent czasu w oknie próbkowania, w którym na karcie wykonywał się co najmniej jeden kernel. Kernel to pojedynczy program uruchamiany na GPU: jedno mnożenie macierzy, jedna operacja na pamięci albo jedna operacja komunikacji zbiorowej. I tu jest sedno: metryka nie rozróżnia, co ten kernel robi. Kernel NCCL, który w pętli czeka na dane od innej karty, podnosi zajętość dokładnie tak samo jak kernel, który liczy mnożenie macierzy. Sto procent GPU-Util mówi więc tylko tyle, że kolejka karty nie była pusta. Kolejka to bufor zadań — strumienie CUDA — z którego karta pobiera kolejne kernele; dopóki czeka w niej choć jeden, karta zgłasza zajętość. O tym, czy jednostki obliczeniowe albo interfejs pamięci są rzeczywiście nasycone, ta metryka nie mówi nic.

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

Do pomiaru nasycenia używamy DCGM, czyli narzędzia NVIDIA do monitoringu kart. Konkretnie: dcgmi dmon, uruchomione z poziomu hosta. Próbkowanie było ustawione na jedną sekundę, więc nie zmienialiśmy konfiguracji serwera, vLLM-a ani kontenerów. To był pomiar obserwacyjny: patrzymy, co robi sprzęt podczas normalnej pracy modelu.
Dwa słowa o licznikach. SM_ACTIVE mówi, przez jaką część czasu aktywne były multiprocesory strumieniowe GPU, czyli bloki wykonujące pracę na karcie. To nie jest to samo co „ile czasu GPU liczyło macierze”. Aktywny może być też kernel komunikacyjny albo kernel czekający na dane. Dlatego SM_ACTIVE traktujemy jako licznik aktywności SM-ów, a nie jako czysty udział obliczeń modelu.
DRAM_ACTIVE dotyczy interfejsu pamięci HBM. Pokazuje, przez jaką część czasu aktywny był ruch do albo z pamięci karty. Jeżeli dekodowanie byłoby ograniczone przepustowością HBM, spodziewalibyśmy się wysokich wartości tego licznika, rzędu kilkudziesięciu procent bliżej górnego zakresu, a nie pojedynczych procentów.
Mierzyliśmy Kimi-K2.6 w konfiguracji produkcyjnej: TP=8, EAGLE3 włączone, osiem kart H200. Pomiar podzieliliśmy na trzy okna. Pierwsze to stan spoczynkowy: model załadowany, ale bez zapytań. Tam SM_ACTIVE i DRAM_ACTIVE wyszły 0,000, więc tło nie zakłócało pomiaru. Drugie okno to jeden klient, trzecie to 64 klientów. Obciążenie generował vllm bench serve, a wyniki uśredniamy na jedną kartę z aktywnej części okna.
I teraz kluczowy wynik: przy GPU-Util raportowanym jako 100% karty wcale nie były blisko nasycenia. Pobór mocy wynosił około 170–199 W na kartę przy limicie 600 W. SM_ACTIVE było w okolicach 20%, DRAM_ACTIVE tylko 7–9%, a PCIe przenosiło około 6–8 GB/s. Innymi słowy: GPU formalnie cały czas „coś robiło”, ale żaden z obserwowanych zasobów nie pracował blisko granicy.
Ważne zastrzeżenie: to nie jest ogólna cecha H200 ani każdego modelu LLM. To profil konkretnej konfiguracji: Kimi-K2.6 rozłożony na osiem kart. Dla porównania testowy Qwen uruchomiony na jednej karcie przy c=64 miał dużo wyższe liczniki: SM_ACTIVE około 0,68 i DRAM_ACTIVE około 0,39. Problem nie polega więc na tym, że H200 nie da się obciążyć. Problem pojawia się w tej wielokartowej konfiguracji, gdzie czas kroku zaczyna znikać w komunikacji i synchronizacji między kartami.

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

Hipotezy nie są dowolne — wynikają wprost z rozkładu czasu kroku. Każdy krok generowania składa się z trzech części: stałego narzutu silnika F_host, komunikacji — czyli liczby synchronicznych rund scalania razy czas jednej rundy, zależny od łącza i liczby kart — oraz obliczeń i pamięci, W_silicon. Te trzy składniki sumują się do całego kroku, więc przestrzeń hipotez jest kompletna z samej konstrukcji — nie ma czwartego miejsca, w którym mógłby ginąć czas. H4 to wariant topologiczny H2: pytamy nie „czy komunikacja", tylko „która trasa". Wyjaśnię dwa pojęcia z tabeli. All-reduce to synchroniczne scalanie wyników częściowych ze wszystkich kart — przy podziale modelu trzeba scalać mniej więcej dwa razy na warstwę, co przy 61 warstwach Kimi daje około 122 scalenia w każdym kroku, i żadna karta nie ruszy dalej, dopóki ostatnia nie skończy. UPI z kolei to łącze między dwoma procesorami serwera — karty podpięte pod różne CPU komunikują się właśnie przez nie. I najważniejsza rzecz w kroku szóstym: do każdej hipotezy z góry zapisujemy ślad, jaki musiałaby zostawić w danych. Dzięki temu pomiar będzie rozstrzygał, a nie ilustrował.

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

Krok siódmy to szybkie eliminacje. Zanim uruchomimy jakikolwiek eksperyment, sprawdzamy, które hipotezy padają już od danych zebranych w krokach 3 i 4. H1 miała z góry zapisany ślad: aktywność interfejsu pamięci na poziomie 0,70–0,90. Pomiar pokazuje 0,070–0,093 — o rząd wielkości mniej, i to stabilnie przez całe okno obciążenia. Trzeba uczciwie dodać, że próbkujemy co sekundę, więc chwilowe skoki wewnątrz kroku dekodowania się uśredniają — pełną charakterystyką pamięci HBM to nie jest. Ale przy różnicy rzędu wielkości do werdyktu wystarcza. Sam werdykt zapisujemy w formacie, który będzie wracał do końca prezentacji: predykcja, pomiar i rozstrzygnięcie z zakresem ważności — w tym przypadku: obalona dla badanych scenariuszy pracy serwera. Ta hipoteza nie kosztowała nas ani jednego dodatkowego pomiaru. Zostały trzy — i każda wymaga już eksperymentu.

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

Plan eksperymentów ma jedną żelazną regułę: zmieniamy dokładnie jeden element układu naraz, a resztę konfiguracji zamrażamy — inaczej wynik nie wskaże przyczyny. Kolejność wyznacza koszt. H4 to jeden dodatkowy bieg, H3 — jeden profil i trzy przełączniki silnika, a H2 wymaga osobnego startu silnika dla każdej wartości TP, więc jest najdroższa. Dane będziemy zbierać z trzech niezależnych źródeł. Pierwsze to metryki po stronie klienta z vllm bench serve — TPOT, ITL i przepustowość, każdy pomiar po rozgrzewce. Drugie to liczniki sprzętowe DCGM — dcgmi dmon, próbkowanie co sekundę, uśrednianie tylko w oknie benchmarku. Trzecie to profil czasowy z torch profilera, który rozkłada krok na komunikację, obliczenia i przerwy. Czy te trzy źródła się zgadzają, sprawdzimy osobno w kroku 15. Została jeszcze kalibracja szumu. Warianty eksperymentów i tak wymagały restartów silnika, więc wykorzystaliśmy je do oszacowania zmienności pomiaru — przy TP=2 wyszło około ±0,4 ms między niezależnymi uruchomieniami. Każdą przyszłą różnicę będziemy najpierw odnosić do tego pasma, zanim nazwiemy ją efektem.

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

Konstrukcja tego eksperymentu jest prosta: ta sama liczba kart, zmieniamy wyłącznie trasę komunikacji. Rozmieszczenie wymuszamy przez CUDA_VISIBLE_DEVICES, a poprawność kontrolujemy poborem mocy — karty, które nie biorą udziału, zostają na spoczynkowych ~70 W, więc mamy pewność, że obciążenie szło na wskazane GPU. Teraz wyniki. Przy dwóch kartach wariant przez UPI wyszedł 9,13 ms wobec 9,91 ms — na pierwszy rzut oka szybszy. Ale to pojedynczy pomiar przy zmienności ±0,4 ms między niezależnymi startami, więc czytamy go wyłącznie jako brak kary, a nie jako przewagę UPI. Przy czterech kartach pod c=64 obraz jest taki sam. Werdykt: H4 obalona dla badanych układów w tym serwerze — najgroźniejsza topologicznie trasa nie kosztuje nic mierzalnego. I to jest ważny wynik kierunkowy. Skoro rodzaj trasy nie boli, podejrzenie przesuwa się na liczbę uczestników komunikacji i na stały narzut — czyli dokładnie na H2 i H3, które badamy dalej, wciąż w kolejności kosztu.

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
[WYKRES W3: dwa słupki skumulowane — rozkład czasu profilu, Kimi TP=8:
c=1: 63% bez żadnej operacji GPU | 22,5% komunikacja NCCL | 9,1% obliczenia | 5,6% inne;
c=16: 10% bez żadnej operacji GPU | 83,9% komunikacja NCCL | 4,6% obliczenia | ~1,5% inne]
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

Na tym slajdzie debiutuje trzecie źródło danych — profil czasowy z torch profilera, czyli pełna oś czasu operacji GPU. Najpierw kontrola rzetelności: przebieg profilowany i nieprofilowany różnią się o około 5%, więc profiler nie zniekształca obrazu. W profilu pojedynczego zapytania największym składnikiem jest czas, w którym nie dzieje się żadna operacja GPU — 63%. To właśnie stały narzut hosta. Drugi słupek pokazuje, że to obraz tylko tego reżimu: pod obciążeniem, przy c=16, czas bez operacji GPU spada do 10%, a krok przejmuje komunikacja — do tego wrócimy przy H2. Tutaj skupiamy się na pojedynczym kliencie. Interwencje robimy na modelu testowym przy TP=1, gdzie komunikacji nie ma wcale, więc wszystkie koszty można przypisać wyłącznie hostowi. W tabeli są dwie metryki i różnica między nimi jest ważna. Czas kroku podajemy jako medianę ITL, czyli odstępu między kolejnymi porcjami tokenów zwracanymi przez serwer. TPOT z kolei to średni czas przypadający na jeden wygenerowany token. Przy spekulacji MTP jeden krok może zaakceptować więcej niż jeden token — dlatego TPOT może zostać podobny, nawet gdy sam krok, mierzony przez ITL, się wydłuża. I stąd najciekawszy wiersz tabeli: wyłączenie spekulacji skraca krok z 8,93 do 5,36 ms, ale taki krok daje jeden token zamiast średnio 2,6. Na pojedynczy token spekulacja wygrywa — TPOT 3,39 wobec 5,36 ms — a jej obsługa kosztuje 3,57 ms, czyli 40% kroku. Wariant eager działa inaczej: nie rozkłada kroku, tylko ujawnia koszt, którego nasza konfiguracja na co dzień unika. CUDA Graphs to mechanizm, który nagrywa sekwencję kerneli i odtwarza ją jednym poleceniem; bez niego krok rośnie do 55,1 ms przy SM_ACTIVE 0,009 — karta niemal wyłącznie czeka na polecenia hosta. Governor CPU w trybie performance nie zmienia nic — oszczędzanie energii zostaje uniewinnione. Werdykt: H3 potwierdzona dla pojedynczego klienta.

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

Składnik N_rounds razy r ma dwie części o różnym pochodzeniu. N_rounds wynika z architektury modelu: po bloku uwagi i po bloku FFN/MoE trzeba scalić wyniki częściowe, czyli mniej więcej dwa razy na warstwę — przy 61 warstwach Kimi to około 122 obowiązkowe scalenia w każdym kroku. r to czas jednej rundy — zależy od łącza i rośnie z liczbą uczestników. Samo scalanie wykonuje biblioteka NCCL. Punktem odniesienia jest ring all-reduce: karty tworzą logiczny pierścień, redukcja i rozesłanie wyniku to 2(N−1) kroków, a w każdej rundzie każda karta czeka na pozostałe. NCCL dobiera wariant algorytmu do każdego wywołania. Ważny szczegół dla interpretacji: na tym serwerze sprzętowo przyspieszane ścieżki scalania były nieaktywne. Własny all-reduce vLLM-a był wyłączony, bo nie jest obsługiwany dla więcej niż dwóch kart w konfiguracji czysto PCIe, a multicast NVLS był niedostępny. Scala więc standardowe NCCL po PCIe. Sam eksperyment to krzywa TP na modelu testowym. TP=1 działa bez żadnej komunikacji i jest punktem odniesienia — każdą dodatkową milisekundę kroku przy TP=2, 4 i 8 można przypisać wyłącznie zrównolegleniu. Przewidywanie zapisujemy przed pomiarem — na następnym slajdzie skonfrontujemy je z danymi.

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

Najpierw krzywa przepustowości. TP=2 daje plus 17% względem jednej karty — to 58% ideału. Od TP=4 wynik spada poniżej pojedynczej karty, a TP=8 osiąga 21% tego, co jedna karta, przy efektywności skalowania 2,7%. Przyrosty czasu kroku odnosimy do pasma szumu ±0,4 ms: +1,56 ms przy TP=4 to cztery pasma, +5,18 ms przy TP=8 to trzynaście — to są efekty realne. Natomiast +0,93 ms przy TP=2 ledwie wystaje z szumu. Liczniki potwierdzają mechanizm. Moc na kartę spada z 436 W przy TP=1 do 111 W przy TP=8, SM_ACTIVE z 0,665 do 0,053, a PCIe RX rośnie do 7,18 GB/s — i we wszystkich scenariuszach c≥8, u Kimi i u Qwena, zatrzymuje się w paśmie 7,2–7,9 GB/s. I tu ważna rzecz: to nie jest wysycenie łącza. Nominalnie PCIe Gen5 x16 przenosi około 64 GB/s w jedną stronę, używamy więc jakichś 11%. All-reduce to wiele krótkich, synchronicznych rund, w których dominują dwie rzeczy: czas pojedynczej wymiany między kartami — na PCIe około 20 µs, na NVLinku 2–9 µs — i czekanie na pozostałych uczestników. Ogranicza nas czas rundy, nie przepustowość rury. Do tego interwencja P2P: brak efektu, minus 0,6%, zgodnie z kryterium przyczynowości wyklucza transport jako ograniczenie przy dwóch kartach. Koszt komunikacji rośnie z liczbą uczestników, a nie z samego istnienia łącza. Na koniec tabela profili — trzy wiersze, dwa reżimy pracy. Pierwszy wiersz to Kimi przy pojedynczym kliencie: 63% kroku bez żadnej operacji GPU, komunikacja 22,5%, obliczenia 9,1%. W liczbach bezwzględnych NCCL zajmuje 1,14 s z 5,06 s profilu. Ten reżim ogranicza stały narzut kroku — scheduler, uruchamianie kerneli, synchronizacje, obsługa spekulacji, sampling. Komunikacja istnieje, ale ginie na tle pustych przerw. Drugi wiersz to ten sam Kimi pod obciążeniem, przy c=16 — i różnica między 22,5% a 83,9% nie oznacza, że model nagle wykonuje inną matematykę. Zmienił się reżim pracy. Silnik ma więcej sekwencji naraz, więc lepiej wypełnia krok: przerwy spadają z 63% do 10%, narzut hosta się amortyzuje. I wtedy na wierzch wychodzi prawdziwe ograniczenie — osiem kart musi po każdej części warstwy zsynchronizować wyniki. Przy większym batchu kolektywy są większe, a na PCIe dochodzi czekanie kart na siebie; profiler liczy ten czas jako NCCL, bo kernel NCCL cały czas trwa, nawet jeśli część tego czasu to peer-wait. Stąd 83,9%. Jedno zastrzeżenie: c=16 to nasz nietypowy punkt pomiarowy — ITL 512–525 ms, niska moc, niskie SM_ACTIVE, a przy c=32 serwer zachowuje się już inaczej. Uczciwie mówimy więc: profil c=16 szczególnie mocno ujawnił koszt komunikacji, a nie: od c=16 zawsze jest 84% NCCL. Trzeci wiersz pokazuje, że mechanizm nie jest osobliwością Kimi: Qwen na TP=4 przy c=64 ma komunikację 53,3%. Obie hipotezy są więc prawdziwe, każda w swoim reżimie: przy c=1 — narzut hosta, pod obciążeniem równoległym przy TP≥4 — komunikacja.

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

Krok 15 ma prostą zasadę: wniosek przyjmujemy dopiero wtedy, gdy dwie niezależne drogi pomiarowe dają tę samą liczbę. Tutaj to metryki klienta z vllm bench serve i profil czasowy GPU z torch profilera — różne narzędzia, patrzące na różne warstwy systemu. Pierwsza droga to czysty bench. Przy przejściu z TP=2 na TP=4 przepustowość spada z 1404 do 680 tokenów na sekundę; 680 przez 1404 to około 48%, czyli TP=4 zachowuje niecałą połowę wydajności — 52% ginie. Jeżeli tę stratę rzeczywiście powoduje komunikacja, to druga, niezależna droga — profil czasowy — powinna pokazać podobny udział komunikacji w kroku. I pokazuje: 53,3%. Rachunek krzyżowy domyka sprawdzenie: skoro komunikacja zabiera 53,3% czasu kroku, to jej usunięcie powinno podnieść przepustowość TP=4 do 680 podzielone przez 1 minus 0,533, czyli około 1456 tokenów na sekundę. A na TP=2, gdzie interwencja P2P pokazała koszt komunikacji bliski zera, zmierzyliśmy 1404. Różnica około 4%. Dwie metody, jedna liczba — wniosek o komunikacji jest wiarygodny. Została jeszcze zagadka punktu c=16: ITL 512 ms wobec 127 ms przy c=32, czyli cztery razy wolniej przy mniejszym obciążeniu. Powtórka daje 525 ms, w granicach ±3%, więc to nie jest błąd pomiaru — a żaden zmierzony zasób tego nie tłumaczy. I tu jest wartość metodyczna parkowania: nie wszystko trzeba wyjaśnić natychmiast. Anomalię rejestrujemy z liczbami i datą, żeby nie zgubić jej z oczu — jej wyjaśnienie wykracza poza zakres tej prezentacji.

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

Krok 16 w tym śledztwie to nie jest budowa nowego modelu — to kalibracja wzoru, który prowadzi nas od momentu postawienia hipotez. Każde s w tabeli wejść pochodzi z konkretnego pomiaru, z krzywej TP albo z profilu czasowego, i ma wskazaną podstawę. Współczynnik capture bierze się z geometrii mostków: grupa do czterech kart mieści się w jednej wyspie NVLink, więc capture wynosi 1,0. Przy ośmiu kartach część scaleń nadal przechodzi między wyspami po PCIe — przyjęliśmy 0,75. Wariant idealny, S_ideal równe 1 przez 1 minus s razy capture, to górna granica dla łącza, które całą objętą komunikację po prostu usuwa. Wariant realny dodaje czynnik 1 minus 128 przez 900, czyli 0,858 — bo NVLink nie zeruje czasu rund, tylko skraca go proporcjonalnie do przepustowości. 128 i 900 GB/s to wartości nominalne z kart katalogowych. Do konstrukcji modelu mamy dwa uczciwe zastrzeżenia. Pierwsze: stosunek przepustowości to uproszczenie. Realny mechanizm zysku to skrócenie pojedynczej rundy — opóźnienia wymiany i czekania na uczestników — a tego ten czynnik wprost nie modeluje. Konsekwencje zobaczymy przy konfrontacji predykcji z pomiarem. Drugie: s równe 0,839 pochodzi z profilu punktu c=16, który oznaczyliśmy jako nietypowy — nie reprezentuje wszystkich punktów wysokiej współbieżności, więc wynik 2,18× traktujemy ostrożnie. I na koniec odczyt decyzyjny. Zysk pojawia się tylko tam, gdzie komunikacja dominuje krok, czyli przy TP≥4 pod obciążeniem równoległym: od 1,84 do 2,18 razy. Dla pojedynczego klienta i dla TP=2 model przewiduje mniej niż 1,2× — w tych scenariuszach zakup nie ma uzasadnienia.

---

## Slajd 15 — Krok 18: Pre-rejestruj predykcje

Status: ZAAKCEPTOWANY (2026-08-09)

Decyzje: skrócona tabela (~8 wierszy); kolumna progów falsyfikacji
jawnie na slajdzie; bez motta u góry („nie edytuj po fakcie" w
notes); para custom all-reduce dodana jako predykcja już tutaj.
2026-08-10: predykcje end-to-end ujednolicone do wariantu S_nvlink
(1,84× / 2,18×) — zgodnie z wykresem W5 (slajd 17) i analizą błędów
(slajd 18); progi falsyfikacji bez zmian.

### Na slajdzie

> ## Krok 18: Pre-rejestruj predykcje
>
> Zapisane przed montażem mostków, z progami falsyfikacji:
>
> | pomiar | baseline (PCIe) | predykcja | próg falsyfikacji |
> |---|---:|---|---|
> | P2P w wyspie (GPU0↔GPU1) | ~25–50 GB/s | **> 100 GB/s** | < 60 → mostek nie działa |
> | NCCL busbw, 4 karty w wyspie | plateau 7,2–7,9 GB/s | **> 100 GB/s** | < 30 → NCCL nie wybrał NVLinka |
> | Qwen TP=4, c=64 | 680 tok/s | **~1250 tok/s** (S_nvlink 1,84×) | < 850 → model zawyżony |
> | Kimi TP=8, c=32 | 285 tok/s | **~620 tok/s** (S_nvlink 2,18×, górne oszac.) | < 400 → capture 0,75 zawyżony |
> | c=1 (oba modele) | Qwen ITL 10,54 ms; Kimi TPOT 8,7 ms | **zysk co najwyżej mały, ≤1,3×** (rządzi narzut hosta) | Qwen ITL < 8 ms lub Kimi TPOT < 5 ms → teza o narzucie upada |
> | PCIe RX przy c≥8 | plateau 7,2–7,9 GB/s | **wyraźny spadek** | brak spadku → NCCL nie używa mostków |
> | warning custom all-reduce (log vLLM) | aktywny u obu | **Qwen TP4: znika / Kimi TP8: zostaje** | inna para → mechanizm źle zrozumiany |

### Speaker notes

Te predykcje wpisaliśmy do planu sesji przed fizycznym montażem mostków, z adnotacją „nie zmieniaj po fakcie". Dzięki temu późniejsza konfrontacja jest uczciwa — nie da się dopasować oczekiwań do wyniku. Istotą kroku 18 jest kolumna progów: każda predykcja ma z góry określoną wartość, przy której uznamy ją za obaloną. Model jest więc falsyfikowalny w ścisłym sensie. Predykcję dla Kimi traktujemy jako górne oszacowanie — s równe 0,839 pochodzi z nietypowego punktu c=16, a capture 0,75 to założenie geometryczne, nie pomiar. Osobno warto omówić parę warningów custom all-reduce, bo ona sprawdza zrozumienie mechanizmu, a nie tylko liczby. vLLM aktywuje własny, szybszy all-reduce tylko wtedy, gdy w grupie TP każda para kart ma bezpośredni link NVLink. Przy mostkach 4+4 grupa TP=4 mieści się w jednej wyspie i ma pełną siatkę — więc warning powinien zniknąć. Grupa TP=8 jest rozpięta przez dwie wyspy i pełnej siatki nie ma — choćby para GPU0–GPU4 zostaje bez linku — więc warning powinien zostać, mimo poprawnie działających mostków. Jeżeli wyjdzie inna para wyników, znaczy to, że źle rozumiemy mechanizm. I jeszcze wiersz o PCIe RX: to sygnał niezależny od benchmarków i od logów NCCL, bo pochodzi wprost z liczników sprzętowych.

---

## Slajd 16 — Krok 19 (a): Interwencja i weryfikacja mikro

Status: ZAAKCEPTOWANY (2026-08-09)

Decyzje: topologia PO (D1-PO) na slajdzie; weryfikacja mikro jako
wykres W4 (skala log); predykcje mikro pokazane jako odhaczenia.

### Na slajdzie

> ## Krok 19 (a): Interwencja — montaż i weryfikacja
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

Krok 19 protokołu mówi: wykonaj zmianę i zmierz dokładnie to samo, co przed nią. Ale zanim uruchomimy benchmarki end-to-end, sprawdzamy warstwę mikro — czy łącze fizycznie działa i czy system je widzi. P2P wewnątrz wyspy skacze z około 25–50 do 132,8 GB/s. Do tego kontrola negatywna: para między wyspami zostaje przy 29,1 GB/s. To potwierdza, że mapa wysp jest poprawna — wzrost na tej parze oznaczałby, że źle rozpoznaliśmy topologię. NCCL busbw wewnątrz wyspy osiąga 185–333 GB/s wobec plateau 7,2–7,9 z ery PCIe — dwa rzędy wielkości. A grupa 2+2 rozpięta przez obie wyspy daje tylko 24,8–31,3 GB/s. To pokazuje, że kolektyw działa hierarchicznie, a nie płaskim pierścieniem — i empirycznie wspiera założenie capture z modelu. Zamknęła się też bramka custom all-reduce, dokładnie po przewidzianej parze. U Qwena warning zniknął — TP=4 ma pełną siatkę w wyspie, a log potwierdza aktywację kernela. U Kimi został, bo TP=8 przez dwie wyspy pełnej siatki nie ma, mimo poprawnie działających mostków. Wszystkie predykcje warstwy mikro zaliczone. Dopiero teraz przechodzimy do pomiaru end-to-end.

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
> odniesienia: predykcja (~1250 / ~620) i próg falsyfikacji
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

Zasada kroku 19 jest prosta: mierzymy dokładnie te same benchmarki, na tej samej konfiguracji silnika, co przed interwencją. Jedyną zmienną są mostki, więc porównanie jest jeden do jednego. Teraz wyniki. Qwen na TP=4 przy c=64 przyspiesza z 680 do 2022 tokenów na sekundę — 2,97 razy. Kimi na TP=8 przy c=32 z 285 do 594 — 2,08 razy. A przy pojedynczym kliencie TPOT spada o jakieś 15–20%, czyli mieści się w przewidzianym „poniżej 1,3×" — i potwierdza, że w tym reżimie rządzi stały narzut hosta, którego szybsze łącze nie usuwa. Wykres ma dwie linie odniesienia i czytamy go względem obu. Próg falsyfikacji mówi, czy model przeżył konfrontację. Predykcja mówi, jak dokładnie trafił. Oba słupki przechodzą progi; ocenę dokładności zrobimy za chwilę. I jeszcze jedna rzecz, ważna decyzyjnie: optimum ery PCIe to było 1404 tok/s na TP=2. TP=4 z NVLinkiem daje 2022, czyli przebija tę wartość — konfiguracja czterokartowa przestała być karą.

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
Qwen: 2,97× — znacznie ponad predykcję (S_nvlink 1,84×), ponad nawet sufit łącza idealnego (S_ideal 2,14×). Dlaczego niedoszacował:
> - udział komunikacji z profilu zawierał także czekanie na inne
>   karty (peer-wait), a ono przy szybszym łączu kurczy się
>   ponadproporcjonalnie → model był oszacowaniem **dolnym**, nie
>   górnym
> - interwencja nie była pojedyncza: mostki przy okazji odblokowały
>   kernel custom all-reduce vLLM — **ukryta druga zmiana**
>
> **Kimi: 2,08× — tuż poniżej predykcji (S_nvlink 2,18×):**
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

Krok 20 nie kończy się na „przeszło albo nie przeszło". Analizujemy odchylenia w obu kierunkach, bo to one korygują rozumienie mechanizmu. Zacznijmy od Qwena, który pobił predykcję z dużym zapasem: zmierzone 2,97× wobec przewidzianych 1,84× — więcej nawet niż sufit łącza idealnego, 2,14×. To ma dwie przyczyny. Po pierwsze, model traktował czas kerneli NCCL jak czysty transfer danych. A profil wlicza do NCCL także czekanie kart na siebie — o którym mówiliśmy przy H2 — i to czekanie przy krótszej rundzie znika szybciej niż proporcjonalnie. Wniosek na przyszłość: udział komunikacji z profilu to górna granica czasu transferu, więc model zbudowany na nim daje dolne oszacowanie zysku. Po drugie, kontrola pojedynczości interwencji wykryła ukrytą drugą zmianę: vLLM sam aktywował własny kernel all-reduce, gdy zobaczył pełną siatkę. Zmiana sprzętowa pociągnęła za sobą zmianę software'ową. Próbowaliśmy później rozdzielić te wkłady. Przy c=64 się nie udało — porównania dają przedział 1,0–1,2× przy szumie ±6% pojedynczego biegu. Przy c=1 wkład kernela jest realny, około +8% na TPOT. Teraz Kimi i błąd w dół. Najpierw skąd obie liczby. 0,75 przyjęliśmy z geometrii ring all-reduce: karty tworzą logiczny pierścień, komunikacja rozkłada się równomiernie na odcinki, a przy wyspach 0–3 i 4–7 sześć z ośmiu odcinków leży wewnątrz wysp — sześć ósmych to 0,75. Z kolei 0,62 to wartość odwrócona z pomiaru: podstawiając zmierzone 2,08× i s równe 0,839 do wzoru, wychodzi capture około 0,62. Fizycznie ten rozjazd tłumaczy synchroniczność rundy. Scalenie idzie w tempie najwolniejszego ogniwa, więc dwa odcinki między wyspami — nadal po PCIe — zabierają większą część czasu rundy, niż wynosi ich udział w liczbie odcinków. Widać to zresztą w pomiarze busbw grupy 2+2 przez wyspy: 24,8–31,3 GB/s wobec 185–333 wewnątrz wyspy. Na koniec ważna zbieżność: pomiar end-to-end i profil dają zgodnie 0,62. Dwie niezależne drogi znów spotykają się na jednej liczbie — tym razem przy analizie błędu.

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

Na koniec klamra. Te dziesięć punktów to skondensowany szkielet całej prezentacji i każdy z nich ma za sobą pokazany dziś przykład z pomiarów. Metryka, która nie mierzyła tego, co myśleliśmy. Hipoteza obalona za darmo, z danych, które już mieliśmy. Interwencje po jednej zmianie naraz. Pasmo szumu, do którego odnosiliśmy każdą różnicę. Dwie niezależne metody spotykające się na jednej liczbie. I model, który pomylił się w obie strony — i właśnie dlatego czegoś nas nauczył. Sam protokół jest ogólny: nie zależy od vLLM, od NVLinka ani od konkretnego serwera. Zmienia się tylko treść hipotez i zestaw liczników. Dziękuję za uwagę.