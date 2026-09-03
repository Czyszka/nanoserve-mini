# Slajdy v2 — szkielet, uwagi krytyczne, pytania

Status: **SZKIC — struktura do omówienia** (2026-09-03). Tytuły slajdów
(sekcja A) są propozycją użytkownika, zapisaną dosłownie. Pod każdym:
co mamy z v1 / z sesji 2026-08-31, moje uwagi krytyczne i pytania do
rozstrzygnięcia. Sekcja B: terminy i gdzie je definiujemy. Sekcja C:
budżet czasu. Sekcja D: uwagi do całości.

## Decyzje użytkownika (2026-09-03, runda 1)

| # | decyzja | konsekwencja |
|---|---|---|
| 1 | TP definiujemy na **slajdzie 4**, nie 1 | slajd 1 mówi słowami: „Kimi wymaga 8 kart, Qwen mieści się na jednej" — bez skrótu „TP" |
| 2 | slajd 4 = **era PCIe**; cel: „wraz ze wzrostem TP przepustowość Qwena w pewnym momencie spada" (wykres W1 z v1 slajd 12) | grid po NVLinku z 08-31 → slajd 10 / backup |
| 3 | definicja GPU-Util zostaje na **slajdzie 5** (jedno miejsce: z czego składa się krok + co GPU-Util liczy jako 100%) | slajd 2 pokazuje tylko paradoks i pytanie do sali — bez sugestii „metryka kłamie"; slajd 3 mówi „żaden zasób nie pracuje" i nie tłumaczy dlaczego |
| 4 | slajd 6: dane z sesji 08-31 (w toku) | fallback z v1 zostaje zapisany |
| 5 | slajd 9: **custom all-reduce → notes**; ze slajdu wypada busbw w GB/s | slajd stoi na tabeli latencji µs (pomiar 08-31) |
| 6 | slajd 9: latencje z sesji 08-31 | jw. |
| 7 | koszt: **2 mostki** (2 szt. × ~4,5 tys. zł ≈ 9 tys. zł); zysk pokazać obrazowo dla użytkownika końcowego | **patrz uwaga do slajdu 10 — „2× przepustowości" ≠ „odpowiedź 2× szybciej"** |
| 8 | **bez slajdu 11** — slajd 10 jest podsumowaniem | ostatnie zdanie prezentacji = zdanie-komunikat slajdu 10; propozycja 11 zostaje w pliku jako odrzucona |
| tytuł | **ZAAKCEPTOWANY (runda 3):** „100% GPU-Util, a tylko 30% limitu mocy. Co jest wąskim gardłem?" — podtytuł: *badania wydajnościowe serwera 8×H200 i ich efekty — studium przypadku NVLink* | ostatni slajd odpowiada na pytanie z tytułu jednym zdaniem („żaden zasób — czekanie kart na siebie"); przy limicie długości na liście meetupu: pierwsze zdanie = tytuł, pytanie → podtytuł. Burza mózgów T1–T7 niżej = historia |

Konwencja pracy (jak w v1): slajd po slajdzie → pytania → decyzje → tekst
„na slajdzie" + speaker notes → status SZKIC / W ITERACJI / ZAAKCEPTOWANY.

---

## A. Slajdy (propozycja użytkownika + uwagi)

### 0. Tytuł prezentacji

**Propozycja użytkownika:** tytuł prezentacji.

**Z v1:** „100% GPU-Util, a tylko 1/3 mocy — jak badać wydajność inferencji
LLM?" + podtytuł „Studium przypadku: vLLM, Kimi-K2.6 (1T), 8×H200, prawo
Amdahla". Decyzje v1: bez danych prelegenta, bez nazwy wydarzenia, bez
linków GitHub.

**Uwagi krytyczne:**

- Tytuł v1 obiecuje „jak badać" — czyli metodykę. v2 według Twojej struktury
  opowiada **historię jednej modernizacji** (anomalia → przyczyna → NVLink →
  zysk). Tytuł musi obiecać to, co dostarczamy. Propozycja kierunku:
  „100% GPU-Util, a tylko 1/3 mocy — dlaczego 8 kart H200 czekało na siebie
  i co dały mostki NVLink". Podtytuł bez „prawa Amdahla" (za trudne na
  tytuł; w v2 Amdahl w ogóle nie musi paść z nazwy).
- Na tytułowym slajdzie warto od razu dać **jedno zdanie z odpowiedzią**
  (np. „Czas kroku zjadała komunikacja między kartami; NVLink dał 2–3×
  przepustowości pod obciążeniem, ~0 dla pojedynczego czatu"). Słuchacz
  wie wtedy, dokąd zmierzamy — v1 trzymała odpowiedź do slajdu 17.

**Uwaga do propozycji „Badania wydajnościowe i ich efekty / studium
przypadku" (runda 1):** to tytuł, który pasuje do każdej prezentacji o
czymkolwiek — nie mówi *czego* badania, *jakiego* sprzętu ani *jaki* efekt.
Na liście wystąpień meetupu nikt go nie wybierze, a sala nie wie, na co
czeka. Sam rdzeń jest dobry (to faktycznie jest „badania → efekt"), brakuje
konkretu. Trzy warianty do wyboru, od najbliższego Twojej propozycji:

- A. **Badania wydajnościowe serwera 8×H200 i ich efekt: mostki NVLink** —
  podtytuł: *studium przypadku: od 100% GPU-Util przy 1/3 mocy do 2–3×
  przepustowości*
- B. **100% GPU-Util, a tylko 1/3 mocy** — podtytuł: *badania wydajnościowe
  serwera 8×H200 i ich efekty — studium przypadku*
- C. **Dlaczego 8 kart H200 czekało na siebie** — podtytuł: *badania
  wydajnościowe i ich efekty — studium przypadku NVLink*

Rekomendacja: **B** — zachowuje Twoje sformułowanie jako podtytuł, a hasło
z v1 jako hak. Odpowiedź na tytule (jedno zdanie) — nadal rekomenduję,
skoro nie będzie slajdu podsumowania.

**Burza mózgów tytułu (runda 2).** Punkt wyjścia użytkownika: „100%
zajętości GPU, a tylko 30% mocy?". Uwaga do liczby: zmierzone 111–199 W
z 600 W to 18–33%; dla Kimi (170–199 W) „30%" jest uczciwe, „1/3" też —
30% brzmi konkretniej. Uwaga do słowa „moc": laik czyta „moc" jako „moc
obliczeniowa", inżynier jako waty — ta dwuznaczność działa na korzyść
haka, ale na slajdzie 2 trzeba od razu pokazać, że chodzi o waty.

| # | tytuł | styl | ocena |
|---|---|---|---|
| T1 | **100% zajętości GPU, a tylko 30% mocy?** | pytanie-paradoks (Twoja) | mocny hak, po polsku; „zajętość" mniej precyzyjne niż „GPU-Util", ale zrozumiałe dla wszystkich |
| T2 | **GPU-Util 100%, pobór mocy 30%. Gdzie zniknęło 70%?** | paradoks + pytanie | dwie liczby i pytanie, na które prezentacja odpowiada wprost (odp.: w czekaniu na inne karty); dla sali IT „GPU-Util" jest rozpoznawalne |
| T3 | **Osiem kart H200 na 100% — i tylko jedna trzecia mocy** | obrazowy | nazywa sprzęt (dobre na listę wystąpień), trochę długi |
| T4 | **Karty pracują na 100%. Serwer nie.** | krótki, prowokacyjny | najkrótszy; nie mówi nic o LLM ani NVLink — wymaga podtytułu |
| T5 | **Więcej kart = wolniej?** | paradoks nr 2 | hak ze slajdu 4 zamiast ze slajdu 2; celny dla ludzi od inferencji, mniej obrazowy dla reszty |
| T6 | **Dlaczego 8 kart H200 czekało na siebie** | odpowiedź w tytule | zdradza puentę — dobre, jeśli chcemy, żeby sala od początku wiedziała, dokąd idziemy |
| T7 | **Sto procent, które nic nie znaczy** | literacki | ładny, ale niejasny bez podtytułu; ryzyko „o czym to?" |

Podtytuł (wspólny dla wszystkich): *badania wydajnościowe serwera
8×H200 i ich efekty — studium przypadku NVLink*. Z podtytułem każdy z T1–T7
niesie komplet: hak + sprzęt + efekt.

Moja kolejność: **T2 > T1 > T6 > T3**. T2 ma to, czego brakowało v1:
pytanie, na które ostatni slajd odpowiada jednym zdaniem („70% zniknęło
w czekaniu kart na siebie; mostki oddały z tego 2–3× przepustowości").
Jeśli wolisz czystą polszczyznę bez „GPU-Util" — T1 z podtytułem.

---

### 1. Stanowisko pomiarowe

**Propozycja użytkownika:** stanowisko pomiarowe.

**Z v1 (slajd 2):** Supermicro SYS-521GE-TNRT, 2× Xeon Gold 6530, 8× H200
NVL 143 GB, PCIe 5.0 (stan wyjściowy), vLLM w Dockerze; Kimi-K2.6 (1T,
554 GB wag → TP=8, Eagle3) i Qwen3.6-35B (model testowy, TP=1/2/4/8).

**Uwagi krytyczne:**

- To jest jedyne miejsce przed slajdem 4, gdzie można wprowadzić **TP**
  („model za duży na jedną kartę → tniemy go na N kart; Kimi nie mieści
  się na mniej niż 8") i **c** (liczba równoległych zapytań). Bez tego
  slajd 4 („różne TP i c") będzie nieczytelny. Proponuję: na tym slajdzie
  jedna grafika: serwer → 8 kart → Kimi rozpięty na wszystkich ośmiu,
  Qwen mieści się na jednej. Definicja c może poczekać do slajdu 4.
- Zastrzeżenie z v1 („TP=4/8 dla Qwena to nie konfiguracje produkcyjne")
  jest ważne, bo inaczej ktoś zapyta „po co Qwen na 8 kartach". Jedno
  zdanie w notes wystarczy.
- Bez listy narzędzi na slajdzie (nvidia-smi, DCGM, torch profiler,
  vllm bench) — każde narzędzie wchodzi na slajdzie, na którym go używamy.

**Pytania:** czy nazwa modelu Kimi i „1T parametrów" ma zostać (v1: tak,
bez nazwy projektu/firmy)?

---

### 2. Anomalia, w tym pomiar mocy, GPU-Util

**Propozycja użytkownika:** anomalia, w tym pomiar mocy, gpu-util.

**Z v1 (slajd 3):** zrzut nvidia-smi (8× 100% util, ~175 W z 600 W),
wykres W0 (moc w czasie, linia 600 W), pytanie do sali.

**Uwagi krytyczne:**

- Najmocniejszy slajd v1 — zostaje niemal bez zmian. Zrzut + jedno pytanie.
  Wykres W0 raczej wypada (drugi element obrazkowy o tym samym) — chyba że
  chcemy pokazać „stan trwały, nie chwilowy"; wtedy W0 zamiast liczb.
- **Decyzja do podjęcia teraz:** czy tu pada jednozdaniowa definicja
  GPU-Util („procent czasu, w którym na karcie *cokolwiek* się wykonywało"),
  czy trzymamy napięcie do slajdu 5? Ryzyko trzymania: sala domyśla się
  „metryka kłamie" na slajdzie 2 i przez trzy slajdy czeka na potwierdzenie.
  Moja rekomendacja: definicja tu, jednym zdaniem; slajd 5 pokazuje *co*
  konkretnie się wykonywało.
- W v1 anomalią był tylko pobór mocy. Druga, mocniejsza anomalia — **więcej
  kart = wolniej** (slajd 4) — nie jest tu zapowiedziana. Można ją
  zapowiedzieć jednym zdaniem („i to nie koniec dziwności").

---

### 3. Pomiary DCGM

**Propozycja użytkownika:** pomiary dcgm.

**Z v1 (slajd 5):** tabela 4 liczników (moc, SM_ACTIVE, DRAM_ACTIVE, PCIe
RX/TX) dla Kimi c=1 / c=64 + wykres W2 + puenta „GPU-Util 100%, nasycenie:
żadnego zasobu".

**Uwagi krytyczne:**

- v1 miała tu tabelę **i** wykres — jedno z dwóch. Rekomendacja: wykres W2
  uproszczony do 4 słupków „% nasycenia" (util 100 / moc 30 / SM 20 /
  HBM 8) i jedna linia komunikatu. Bez PCIe RX/TX na slajdzie — łącze
  wraca na slajdzie 8, tu tylko zaciemnia.
- Trzeba zdefiniować SM i HBM po ludzku („jednostki liczące" / „pamięć
  karty") — na slajdzie w podpisach, nie w notes.
- Kontrast Qwen TP1 (SM 0,68, DRAM 0,39, 436 W) jest ważny: dowodzi, że
  kartę *da się* nasycić. Jedna liczba w notes, ewentualnie szary słupek
  odniesienia na wykresie.
- Slajd 3 nie powinien jeszcze tłumaczyć *dlaczego* — tylko „żaden zasób
  nie pracuje". Wyjaśnienie zaczyna się na slajdzie 5.

---

### 4. Pomiary przepustowości Qwen dla różnych TP i c

**Propozycja użytkownika:** pomiary przepustowości Qwen dla różnych TP i c.

**Z v1 (slajd 12, wykres W1):** era PCIe, c=64: 1202 / 1404 / 680 / 257
tok/s; c=1 ITL 8,98 / 9,91 / 10,54 / 14,16 ms. **Z sesji 2026-08-31:**
pełny grid TP1/2/4/8 × c=1/16/32/64 × {wyspa, cross, nop2p} po NVLinku.

**Uwagi krytyczne:**

- **Która era?** Narracja jest chronologiczna, więc tu powinna być krzywa
  **z ery PCIe** (przed modernizacją) — to ona jest anomalią nr 2 („4 karty
  wolniejsze niż 1"). Grid z 08-31 (po NVLinku) idzie na slajd 10 jako
  „po". Jeśli pokażemy tu krzywą po NVLinku, slajd 10 nie ma czego
  porównać.
- Jeden wykres: słupki tok/s dla TP=1/2/4/8 przy jednym c (c=64). Bez
  linii efektywności skalowania, bez drugiego c — to były dwa komunikaty
  na jednym wykresie w v1. Wariant c=1 (ITL rośnie z TP) do notes albo
  jedno zdanie.
- Tu definiujemy **c** (jeśli nie na slajdzie 1) i mówimy, dlaczego Qwen
  a nie Kimi (Kimi nie da się uruchomić na TP<8, więc nie ma krzywej).
- Komunikat slajdu: „Dokładanie kart *spowalnia*. Coś między kartami
  zjada czas." — to jest zawiązanie akcji dla slajdów 5–7.

**Pytania:** PCIe-era (rekomendacja) czy NVLink-era? c=64 czy c=32?

---

### 5. Elementy czasu kroku generowania, co to kernele, co mierzy GPU-Util, wzór kroku

**Propozycja użytkownika:** elementy czasu kroku generowania, co to
kernele, co mierzy gpu-util, wzór kroku.

**Z v1 (slajdy 4 i 6):** grafika D2 (oś czasu kroku: kernel compute |
kernel NCCL czekający | memory-bound | przerwa hosta; klamra „dla GPU-Util
wszystko = zajęte"); wzór T(krok) = F_host + N_rounds × r + W_silicon.

**Uwagi krytyczne:**

- To jest **najtrudniejszy slajd** i nosi cztery tematy naraz (krok,
  kernel, GPU-Util, wzór). Wg zasady „jeden komunikat" to za dużo.
  Propozycja redukcji: komunikat = „krok generowania jednego tokenu to
  ciąg małych programów na GPU (kerneli); GPU-Util liczy *czy* jakiś
  kernel trwa, nie *co* robi". Wzór tylko słownie:
  **czas kroku = narzut silnika + komunikacja między kartami + obliczenia**.
  Symbole F_host / N_rounds / r / W_silicon — wcale (nawet w notes można
  bez nich).
- Grafika D2 z v1 jest dobra i wystarczy jako jedyny element.
- Jeśli definicja GPU-Util padła na slajdzie 2, tu jej nie powtarzamy —
  tylko pokazujemy na osi czasu, że kernel-który-czeka też „świeci".
- „Krok generowania" trzeba nazwać: jeden krok = jeden nowy token dla
  wszystkich zapytań w batchu (spekulacja Eagle3 komplikuje — pominąć
  na slajdzie, jedno zdanie w notes).

**Pytania:** czy słowo „kernel" w ogóle wchodzi na slajd, czy mówimy
„operacja na GPU"? (Rekomendacja: „operacja (kernel)" raz, potem
„operacja".)

---

### 6. Torch profiler, rozkład czasu kroku

**Propozycja użytkownika:** torch profiler, rozkład czasu kroku, co to
torch profiler po polsku, co robi dla Kimi, Qwen, różne TP i c
(uzupełnienie w trakcie sesji serwerowej).

**Z v1 (slajdy 10 i 12, wykres W3):** Kimi TP8 c=1: 63% przerwy / 22,5%
NCCL / 9,1% compute; c=16: 10% / 83,9% / 4,6%; Qwen TP4 c=64: 33% / 53,3%
/ 5,6%; kontrola narzutu profilera ±5–9%. **Z sesji 2026-08-31:** profile
Qwen TP1/2/4/8 × c=1/16/32 po NVLinku.

**Uwagi krytyczne:**

- Ryzyko nr 1 tego slajdu: **siatka 12 profili**. Sala nie przeczyta.
  Jeden wykres: słupki skumulowane (przerwy / komunikacja / obliczenia)
  dla Qwen TP=1 → 2 → 4 → 8 przy jednym c (np. c=32) — czyli „jak rośnie
  udział komunikacji, gdy dokładamy karty". To jest dokładnie ilustracja
  slajdu 4. Kimi (TP8) jako piąty słupek albo osobne zdanie.
- **Zależność od dzisiejszej sesji:** jeśli profile Qwen TP1–8 nie
  przyjdą, fallback = trzy słupki z v1 (Kimi c1, Kimi c16, Qwen TP4 c64).
  Gorsze (mieszają modele i c), ale mamy.
- Uwaga metodyczna z v1 do zachowania w notes: profil liczy czekanie kart
  na siebie jako „komunikację" (kernel NCCL trwa, gdy karta czeka na
  ostatnią). To ważne dla slajdu 7.
- Definicja torch profilera po polsku: „rejestrator osi czasu: zapisuje,
  co dokładnie i jak długo wykonywała karta w każdej milisekundzie".
  Wystarczy.
- Wątek H3 z v1 (narzut hosta przy c=1: spekulacja 40% kroku, CUDA
  Graphs, governor) **wypada** z v2 — poza główną linią. Jedno zdanie
  w notes: „przy pojedynczym czacie rządzi narzut silnika, nie łącze —
  dlatego NVLink daje tam tylko 15–20%" — potrzebne przy slajdzie 10.

**Pytania:** c=16 czy c=32 jako reprezentatywne obciążenie? (c=16 Kimi
w erze PCIe było anomalią — unikać go jako punktu wzorcowego.)

---

### 7. Najważniejszy składnik — komunikacja, co to all-reduce

**Propozycja użytkownika:** najważniejszy składnik — komunikacja, co to
all-reduce.

**Z v1 (slajd 11, schemat D3):** jedna warstwa pod TP: blok uwagi →
SCALENIE 1 → blok FFN/MoE → SCALENIE 2; × 61 warstw Kimi ≈ 122 scalenia
na krok; scalenie synchroniczne — nikt nie rusza dalej, aż skończy
ostatnia karta. Ring all-reduce, NCCL — w notes.

**Uwagi krytyczne:**

- Dobre miejsce. Komunikat: „każda karta liczy kawałek, po każdym
  kawałku warstwy wszystkie muszą *dodać* swoje wyniki — 122 razy na
  jeden token — i każda czeka na najwolniejszą".
- Nie tłumaczyć algorytmu ring (2(N−1) kroków) na slajdzie — to poziom
  v1. Jeden obrazek: 4 karty, strzałki wymiany, napis „suma".
- Kluczowa myśl do przygotowania **tutaj**, bo slajd 9 na niej stoi:
  wiadomość w jednej rundzie jest mała (kilkanaście KB przy c=1), rund
  jest dużo → liczy się **czas jednej rundy (latencja)**, nie
  przepustowość rury. W v1 to było zdanie na slajdzie 12 („ogranicza nas
  czas rundy, nie przepustowość") — twierdzenie z literatury; sesja
  08-31 ma je zmierzyć.
- NCCL: jedno zdanie w notes („biblioteka NVIDIA, która to scalanie
  wykonuje"). Nazwa może paść raz.

---

### 8. Topologia sprzętowa przed NVLink, parametry PCIe

**Propozycja użytkownika:** topologia sprzętowa przed nvlink, parametry
PCIe.

**Z v1 (slajd 9, diagram D1):** 2× CPU + UPI, 4 switche PCIe 5.0 x16,
pary GPU (0,1)(2,3) pod CPU0 i (4,5)(6,7) pod CPU1; schemat w
`infrastructure.md` §2.2. Parametry: PCIe Gen5 x16 128 GB/s dwukierunkowo,
~20 µs/wymianę (literatura). Wynik H4 z v1: trasa przez UPI nie kosztuje
(9,13 vs 9,91 ms — w szumie).

**Uwagi krytyczne:**

- Slajdy 8 i 9 to **dwa slajdy topologii** w 11-slajdowej prezentacji.
  To dużo. Uzasadnienie: 8 = „jak jest" (droga sygnału GPU → switch →
  CPU → UPI → CPU → switch → GPU), 9 = „jak będzie". Może się bronić,
  jeśli 8 jest krótki (~1 min): jeden schemat, dwie liczby (128 GB/s,
  ~20 µs).
- UPI: w v1 osobna hipoteza (H4, obalona). W v2 **wypada** jako temat —
  na schemacie po prostu rysujemy łącze między CPU, bez nazwy, albo z nazwą
  i bez komentarza. Nie wprowadzać terminu, którego nie użyjemy.
- „Parametry PCIe": przepustowość jest myląca — mierzyliśmy zaledwie
  ~7,5 GB/s z 64 GB/s w jedną stronę, więc *nie* przepustowość była
  problemem. Jeśli pokazujemy 128 GB/s, to musimy od razu powiedzieć „i
  używaliśmy 10% tego" — inaczej sala wyciągnie zły wniosek („za wolna
  rura"). Właściwa liczba do pokazania to **latencja** (~20 µs), zgodnie
  z tezą ze slajdu 7.

**Pytania:** czy pokazujemy w ogóle GB/s, czy tylko µs? (Rekomendacja:
oba, ale z jawnym „10% użycia" przy GB/s.)

---

### 9. Topologia połączeń przed i po NVLink, pomiary czasu dostępu, custom all-reduce, schematy

**Propozycja użytkownika:** topologia połączeń przed i po nvlink, pomiary
czasu dostępu do danych (dziś na sesji), custom all-reduce, schematy
topologii.

**Z v1 (slajd 16, diagram D1-PO, wykres W4):** dwie wyspy NV6 (GPU 0–3 /
4–7), między wyspami PCIe/UPI; P2P 132,8 vs 29,1 GB/s; busbw 185–333 vs
24,8–31,3 GB/s; bramka custom all-reduce (Qwen TP4: aktywny, Kimi TP8:
nie). **Z sesji 2026-08-31:** latencja P2P (wyspa vs cross), all-reduce
NCCL µs/op przy 4–16 KB dla wyspa-2/4, cross-2/4, all-8, nop2p; predykcje
pre-rejestrowane w planie (wyspa 1–3 µs P2P, NCCL 10–35 µs, cross ≥2×).

**Uwagi krytyczne:**

- Znów cztery tematy na jednym slajdzie (topologia po, latencje, custom
  AR, schematy). Propozycja cięcia:
  - **zostaje:** schemat „po" (dwie wyspy) obok schematu „przed" z
    slajdu 8 (ten sam rysunek, dorysowane mostki) + **jedna tabela
    latencji**: PCIe / NVLink w wyspie / między wyspami — w µs na rundę.
    To jest sedno: „runda 5–10× krótsza".
  - **wypada ze slajdu → notes:** custom all-reduce. To szczegół
    software'owy (vLLM włącza własny kernel, gdy widzi pełną siatkę),
    istotny tylko jako wyjaśnienie, dlaczego Qwen zyskał 2,97× zamiast
    ~2×. Dla sali „znającej AI, ale nie vLLM" to za głęboko. Jedno zdanie
    w notes na slajdzie 10.
  - **wypada:** busbw w GB/s (W4). Skoro teza brzmi „liczy się latencja",
    to pokazywanie GB/s jest niekonsekwentne. Ewentualnie jedna liczba w
    notes jako „przy okazji przepustowość ×20".
- Ryzyko: literatura mówi 2–9 µs (A100/V100), plan 08-31 przewiduje NCCL
  10–35 µs w wyspie. Jeśli zmierzymy 20–30 µs przy PCIe ~40–60 µs, to
  „NVLink 2 µs" z v1 należy **wycofać**, a nie bronić. Slajd musi stać na
  naszym pomiarze, nie na cytacie.
- Termin „wyspa" (4 karty połączone mostkiem) trzeba zdefiniować tu, bo
  wraca na slajdzie 10 (Kimi TP8 = dwie wyspy → mniejszy zysk).

**Pytania:** czy zostawiamy custom all-reduce na slajdzie (Twoja
propozycja), czy w notes (moja)? Co, jeśli sesja nie da latencji —
fallback: tylko GB/s z 07-31 + literatura z jawnym zastrzeżeniem.

---

### 10. Wyniki przed i po NVLink, zysk, koszt

**Propozycja użytkownika:** wyniki pomiarów przed i po nvlink, wykresy
(Kimi, Qwen jeden pod drugim, nie obok siebie), wyliczony zysk z
modernizacji, koszt NVLink (około 4,5 tys. zł sztuka).

**Z v1 (slajd 17, wykres W5):** Qwen TP4 c64 680 → 2022 (2,97×); Kimi TP8
c32 285 → 594 (2,08×); c=1: −20% / −15% TPOT. Notatka decyzyjna: zysk
tylko przy TP≥4 pod obciążeniem; c=1 ≤1,3×; TP≤2 ≈ 0.

**Uwagi krytyczne:**

- Dwa wykresy jeden pod drugim (Kimi, Qwen) — OK, o ile każdy ma **dwa
  słupki** (przed/po) i jedną liczbę „×". Bez linii predykcji i progów
  falsyfikacji z v1.
- **Uczciwość wyniku:** zysk 2–3× dotyczy obciążenia równoległego. Przy
  pojedynczym czacie 15–20%. Jeśli pokażemy tylko 2–3×, ktoś z sali
  (słusznie) zapyta o latencję pojedynczego zapytania. Proponuję trzeci
  wiersz/zdanie: „pojedynczy czat: −15–20% opóźnienia — bo tam rządzi
  narzut silnika, nie łącze".
- **Koszt:** „4,5 tys. zł sztuka" — ile sztuk? Dwie wyspy po 4 karty:
  ile fizycznych mostków (jeden 4-way na wyspę = 2 szt.? czy 3 na wyspę?).
  Trzeba podać liczbę sztuk i sumę, a nie cenę jednostkową. To nie jest
  w repo — do uzupełnienia przez Ciebie.
- **Zysk z modernizacji — w jakiej walucie?** Najmocniejsza rama: „2× więcej
  tokenów/s z tej samej maszyny za ~X tys. zł" versus „drugi serwer 8×H200
  za Y". Alternatywa: koszt za 1000 tok/s przed i po. Wybrać jedną; nie
  liczyć ROI w złotych za token (za dużo założeń o obciążeniu).
- Tu też pada wyjaśnienie różnicy Kimi 2,08× vs Qwen 2,97×: Kimi TP8 =
  dwie wyspy, część scaleń nadal po PCIe (notes; na slajdzie jedno
  zdanie „Kimi na 8 kartach przekracza granicę wysp — mniejszy zysk").

**Pytania:** czy pokazujemy koszt serwera jako odniesienie (jeśli tak —
skąd liczba)?

**Uwaga do decyzji 7 („zysk 2× ⇒ użytkownik dostaje odpowiedź 2×
szybciej") — to jest nieprawda i sala z vLLM-em to wychwyci.**
Zmierzone 2,08× / 2,97× to **przepustowość serwera** (tok/s dla wszystkich
klientów naraz przy c=32/64). Pojedynczy użytkownik odczuwa co innego:

| kto | co mierzymy | przed → po | odczucie |
|---|---|---|---|
| jeden użytkownik, serwer pusty (c=1) | TPOT Kimi | 8,7 → 7,44 ms | odpowiedź **~15% szybciej** (Qwen: 20%) |
| jeden z 32 użytkowników naraz (Kimi c=32) | ITL med | 127 → ~90 ms | tokeny płyną **~30% szybciej** |
| operator serwera (c=32) | tok/s łącznie | 285 → 594 | **2× więcej użytkowników** przy tej samej prędkości odpowiedzi |

**Aktualizacja (runda 2) — przełożenie na użytkownika końcowego z danych
w repo.** Metryka odczuwana przez użytkownika to **TPOT** (czas na jeden
wygenerowany token, medianą), nie ITL — przy spekulacji Eagle3 jedna
porcja (ITL) niesie ~2,6 tokena, więc ITL zaniża odczuwany zysk. Kimi TP8,
ta sama praca (SWE custom, 256 tokenów odpowiedzi), przed = 2026-06-11
(PCIe), po = 2026-07-31/08-03 (NVLink):

| użytkowników naraz | TPOT przed → po (ms/token) | odpowiedź 256 tok. przed → po | ile razy szybciej | źródło |
|---:|---|---|---:|---|
| 1 | 8,7 → 7,44 | 2,2 s → 1,9 s | **1,2×** | `kimi_ramp/bench/kimi_c1.json`; 07-31 |
| 8 | 78,5 → 17,5 | 20 s → 4,5 s | **4,5×** | `kimi_c8.json`; `…domkniecie_grafana/grafana/bench/ramp_c8.json` (jeden bieg) |
| 16 | 190,5 → 26,0 | 49 s → 6,7 s | **7,3×** | `kimi_c16.json` (anomalia c16, potwierdzona powtórką); `…gap_fill/kimi/bench/kimi_c16.json` |
| 32 | 94,1 → 44,9 | 24 s → 11,5 s | **2,1×** | `kimi_c32.json`; `…gap_fill/kimi/bench/kimi_c32.json` |
| przepustowość serwera (c=32) | 285 → 608 tok/s | — | **2,1×** | jw. |

Wniosek: „2×" z przepustowości **jest** tym, co odczuwa użytkownik przy 32
osobach naraz (24 s → 11,5 s na odpowiedź), a przy 8–16 osobach zysk jest
większy (4–7×), bo w erze PCIe ten zakres był patologiczny (c=16: 49 s na
odpowiedź — serwer z 8 kart obsługiwał 16 osób wolniej niż jedną). Przy
jednej osobie na pustym serwerze: 1,2×. To jest gotowy materiał na slajd
10: cztery wiersze „ilu użytkowników → ile sekund na odpowiedź przed/po".

Zastrzeżenia do wypowiedzenia ustnie: (a) 256 tokenów to krótka odpowiedź
(~150–200 słów) — dłuższe skalują liniowo; (b) wiersz c=8 „po" to jeden
bieg z rampu 08-03, bez powtórki; (c) 4,5× i 7,3× to w części zniknięcie
anomalii c=16 — ale T9 §14 pokazał, że anomalia była transportowa, więc
to legalnie zasługa NVLinka; (d) wszystkie „po" ciepłe (po wygrzewce).

Poprzednie sformułowanie (ITL, „~30%") — zastąpione powyższym; ITL zostaje
w notes jako metryka techniczna. Wcześniejsza alternatywa:
„przy 32 osobach naraz każda dostaje tekst ~30% szybciej" **albo** „ta sama
maszyna obsłuży 2× więcej osób bez spowolnienia". Zdanie „odpowiedź 2×
szybciej" trzeba wykreślić. Propozycja na slajd: dwa krótkie wiersze —
dla użytkownika (−30% czasu na token pod obciążeniem, −15% przy pustym
serwerze) i dla operatora (2–3× przepustowości za ~9 tys. zł, czyli ~0,3%
ceny serwera — jeśli zgodzisz się podać rząd wielkości ceny serwera).
Liczby ITL do potwierdzenia na danych 08-31 (Kimi c32 po NVLinku:
90,2 ms nieprofilowany, `2026-08-03-nvlink-day-summary.md` §2).

---

### 11. (Propozycja dodatkowa) Podsumowanie / do zabrania — ODRZUCONA (decyzja 8)

Użytkownik: slajd 10 jest sam w sobie podsumowaniem. Konsekwencja: zdanie
u góry slajdu 10 musi być zdaniem, z którym sala wychodzi; slajd 10 nie
może kończyć się liczbą kosztu. Budżet czasu §C: 0,5 min z 11 przechodzi
na slajd 10. Treść poniżej zostaje jako materiał na to zdanie.

**Uzasadnienie:** 20-minutowa prezentacja bez slajdu końcowego kończy się
na wykresie kosztów, a ostatnie zdanie prelegenta zapamiętują wszyscy.
Trzy zdania na slajdzie:

1. GPU-Util 100% ≠ karta pracuje — patrz na moc, SM, pamięć.
2. Przy modelu na ≥4 kartach czas kroku zjada 100+ rund komunikacji na
   token; liczy się latencja rundy.
3. NVLink: 2–3× pod obciążeniem, ~0 dla pojedynczego czatu i modeli na
   1–2 kartach — kupuj tylko w pierwszym przypadku.

Bez protokołu 10 punktów z v1. Bez „Dziękuję" jako osobnego slajdu.

---

## B. Terminy — gdzie definiujemy (raz, jednym zdaniem)

| termin | slajd | forma |
|---|---|---|
| TP (podział modelu na N kart) | 4 (decyzja 1) | 1 zdanie + podpis osi; slajd 1 mówi „wymaga 8 kart" |
| c (równoległe zapytania) | 1 lub 4 | podpis |
| GPU-Util | 5 (decyzja 3) | oś czasu kroku |
| DCGM, SM, HBM | 3 | podpisy osi |
| tok/s, krok / ITL | 4 | podpis osi; ITL tylko jeśli pokażemy c=1 |
| krok generowania, kernel/operacja | 5 | oś czasu |
| torch profiler | 6 | 1 zdanie |
| all-reduce, NCCL (raz) | 7 | obrazek + 1 zdanie |
| PCIe, switch, latencja rundy | 8 | schemat |
| NVLink, wyspa | 9 | schemat |
| **nie wprowadzamy:** UPI, NUMA, ring, busbw, custom all-reduce (→ notes), Amdahl, capture, F_host/N_rounds/r/W_silicon, Eagle3/MTP (→ notes) | | |

Jedenaście terminów na 20 minut to i tak górna granica. Każdy kolejny
wymaga wyrzucenia innego.

## C. Budżet czasu (20 min)

| slajd | min | uwaga |
|---|---:|---|
| 0 tytuł | 1,0 | z odpowiedzią w jednym zdaniu |
| 1 stanowisko | 1,5 | + definicja TP |
| 2 anomalia | 1,5 | zrzut + pytanie do sali |
| 3 DCGM | 2,0 | |
| 4 krzywa TP Qwen | 2,0 | anomalia nr 2 |
| 5 czas kroku | 2,5 | najtrudniejszy pojęciowo |
| 6 profiler | 2,0 | jeden wykres |
| 7 all-reduce | 2,0 | |
| 8 topologia przed | 1,0 | schemat + 2 liczby |
| 9 topologia po + latencje | 2,0 | tabela µs |
| 10 wyniki + koszt + podsumowanie | 2,5 | ostatnie zdanie prezentacji |
| **razem** | **20,0** | zapas 0 — realnie trzeba ciąć do ~18 na próbie |

## D. Uwagi do całości

1. **Chronologia vs pojęcia.** Struktura miesza dwa porządki: 2–4 to
   „co zobaczyliśmy", 5–7 to „jak to rozumieć", 8–10 to „co zrobiliśmy".
   To dobry układ — pod warunkiem, że slajd 4 kończy się pytaniem
   („dlaczego więcej kart = wolniej?"), a slajd 7 odpowiada na nie
   wprost. Inaczej blok 5–7 będzie wyglądał jak wykład wtrącony w historię.
2. **Trzy slajdy zależą od dzisiejszej sesji** (4 — jeśli NVLink-era, 6,
   9). Dla każdego zapisałem fallback z v1. Struktura nie może stać na
   danych, których jeszcze nie ma — jeśli latencje nie przyjdą, slajd 9
   redukuje się do schematu + literatura z zastrzeżeniem.
3. **Co świadomie wypada z v1** (do potwierdzenia): protokół 20 kroków,
   hipotezy H1–H4 i boksy werdyktów, predykcje pre-rejestrowane, prawo
   Amdahla z nazwy, interwencje hosta (spekulacja / CUDA Graphs /
   governor), analiza błędów modelu (0,75 vs 0,62), reguła wygrzewki,
   kalibracja szumu. Z tego do notes wracają tylko: narzut hosta przy c=1
   (jedno zdanie, slajd 10), custom all-reduce (jedno zdanie, slajd 10),
   szum ±0,4 ms (gdyby ktoś pytał o TP2).
4. **Ryzyko „zbyt prosto".** Publiczność mieszana; część zna vLLM. Dla
   nich zostawiamy głębię w speaker notes i w odpowiedziach na pytania —
   nie na slajdach. Warto mieć 2–3 slajdy zapasowe *po* podsumowaniu
   (backup: profil Kimi po NVLinku 61% NCCL; tabela decyzyjna z notatki;
   krzywa TP po NVLinku z 08-31) — pokazywane tylko w Q&A.

## E. Dane z sesji 2026-08-31 (commit `8d7ef5b`) — co zmieniają w v2

Pierwszy odczyt surowych plików (`results/runs/2026-08-31_latencja_dostepu/`),
bez podsumowania sesji — liczby do zweryfikowania przy pisaniu slajdów.

### E.1 Mikro-latencje (all-reduce 16 KB ≈ reżim c=1; `nvlink/lat_summary_quick.txt`)

| grupa | NVLink (µs/op) | nop2p (µs/op) | busbw @8 MB NVLink / nop2p (GB/s) |
|---|---:|---:|---|
| wyspa-2 (0,1) | 27,9 | 28,7 | 84,7 / 14,1 |
| wyspa-4 (0–3) | **53,8** | 30,6 | 197,5 / 13,8 |
| cross-2 (0,4) | 29,3 | — | 18,7 |
| cross-4 (0,1,4,5) | 30,2 | — | 27,4 |
| all-8 | 36,1 | 59,5 | 14,9 / 15,4 |

P2P (`p2p_lat.txt`): w wyspie 12,9 µs (0→1, 0→2), 24,3 µs (0→3), cross
0→4 25,9 µs, 3→4 16,1 µs.

**Konsekwencja dla slajdów 7–9 (poważna):** przy małych wiadomościach
NVLink **nie skraca rundy** — wyspa-2 27,9 vs nop2p 28,7 µs, wyspa-4 jest
nawet wolniejsza (53,8 vs 30,6; do wyjaśnienia — NVLS niedostępny wg
`nccl_path_island4.txt`, może wybór algorytmu). Predykcje planu „NCCL
wyspa-4 10–35 µs" i „nop2p ≥ 3× NVLink" — **obalone**. Teza v1 ze slajdu
12 („ogranicza nas czas rundy, nie przepustowość") **nie przeżyła
pomiaru** i nie może być tezą slajdu 7/9. Nowa, uczciwa wersja: przy c=1
liczy się latencja rundy (~30 µs niezależnie od łącza) i NVLink nie
pomaga — zgodne z e2e (Qwen TP4 c1 ITL wyspa 10,15 vs nop2p 8,71 ms;
Kimi c1 tylko 1,2×); pod obciążeniem wiadomość rośnie (c × hidden × 2 B →
setki KB) i wtedy liczy się **przepustowość** (197 vs 14 GB/s) — stąd
2–7× przy c≥8. To lepiej tłumaczy podział „pusty serwer / pod
obciążeniem" ze slajdu 10 niż teza latencyjna. Tabela latencji na slajdzie
9 zostaje, ale z odwróconym komunikatem; busbw wraca na slajd (decyzja 5
do rewizji).

### E.2 Grid Qwen po NVLinku (nieprofilowane; tok/s, `qwen/bench_*/`)

| TP / wariant | c=1 | c=16 | c=32 | c=64 |
|---|---:|---:|---:|---:|
| TP1 | 255 | 1438 | 2015 | 1710 |
| TP2 wyspa | 263 | 1620 | 2467 | 2050 |
| TP4 wyspa | 265 | 1851 | **2990** | 2129 |
| TP8 (2 wyspy) | 232 | 1426 | 1974 | 1625 |
| TP2 cross / TP4 cross | 267 / 233 | 1427 / 1314 | 2058 / 1928 | 1689 / 1472 |
| TP2 / TP4 / TP8 nop2p | 276 / 275 / 217 | 1170 / 1164 / 825 | 1674 / 1556 / 1041 | 1985 / 1784 / 1248 |

- Replikacja TP4 c64: 2129 vs 2022/1989 (+5%, w paśmie).
- Krzywa TP po NVLinku (c=32): 2015 / 2467 / 2990 / 1974 — **TP4 skaluje
  (1,48× vs TP1)**, TP8 nadal spada. Para do slajdu 4 (PCIe c=64: 1202 /
  1404 / 680 / 257) → materiał na „po" na slajdzie 10 (Qwen).
- c=64 < c=32 we wszystkich wariantach — do wyjaśnienia przed użyciem
  (prefill-burst? `max-num-seqs`?). Na slajdach używać c=32.
- nop2p przy TP4 c64 = 1784, nie 680 — potwierdza, że nop2p NIE jest
  rekonstrukcją ery PCIe (08-03); „przed" na slajdach = pomiary 06-11.
- Kara cross-island TP4 c32: 1928 vs 2990 (64% wyspy) — zgodna z predykcją
  „≤ 60%" w granicach; TP2 cross ≈ wyspa (H4 trzyma).

### E.3 Profile Qwen po NVLinku (udział w spanie; `profile/trace_summary_*`)

| TP | c=1: comms / compute / gaps | c=16 | c=32 |
|---|---|---|---|
| TP1 | 0 / 24 / 28% | 0 / 41 / 23% | 0 / 45 / 19% |
| TP2 wyspa | 0,7 / 12 / 60% | 2,8 / 22 / 48% | **12 / 28 / 17%** |
| TP4 wyspa | 2,9 / 15 / 33% | 1,5 / 12 / 69% | **18 / 19 / 18%** |
| TP8 | **69 / 8 / 5%** | 36 / 6 / 47% | **58 / 11 / 13%** |

- Slajd 6, jeden wykres: c=32, TP1→TP8, komunikacja 0 → 12 → 18 → 58%.
  Dokładnie „dokładanie kart = coraz więcej czekania".
- **Kontrola narzutu profilera NIE przeszła:** bench profilowany TP4 c32
  961 tok/s vs 2990 nieprofilowany (−68%; plan: ±15%). Trace'y są
  **jakościowe**, nie ilościowe — na slajdzie 6 mówić „udziały
  orientacyjne", w notes podać przyczynę. Kimi 08-03 (−9%) pozostaje
  jedynym ilościowym profilem.
- Bucket „other" 17–50% spanu — sprawdzić, co w nim siedzi (sampling?
  MoE routing? kopie), zanim pokażemy słupki; inaczej sala zapyta.
- TP8 c=1: 69% comms przy 5% gaps — Qwen na 8 kartach jest comms-bound
  nawet przy jednym kliencie (inaczej niż Kimi: 63% gaps). Notes do
  slajdu 10 (dlaczego Kimi c=1 zyskał tylko 1,2×).

### E.4 Do zrobienia przed pisaniem slajdów 6–10

1. Podsumowanie sesji 08-31 (`results/summaries/`) z werdyktami predykcji —
   sesja miała predykcje pre-rejestrowane; kilka padło (E.1) i to musi
   być zapisane, zanim trafi na slajd.
2. Wyjaśnić: wyspa-4 53,8 µs; c=64 < c=32; bucket „other"; narzut
   profilera −68%.
3. Aktualizacja `agent-state.md` (dane 08-31 SĄ w repo; sync-state).
