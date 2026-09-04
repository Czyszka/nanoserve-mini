# Treść slajdów v2 — „100% GPU-Util, a tylko 30% limitu mocy. Co jest wąskim gardłem?"

Status całości: **SZKIC 1 (2026-09-03)** — do omówienia slajd po slajdzie.
Decyzje strukturalne i historia: `slajdy-v2.md`. Dane: v1 (era PCIe,
06-11), po montażu (07-31/08-03), sesja 08-31 (podsumowanie w
`results/summaries/2026-08-31-latencja-dostepu-summary.md`). Kolejnej
sesji serwerowej nie będzie — wszystkie liczby poniżej są w repo.

Zasady (z README): jeden komunikat na slajd, ≤ 1 wykres/tabela, ≤ 5 liczb
na slajdzie, terminy definiowane raz, wzory słownie. Czas: 20 min.

Konwencja: **Na slajdzie** = dokładny tekst; **Notes** = narracja na głos;
**Grafika** = co rysujemy; **Źródło** = skąd liczby; **Status**.

---

## Slajd 0 — Tytuł (1 min)

Status: ZAAKCEPTOWANY (2026-09-03). Decyzje: podtytuł bez NVLink; bez danych prelegenta/daty/linków.

### Na slajdzie

> # 100% zajętości w GPU-Util, a tylko 30% limitu mocy.
> # Co jest wąskim gardłem?
>
> Badania wydajnościowe serwera 8×H200 i ich efekty — studium przypadku

### Notes

To jest prawdziwy odczyt z naszego serwera: osiem kart H200, każda pokazuje
sto procent obciążenia, a pobiera około trzydziestu procent mocy. Przez kilka tygodni
szukaliśmy, co jest wąskim gardłem. Opowiem, co znaleźliśmy, co zmieniliśmy
w serwerze i ile to dało — w sekundach, dla użytkownika. Odpowiedź na
pytanie z tytułu będzie na ostatnim slajdzie, w jednym zdaniu.

---

## Slajd 1 — Stanowisko pomiarowe (1,5 min)

Status: ZAAKCEPTOWANY (2026-09-03) — G1 wg uwag użytkownika, bez tokenów,
CPU z nazwą, SWE-bench Lite.

### Na slajdzie

> ## Stanowisko pomiarowe
>
> [GRAFIKA G1: osiem kart GPU w rzędzie (0–7). NAD kartami jedna klamra na
> całą ósemkę: „Kimi-K2.6 — 554 GB wag → tylko na 8 kartach".
> POD kartami cztery klamry: „1 GPU" (karta 0), „2 GPU" (0–1), „4 GPU"
> (0–3), „8 GPU" (0–7), podpisy wyśrodkowane pod klamrami; pod spodem
> pogrubione: „Qwen3.6-35B - 67 GB wag → do testów można go uruchomić na
> 1, 2, 4 lub 8"]
>
> - serwer: 2× Intel Xeon Gold 6530, 8× NVIDIA H200 NVL (143 GB każda);
>   karty połączone magistralą PCIe 5.0 — stan wyjściowy
> - silnik: vLLM w kontenerach Docker
> - obciążenie: własny benchmark — zadania programistyczne inspirowane
>   SWE-bench

### Notes

Środowisko to serwer laboratoryjny: dwa Xeony i osiem kart H200. Na
starcie karty rozmawiały ze sobą wyłącznie przez magistralę PCIe — tak jak
dyski czy karty sieciowe. Główny model to Kimi, bilion parametrów; same
wagi zajmują 554 GB, więc mieszczą się wyłącznie na wszystkich ośmiu
kartach naraz. Drugi model, Qwen, ma 67 GB wag i mieści się na jednej
karcie — dlatego służy nam jako model testowy: możemy go uruchomić na
jednej, dwóch, czterech albo ośmiu kartach i porównać, co się dzieje, gdy
dokładamy karty. Obciążenie generujemy własnym benchmarkiem: zadania
programistyczne wzięte z zestawu SWE-bench Lite, zawsze po rozgrzewce
silnika.

Źródło: `infrastructure.md` §2.2 (Xeon Gold 6530, H200 NVL 143 GB);
Kimi 554 GB — notatka decyzyjna §2; Qwen 67 GB — log vLLM
(`2026-08-31_latencja_dostepu/qwen/log_tp1.txt`: „Checkpoint size
66.97 GiB"); SWE-bench Lite 300 promptów —
`docs/plans/2026-06-05-t5-dashboard-load.md`. Bez nazwy projektu/firmy.
Q&A: platforma Supermicro SYS-521GE-TNRT; TP=4/8 dla Qwena to
konfiguracje badawcze, nie produkcyjne.

---

## Slajd 2 — Anomalia (1,5 min)

Status: ZAAKCEPTOWANY (2026-09-03; zakres mocy 126–254 W z okna stabilnego
wykresu, 2026-09-04): bez c, W0' z linią Qwen
1 karta (kolory: niebieski Kimi, ciemnozielony Qwen, czerwona przerywana
limit). Decyzja 3: bez definicji GPU-Util.

### Na slajdzie

> ## Anomalia
>
> [ZRZUT: nvidia-smi — 8 wierszy, kolumny GPU-Util 100% i moc ~175 W / 600 W;
> `../2026-07-31-nvlink-meetup/nvidia_smi_crop.png`]
>
> [WYKRES W0': jak v1 W0 — pobór mocy w czasie okna benchmarku.
> Osiem niebieskich linii (Kimi na 8 kartach, osobna linia na kartę)
> płasko w paśmie 111–185 W, podpis przy liniach: „Kimi — 8 × H200, po
> jednej linii na kartę". Jedna ciemnozielona linia: Qwen na jednej karcie,
> 400–590 W, podpis „Qwen — 1 × H200". Czerwona przerywana pozioma linia
> 600 W z podpisem „limit karty: 600 W". Bez legendy — podpisy przy
> liniach.]
>
> **Osiem kart z Kimi: 100% obciążenia — a pobór mocy 126–254 W z 600 W,
> przez cały benchmark. Karta, która naprawdę liczy: 380–580 W.**

### Notes

Tak wyglądał serwer pod pełnym obciążeniem, z Kimi na ośmiu kartach.
nvidia-smi, narzędzie, na które każdy patrzy pierwsze, pokazuje sto
procent na każdej karcie. A w kolumnie mocy: sto kilkadziesiąt watów, przy
limicie sześciuset. Wykres pod spodem pokazuje, że to nie był chwilowy
przestój między zadaniami: przez cały benchmark karty trzymały się w
paśmie od stu jedenastu do stu osiemdziesięciu pięciu watów. Dla skali
gruba linia: ten sam typ karty, model testowy uruchomiony na jednej karcie,
bez rozkładania na inne — czterysta do sześciuset watów, blisko limitu. Tak
wygląda karta, która naprawdę liczy. Zapamiętajmy ten obraz — wrócimy do
niego, kiedy będziemy wiedzieli, co te osiem kart właściwie robiło.

Źródło: zrzut — rekonstrukcja 08-03 (172–181 W); wykres 8 linii i pasmo
111–185 W — `2026-06-11_nvlink_boundary/kimi_ramp/kimi_c32_dcgmi.txt`
(v1 W0, `generate_charts.py`); linia „1 karta" —
`2026-09-04_qwen_tp1_okno_mocy/qwen/tp1_c64_long_dcgmi.txt`, GPU0 (sesja
2026-09-04: ten sam benchmark SWE c=64, 256-out, co 08-31, tylko 2400
promptów zamiast 600 → 322 próbki, 307 s pracy powyżej 300 W; mediana
459 W, p5 377, maks 577, SM_ACTIVE 0,696, 1841 tok/s). Do wykresu tylko
część aktywna, przycięta do długości okna Kimi. TP=1 nie używa łącza
między kartami, więc pomiar po NVLinku jest ważny jako odniesienie.
Poprzedni pomiar (08-31, 81 s pracy) urywał linię w 1/4 szerokości
wykresu — stąd sesja 09-04. Q&A: to inny model (Qwen), ale ta sama karta i ten sam
benchmark — pokazujemy, że kartę da się obciążyć. W notes nie rozróżniamy
pochodzenia zrzutu i wykresu; Q&A: zrzut z późniejszej rekonstrukcji
tego samego reżimu (NCCL bez P2P), liczby z oryginalnych pomiarów.

---

## Slajd 3 — Druga anomalia: więcej kart = wolniej (2 min)

Status: ZAAKCEPTOWANY (2026-09-03; tytuł, „zapytania od 64 użytkowników
naraz", TP na slajdzie, jeden kolor, bez efektywności, notes bez Kimi,
puenta użytkownika). Rola: druga obserwacja, kieruje podejrzenie
„między karty"; slajd 4 (DCGM) potem eliminuje kartę. Era PCIe.

### Na slajdzie

> ## Druga anomalia: więcej kart = wolniej
>
> Model za duży na jedną kartę tniemy na N kart — każda liczy swój kawałek
> (**tensor parallelism, TP=N**). Qwen mieści się na jednej, więc możemy go
> uruchomić na 1, 2, 4 i 8 kartach i porównać.
>
> [WYKRES W1': cztery słupki w jednym kolorze, oś Y „tokeny/s łącznie";
> podpis „zapytania od 64 użytkowników naraz": 1 karta **1202** ·
> 2 karty **1404** · 4 karty **680** · 8 kart **257**]
>
> **Dokładanie kart nie zawsze zwiększa przepustowość — od czterech ją
> zmniejsza.**

### Notes

Druga obserwacja jest jeszcze dziwniejsza. Bierzemy model testowy, który
mieści się na jednej karcie, i uruchamiamy go na jednej, dwóch, czterech
i ośmiu. Miara: ile tokenów na sekundę serwer produkuje, gdy pyta go 64
użytkowników naraz. Dwie karty dają siedemnaście procent więcej niż jedna
— słabo, ale w górę. Cztery karty: o połowę mniej niż jedna. Osiem: pięć
razy mniej. Dokładanie sprzętu spowalnia. Pytanie, które stąd wynika: co
takiego dzieje się między kartami, że im więcej ich jest, tym gorzej.

Źródło: `2026-06-11-qwen-tp-curve.md` / v1 W1 (bez linii efektywności).
Q&A: TP=4/8 dla Qwena to konfiguracje badawcze, nie produkcyjne.

---

## Slajd 4 — Wykorzystanie zasobów GPU (2 min)

Status: ZAAKCEPTOWANY (2026-09-03; tytuł i puenta użytkownika; trzy serie:
Qwen 1 / Qwen 8 / Kimi 8 — propozycja użytkownika; liczby czerwcowe). Rola slajdu (po zamianie kolejności 3↔4,
2026-09-03): eliminacja — klasyczni podejrzani (obliczenia, pamięć)
odpadają, zostaje „między kartami" ze slajdu 3; narzędzie + wynik,
bez tłumaczenia dlaczego. Tylko wykres, bez tabeli liczb.

### Na slajdzie

> ## Wykorzystanie zasobów GPU
>
> Pomiar: **DCGM** — liczniki sprzętowe NVIDIA, `dcgmi dmon` z hosta,
> próbka co 1 s, bez zmian w kontenerach i bez zatrzymywania serwera
>
> [WYKRES W2': pionowe słupki grupowane, oś Y 0–100%. Cztery grupy:
> „GPU-Util (nvidia-smi)" · „pobór mocy (z limitu 600 W)" ·
> „jednostki liczące (SM) — % czasu aktywne" · „pamięć HBM — % czasu
> aktywna". W każdej grupie trzy słupki, w tej kolejności:
> **Qwen, 1 karta** (zielony KRESKOWANY, rzadkie kreski, zielony obrys —
> odniesienie) · **Qwen, 8 kart** (zielony pełny) · **Kimi, 8 kart**
> (niebieski pełny) — pełne słupki = przypadki anomalii, kreskowany =
> skala; zieleń = Qwen, niebieski = Kimi jak na slajdach 2–3. Legenda w jednym wierszu nad wykresem, wartości nad
> słupkami, bez siatki. Qwen 1: 100 / 73 / 67 / 39; Qwen 8: 100 / 19 / 5 / 3;
> Kimi 8: 100 / 30 / 20 / 8.]
>
> **Żaden element karty nie pracuje na granicy możliwości.**

### Notes

nvidia-smi ma jedną metrykę obciążenia. DCGM, drugie narzędzie NVIDIA, ma
kilkadziesiąt liczników sprzętowych — czytamy je z hosta, co sekundę, bez
ingerencji w kontenery i bez zatrzymywania serwera. Trzy z nich
odpowiadają na pytanie „czy karta jest zajęta naprawdę". Niebieskie słupki
to Kimi na ośmiu kartach. Moc: trzydzieści procent limitu. Jednostki
liczące, czyli bloki na karcie, które mnożą macierze: aktywne przez
dwadzieścia procent czasu. Pamięć karty: aktywna przez osiem procent
czasu. Zielone słupki to model testowy na jednej karcie: moc siedemdziesiąt
trzy procent, jednostki liczące sześćdziesiąt siedem, pamięć trzydzieści
dziewięć. I GPU-Util dla niej: też sto procent — ta metryka
w ogóle nie rozróżnia tych przypadków. Czyli kartę da się obciążyć. Trzeci
słupek w każdej grupie to ten sam Qwen, ale na ośmiu kartach — prawy
koniec krzywej z poprzedniego slajdu: moc dziewiętnaście procent,
jednostki liczące pięć, pamięć trzy. Jeszcze gorzej niż Kimi. Wspólny
mianownik obu słabych par to osiem kart, nie model. Wniosek z tego slajdu: dwaj klasyczni
podejrzani, za mało mocy obliczeniowej i za wolna pamięć, odpadają. Żaden element
karty nie pracuje na granicy możliwości, więc żaden nie jest wąskim
gardłem. Na karcie nic. Zostaje to, co między kartami — i to jest temat
następnych trzech slajdów.

Źródło: Qwen 8 kart — `2026-06-11-qwen-tp-curve.md` (TP8 c64 active-filtered:
111 W = 19%, SM 0,053, DRAM ~0,03; GPU-Util 100% wg v1 slajd 3). Kimi —
`2026-06-11_nvlink_boundary/kimi_ramp/kimi_c32_dcgmi.txt`
(v1 W2: 199 W, SM 0,20, DRAM 0,070; c=1 niemal identycznie: 170 W, 0,21,
0,093); GPU-Util 100% — zrzut nvidia-smi. Qwen — `2026-06-11-qwen-tp-curve.md` (TP1 c64
active-filtered: 436 W = 73%, SM 0,665, DRAM 0,385); decyzja: liczby
czerwcowe, bez liczenia nowych z 08-31 (zbieżne). GPU-Util Qwena TP1 pod obciążeniem = 100% —
obserwacja prelegenta z sesji (nvidia-smi na żywo); w repo brak zapisanego
zrzutu, więc w Q&A mówić „obserwowane, nie archiwizowane". PCIe na wykresie jako piąta grupa (2026-09-04, wg użytkownika): % z 64 GB/s
(PCIe 5.0 x16, jeden kierunek): Qwen 1 = 0,07 GB/s → 0%; Qwen 8 = 7,18 → 11%;
Kimi 8 = 8,0 (RX, okno stabilne `kimi_c32_dcgmi`) → 13%.

---

## Slajd 5 — Jeden token = jeden krok. Z czego składa się krok? (2,5 min)

Status: ZAAKCEPTOWANY (2026-09-03): wzór słowami w kolorach składników
(życzenie użytkownika; symbole tylko w Q&A), definicja GPU-Util tutaj
(decyzja 3), puenta użytkownika. Kolory składników — ustalone raz, wracają
na slajdach 6 i 7: obliczenia niebieski (zmiana 2026-09-04 wg użytkownika;
wcześniej ciemnoszary) · komunikacja pomarańczowy · przerwy jasnoszary.

### Na slajdzie

> ## Jeden token = jeden krok. Z czego składa się krok?
>
> [GRAFIKA G2: pozioma oś czasu jednego kroku jako pasek. Odcinki w trzech
> kolorach, w realistycznej kolejności: przerwa · obliczenia · komunikacja ·
> obliczenia · komunikacja · … · przerwa. Legenda pod paskiem:
> **obliczenia** (mnożenia macierzy) · **komunikacja** (karty wymieniają
> wyniki i czekają na siebie) · **przerwy** (silnik na CPU przygotowuje
> następny krok). Nad paskiem klamra TYLKO nad odcinkami obliczeń i
> komunikacji, podpis: „kernele — dla GPU-Util wszystko to = zajęte".]
>
> ┌──────────────────────────────────────────────────────────────────┐
> │ **czas kroku = przerwy (silnik na CPU)**                         │
> │ **+ komunikacja (liczba rund × czas jednej rundy)**              │
> │ **+ obliczenia**                                                 │
> └──────────────────────────────────────────────────────────────────┘
> (każdy składnik w kolorze swojego odcinka na pasku)
>
> GPU-Util liczy, przez jaki % czasu na karcie trwał *jakikolwiek* kernel —
> nie, co ten kernel robił.
>
> Kernel, który czeka na synchronizację danych, i kernel, który wykonuje
> obliczenia — dla GPU-Util **oba liczą się do zajętości**.

### Notes

Żeby zrozumieć obie anomalie, trzeba zajrzeć do środka jednego kroku.
Model generuje odpowiedź token po tokenie; każdy token to jeden krok,
u nas od kilku do stu milisekund. Krok nie jest jedną operacją — to setki
małych programów uruchamianych na karcie po kolei, nazywanych kernelami.
Część z nich liczy: mnożenia macierzy. Część komunikuje: karty wymieniają
się wynikami częściowymi i czekają, aż wszystkie skończą — i to powtarza
się wiele razy w jednym kroku, stąd w ramce „liczba rund razy czas rundy".
A między nimi są przerwy, kiedy karta nie robi nic, bo silnik na
procesorze przygotowuje następny krok. Te trzy składniki sumują się do
czasu kroku; nie ma czwartego miejsca, w którym mógłby ginąć czas.

I teraz definicja, na którą czekamy od drugiego slajdu. GPU-Util z
nvidia-smi to procent czasu, w którym na karcie trwał jakikolwiek kernel.
Metryka nie rozróżnia, co kernel robi. Kernel, który w pętli czeka na dane
od sąsiedniej karty, podnosi ją dokładnie tak samo jak kernel liczący
macierz. Stąd sto procent przy trzydziestu procentach mocy: karta cały czas
„coś robiła", ale tym czymś mogło być czekanie. Który z trzech składników
dominuje — pokaże pomiar na następnym slajdzie.

Q&A (nie na głos): zapis z notatki decyzyjnej: T(krok) = F_host +
N_rounds × r(łącze, liczba kart) + W_silicon. Przerwy formalnie obniżają
GPU-Util, ale przy próbkowaniu nvidia-smi krótkie przerwy giną. Definicja
NVML: utilization.gpu = % czasu w oknie próbkowania, w którym wykonywał
się co najmniej jeden kernel.

Układ: ramka ze wzorem = element dominujący (większa czcionka); definicja
i puenta zwykłym tekstem, pogrubione tylko „oba liczą się do zajętości".
Jeśli trzeba ciąć: definicja GPU-Util schodzi do podpisu klamry na G2.

Źródło: v1 slajdy 4 i 6 (D2, wzór); kolory — decyzja 2026-09-03.

---

## Slajd 6 — Rozkład czasu kroku (2 min)

Status: ZAAKCEPTOWANY + uzupełnienie 2026-09-04 (prawo Amdahla słowami,
z rachunkiem w nawiasie, wg użytkownika). 2026-09-03: jeden pasek — Kimi 8 kart pod
obciążeniem (profil c=16 z 06-11, bez podawania liczby użytkowników);
definicja profilera i wniosek wg użytkownika („rejestruje… ze znacznikiem
czasu"; „84% czasu pomiaru to komunikacja"); tytuł i ramka wzoru OK. Kolory składników jak na slajdzie 5.

### Na slajdzie

> ## Rozkład czasu kroku
>
> Pomiar: **torch profiler** — rejestruje każdą operację karty razem ze
> znacznikiem czasu; na podstawie zapisu można określić, ile czasu zajmuje
> każdy składnik kroku
>
> [WYKRES W3': jeden szeroki poziomy pasek 0–100%, podpis „Kimi, 8 kart,
> serwer pod obciążeniem". Odcinki w kolorach ze slajdu 5:
> przerwy (silnik) **10%** · **komunikacja 84%** · obliczenia **5%** ·
> wąski szary odcinek „inne" bez liczby. Pod paskiem ta sama ramka wzoru
> co na slajdzie 5, w tych samych kolorach, bez zmian — pasek jest jej
> wypełnieniem liczbami.]
>
> **84% czasu pomiaru to komunikacja między kartami. Obliczenia: 5%.**
>
> **Prawo Amdahla: nawet gdyby jakiś składnik zniknął zupełnie, krok
> skróci się tylko o tyle, ile ten składnik zajmował.**
> Bez obliczeń (5%) krok trwałby 95% tego, co teraz — zysk najwyżej
> **1,05x** (100 ÷ (100 − 5)).
> Bez komunikacji (84%) krok trwałby 16% — zysk najwyżej **6x** (100 ÷ (100 − 84)).

### Notes

Torch profiler to rejestrator: włączamy go na kilkadziesiąt sekund pracy
serwera i dostajemy zapis każdej operacji na każdej karcie, ze znacznikiem
czasu. Na tej podstawie liczymy, ile czasu zajął każdy z trzech składników
z poprzedniego slajdu. Pasek to Kimi na ośmiu kartach, serwer pod
obciążeniem, wielu użytkowników naraz. Przerwy: dziesięć procent — silnik
ma co robić, karta rzadko czeka na procesor. Obliczenia: pięć procent.
I komunikacja: osiemdziesiąt cztery procent czasu pomiaru. Wiemy już,
który składnik dominuje — nie wiemy jeszcze, co konkretnie w tej
komunikacji tyle trwa. To jest odpowiedź na obraz
z nvidia-smi: sto procent zajętości, bo kernel komunikacyjny trwa;
trzydzieści procent mocy, bo czekanie nie grzeje.

Z tego rozkładu od razu wynika, gdzie jest dźwignia. Prawo Amdahla mówi
prostą rzecz: nawet jeśli jakiś składnik zniknie całkiem, krok skróci się
tylko o tyle, ile ten składnik zajmował. Gdyby obliczenia trwały zero,
krok trwałby dziewięćdziesiąt pięć procent tego, co teraz — sto podzielić
przez dziewięćdziesiąt pięć, jeden i pięć setnych raza szybciej. Szybsza
karta nic tu nie zmieni. Gdyby zniknęła komunikacja, krok trwałby
szesnaście procent — sto podzielić przez szesnaście, sześć razy szybciej.
To jest sufit i to jest cała strategia: pracujemy nad komunikacją.

Co dokładnie dzieje się w tych osiemdziesięciu czterech procentach —
następny slajd.

Q&A (nie na głos): profil przy 16 równoległych zapytaniach, era PCIe
(06-11); kontrola narzutu profilera: ITL profilowany vs nie ±2%. Dla
jednego użytkownika rozkład jest inny: 63% przerwy / 23% komunikacja /
9% obliczenia — wtedy rządzi silnik, nie łącze (wraca na slajdzie 10 jako
„1 użytkownik: 1,2×"). Ten sam mechanizm u Qwena na 4 kartach przy 64
użytkownikach: 53% komunikacja. Amdahl dokładnie: 1/(1−0,839) = 6,2×;
przerwy 10% to drugi lewar (najwyżej 1,11×). Test spójności z efektem:
trace 08-03 — komunikacja skróciła się 2,9×; Amdahl dla udziału 0,839
i przyspieszenia 2,9× daje 1/(0,161 + 0,839/2,9) = 2,2× — zmierzone
2,1× (slajd 10). Po NVLinku komunikacja to 61% kroku → dalszy sufit
1/(1−0,61) = 2,6× (pełna siatka / NVSwitch).

Źródło: `2026-06-11-nvlink-boundary-verdict.md` K2 (NCCL 83,9%, gaps 10%,
compute 4,6%); c=1 — sesja 06-10 (v1 slajd 10); Qwen TP4 c64 — Q4.

---

## Slajd 7 — Komunikacja między kartami: liczba rund × czas jednej rundy (2,5 min)

Status: ZAAKCEPTOWANY (2026-09-03; runda 6: tabela runda → token → odpowiedź,
bez czasu; puenta „14 GB w sensownym czasie"; linijka koszt stały +
przesył dodana; wyjaśnienia: 256 tokenów to krótka odpowiedź, skąd
31 tys. porcji, co znaczy „sensowny czas").

### Na slajdzie

> ## Komunikacja między kartami: <u>liczba rund</u> × czas jednej rundy
>
> [GRAFIKA G3: przepływ jednej warstwy od lewej do prawej: „wejście
> warstwy k" → 4 karty w rzędzie, każda liczy swój kawałek bloku „uwaga" →
> strzałki między wszystkimi kartami „scalenie wyników (all-reduce)" →
> te same 4 karty, każda swój kawałek bloku „FFN/MoE" → drugie scalenie →
> „wejście warstwy k+1". Z boku licznik: „2 scalenia × 61 warstw =
> **122 rundy na każdy token**". Pod spodem: „scalenie jest warunkiem
> przejścia dalej — bez niego żadna karta nie policzy warstwy k+1".]
>
> Ile danych scala jedna runda? Po jednym wektorze na każdego użytkownika
> obsługiwanego naraz. Rund jest 122 na token; krótka odpowiedź to 256
> tokenów (~150 słów):
>
> | użytkowników naraz | na jedną rundę | na jeden token (× 122 rund) | na wszystkie odpowiedzi naraz (× 256 tokenów) |
> |---:|---:|---:|---:|
> | 1 | 14 KB | 1,7 MB | 0,4 GB |
> | 32 | 460 KB | 56 MB | **14 GB** |
>
> Płynny tekst dla użytkownika ≈ 10 tokenów/s → **100 ms na token** →
> 100 ms / 122 rund = **< 1 ms na rundę** (razem z liczeniem)
>
> **Przy 32 użytkownikach, zanim każdy dostanie krótką odpowiedź, karty
> muszą zsynchronizować 14 GB — w 31 tysiącach rund (122 × 256), każda ze
> stałym kosztem i każda w czasie poniżej milisekundy.**

### Notes

Wracamy do ramki ze slajdu piątego i bierzemy pod lupę środkowy składnik:
liczba rund razy czas jednej rundy. Najpierw: co to jest runda. Model jest
pocięty na karty, więc każda karta liczy tylko swój kawałek każdej
warstwy. Po bloku uwagi i po bloku FFN karty muszą dodać do siebie swoje
wyniki częściowe — inaczej następna warstwa nie ma na czym pracować. To
dodawanie nazywa się all-reduce, wykonuje je biblioteka NCCL. Dwa
scalenia na warstwę, sześćdziesiąt jeden warstw: sto dwadzieścia dwie
rundy na każdy wygenerowany token. I każda runda jest synchroniczna:
żadna karta nie liczy dalej, dopóki nie skończy ostatnia.

Teraz: ile danych scala jedna runda. Po jednym wektorze na każdego
użytkownika obsługiwanego w tym kroku. Skąd czternaście kilobajtów: ten
wektor to wewnętrzna reprezentacja jednego tokenu w modelu — u Kimi ma
siedem tysięcy sto sześćdziesiąt osiem liczb, każda zapisana na dwóch
bajtach, razem czternaście kilobajtów. Dla jednego użytkownika tyle
właśnie scala każda runda — nic. Trzydziestu dwóch: prawie pół megabajta — też
niewiele, każdy z nas kopiuje takie pliki bez zastanowienia. Różnica robi
się widoczna, gdy pomnożymy przez to, co już wiemy. Sto dwadzieścia dwie
rundy na token. I tokeny na odpowiedź: w tabeli liczymy dwieście
pięćdziesiąt sześć, czyli około stu pięćdziesięciu słów — to jest krótka
odpowiedź; modele rozumujące potrafią wygenerować dziesięć razy tyle,
zanim w ogóle zaczną odpowiadać. Wychodzi: czterysta megabajtów, zanim
jeden użytkownik dostanie odpowiedź; czternaście gigabajtów, zanim
dostanie ją każdy z trzydziestu dwóch — bo runda niesie ich wszystkich
naraz. Czternaście gigabajtów jako jeden plik dysk skopiuje w kilkanaście
sekund. Ale czternaście gigabajtów w plikach po kilkaset kilobajtów
każdy to zupełnie inna sprawa — każdy, kto kopiował katalog z tysiącami
małych plików, wie, że trwa to wielokrotnie dłużej, bo każdy plik ma
swój narzut. Tu jest dokładnie tak: sto dwadzieścia dwie rundy razy
dwieście pięćdziesiąt sześć tokenów to trzydzieści jeden tysięcy
osobnych rund na jedną odpowiedź, i w każdej wszystkie karty zatrzymują
się, czekają na najwolniejszą i dopiero ruszają dalej.

Stąd dwa koszty każdej rundy. Pierwszy jest stały: uruchomić operację,
uzgodnić, że wszystkie karty są gotowe, poczekać na najwolniejszą —
płacimy go zawsze, przy czternastu kilobajtach tak samo jak przy pół
megabajcie. Drugi to sam przesył: zależy od tego, ile danych i jak
szybkie łącze. Jeden użytkownik płaci sto dwadzieścia dwa razy koszt
stały. Trzydziestu dwóch płaci to samo plus sto dwadzieścia dwa razy
przesył pół megabajta.

I to wszystko ma się zmieścić w czasie sensownym dla użytkownika.
Wyliczenie jest na slajdzie: tekst ma płynąć tak, żeby dało się go czytać
na bieżąco — mniej więcej dziesięć tokenów na sekundę, czyli sto
milisekund na jeden token. W tych stu milisekundach musi się zmieścić sto
dwadzieścia dwie rundy plus całe liczenie. Na jedną rundę zostaje
poniżej milisekundy. Dla porównania: skopiowanie jednego pliku z dysku
na dysk to zwykle kilka milisekund samego narzutu — my mamy na całą rundę,
ze scaleniem między ośmioma kartami, mniej niż jedną. To jest to, co profiler
policzył jako osiemdziesiąt cztery procent. Ile trwa jedna runda i od
czego to zależy — to już pytanie o łącze między kartami. Następne dwa
slajdy.

Q&A (nie na głos): dane na rundę = liczba zapytań × hidden_size (7168) ×
2 bajty (bf16); to ilość danych DO SCALENIA, nie ruch na łączu (ring na
8 kartach przepuszcza przez każdą kartę ~2× tyle); 31 tys. = 122 × 256;
61 warstw i 2 all-reduce/warstwę — z konfiguracji Kimi i implementacji
Megatron-style TP w vLLM; ring all-reduce = 2(N−1) kroków, każdy w tempie
najwolniejszego odcinka. Koszt stały (~30 µs) i przesył — zmierzone na
slajdzie 9. „10 tok/s" to próg czytania na bieżąco (typowe SLO 50–100 ms
TPOT); przy jednym użytkowniku mierzyliśmy 8,7 ms/token, przy 32 — 94 ms
(era PCIe), czyli 32 użytkowników siedziało na granicy tego progu.

Źródło: notatka decyzyjna §4 (122 scalenia, 14 KiB); rozmiary wiadomości
policzone z hidden 7168 × 2 B × c; HF config Kimi K2.

---

## Slajd 8 — Topologia kart GPU: PCIe (2 min)

Status: W ITERACJI (2026-09-04, runda 15: runda zmierzona osobno liczona
teraz na PEŁNEJ ÓSEMCE z wyłączonym P2P (`all-8 nop2p` 238,0 µs) zamiast
grupy cross-4 z mostkami — ta sama grupa i ten sam pomiar co „po" na
slajdzie 9. Runda 14: sekundy do dwóch miejsc;
„przystanki" liczone jako reszta także w sekundach, dzięki czemu obie
kolumny dodają się dokładnie. Runda 12: liczby podane dokładniej
(24,1 s, 23 172 rundy, 0,873 / 0,162 / 0,711 ms); wiersz przemianowany na
„czas komunikacji … bez obliczeń, karty startują równo". Runda 11: tabela dwukolumnowa (na jedną
rundę / w całej odpowiedzi) w kolejności ciągu przyczynowo-skutkowego:
24 s → 83,9% → 0,87 ms → 0,16 ms z rozbiciem → 0,71 ms czekania; punkt wyjścia (24 s, 83,9%, skąd 23 tys.) w zdaniu
nad tabelą; w rundzie zmierzonej osobno rozbite trzy składniki, obliczeń
w rundzie nie ma — są osobnym składnikiem kroku).

### Na slajdzie

> ## Topologia kart GPU: liczba rund × <u>czas jednej rundy</u>
>
> [GRAFIKA G4: 2 procesory (CPU0, CPU1) połączone łączem podpisanym „UPI";
> pod każdym CPU 2 switche PCIe 5.0; pod switchami pary kart (0,1)(2,3)
> | (4,5)(6,7). Wszystkie połączenia w jednym stylu, bez wyróżnień.]
>
> Karty **nie mają bezpośredniego łącza**. Przesył z karty 0 do karty 4
>    idzie: switch → procesor → UPI → procesor → switch. Każde urządzenie
>    po drodze **odbiera całą porcję i dopiero wtedy wysyła ją dalej**.
>
> Zmierzone: odpowiedź 256 tokenów dla 32 użytkowników = **24,10 s**, z czego
> **83,9% to komunikacja** (slajd 6) = 20,2 s. Silnik korzysta z dekodowania
> spekulacyjnego EAGLE3, więc 1 krok daje średnio 1,35 tokena, więc na 256
> tokenów potrzeba 190 kroków (256 ÷ 1,35), a 32 odpowiedzi liczone są
> w tych samych krokach — razem 190 kroków × 122 rundy = **23 tys. rund**.
>
> | | na jedną rundę | w całej odpowiedzi |
> |---|---:|---:|
> | Odpowiedź 256 tokenów dla 32 użytkowników (zmierzone) | | **24,10 s** |
> | Z tego komunikacja — **83,9%** czasu (slajd 6), w podziale na 23 172 rundy | **0,873 ms** | **20,22 s** |
> | Czas komunikacji trasą z pkt 1, **zmierzony osobno — bez obliczeń, karty startują równo** | **0,238 ms** | 5,51 s |
> | &nbsp;&nbsp;w tym przesył 459 kB przy 29,1 GB/s (zmierzone) | 0,016 ms | 0,37 s |
> | &nbsp;&nbsp;w tym koszt stały: start rundy, uzgodnienie kart (zmierzone) | 0,039 ms | 0,89 s |
> | &nbsp;&nbsp;w tym przystanki po drodze: każdy switch i procesor odbiera i wysyła dalej | 0,183 ms | 4,25 s |
> | **→ zostaje czekanie na ostatnią kartę** (0,873 − 0,238) | **0,635 ms** | **14,71 s** |
>
> **Wąskim gardłem nie jest przepustowość PCIe, tylko czas, jaki każda
> runda spędza na najdłuższej trasie i na czekaniu na ostatnią kartę.**

### Notes

Tak wyglądała droga danych między kartami na starcie. Karty nie mają
bezpośredniego połączenia. Żeby karta zero wysłała porcję danych do karty
cztery, dane muszą przejść przez switch PCIe, procesor, łącze UPI między
procesorami, drugi procesor i drugi switch. Na każdym przystanku
urządzenie najpierw odbiera całą porcję, a dopiero potem wysyła ją dalej.
Dla porównania karta zero do karty jeden to jeden switch, jeden
przystanek. A runda scala wszystkie osiem kart naraz, więc zawsze zawiera
tę najdłuższą trasę — i kończy się dopiero wtedy, gdy dotrze ostatnia
karta.

Teraz przejdźmy tabelę wiersz po wierszu, bo to jest cały ciąg
przyczynowo-skutkowy.

Punkt wyjścia: przy trzydziestu dwóch użytkownikach wygenerowanie
odpowiedzi na dwieście pięćdziesiąt sześć tokenów zajęło dwadzieścia
cztery sekundy. To pomiar.

Z poprzedniego slajdu wiemy, że osiemdziesiąt trzy przecinek dziewięć
procent czasu generowania to komunikacja. Z dwudziestu czterech sekund
daje to dwadzieścia sekund i dwie dziesiąte — tyle karty spędziły na
scalaniu wyników.

Rund w tej odpowiedzi było dwadzieścia trzy tysiące. Dzielimy dwadzieścia
sekund przez dwadzieścia trzy tysiące i dostajemy czas jednej rundy
w pracującym serwerze: osiemdziesiąt siedem setnych milisekundy.

Teraz pytanie: na co ten czas idzie? Zmierzyliśmy samą komunikację osobno.
Zatrzymaliśmy model i serwer, karty nie liczyły nic, wykonywały tylko samo
scalenie, w kółko, wszystkie startując równo, po trasie przechodzącej
między połówkami serwera. Wyszło dwieście trzydzieści osiem tysięcznych
milisekundy — i zapamiętajmy, że w tym pomiarze karty startowały równo,
więc nie ma w nim czekania na nikogo.

Te dwieście trzydzieści osiem tysięcznych rozkłada się na trzy części. Sam
przesył danych — czterysta pięćdziesiąt dziewięć kilobajtów przy
zmierzonych dwudziestu dziewięciu gigabajtach na sekundę — szesnaście
tysięcznych milisekundy. Koszt stały, czyli start rundy i uzgodnienie
kart, zanim popłyną dane — trzydzieści dziewięć tysięcznych. Reszta, sto
osiemdziesiąt trzy tysięczne, to przystanki po drodze: każdy switch i procesor musi odebrać
porcję i wysłać ją dalej.

Zwróćcie uwagę, co z tego wynika. Sama komunikacja po najdłuższej trasie
to dwieście trzydzieści osiem tysięcznych, a w serwerze runda trwa osiemset
siedemdziesiąt trzy tysięczne. Różnica — sześćset trzydzieści pięć
tysięcznych milisekundy — to czekanie na ostatnią kartę. Karty nie kończą swojego kawałka liczenia w tym samym
momencie, a runda nie ruszy bez wszystkich.

Razy dwadzieścia trzy tysiące rund: czternaście i siedem dziesiątych
sekundy z dwudziestu czterech. Największy pojedynczy składnik całej odpowiedzi.
Nie mierzyliśmy go osobno — wynika z różnicy, ale nic innego w rundzie nie
zostało.

I dlatego: wąskim gardłem nie jest przepustowość PCIe — sam przesył to
niecała sekunda w całej odpowiedzi — tylko czas, jaki każda runda spędza
na najdłuższej trasie i na czekaniu na ostatnią kartę. Dokładnie w to
celuje modernizacja.

Q&A (nie na głos): 24 s = TPOT med 94 ms × 256 (Kimi c=32, 06-11); krok
= ITL med 127 ms; tokenów na krok 127/94 = 1,35 (Eagle3); kroków 256/1,35
≈ 190; rund 190 × 122 ≈ 23 tys. (slajd 7 mówi 31 tys. przy 1 tokenie na
krok — rząd wielkości ten sam, spekulacja niesie więcej danych na rundę).
83,9% — profil Kimi TP8 c=16, werdykt 06-11 (gaps 10%, compute 4,6%);
24,1 × 0,839 = 20,2 s; 20,2 / 23 172 = 0,873 ms; czekanie 0,873 − 0,162
= 0,635 ms × 23 172 = 14,71 s. Wartości bez zaokrągleń: 24,101 /
20,220 / 5,515 / 0,365 / 0,892 / 4,258 / 14,706 s. „Przystanki" są resztą
z odejmowania i tak też są liczone w sekundach (5,51 − 0,37 − 0,89
= 4,25), dlatego kolumna dodaje się dokładnie. Rozmiar porcji dokładnie: 32 × 7168 × 2 B
= 458 752 B = 459 kB. Uwaga na fałszywą dokładność: 83,9% pochodzi
z profilu c=16, przeniesionego na przebieg c=32 — trzecia cyfra
znacząca w 0,873 ms jest arytmetyczna, nie pomiarowa. 0,238 ms = nccl
all-reduce 512 KB na wszystkich 8 kartach z wyłączonym P2P (08-31, `all-8
nop2p`: 238,0 µs) — to CAŁA komunikacja rundy po tej trasie, nie sam czas
przejścia trasy; osobnego pomiaru „ile trwa jeden przeskok" nie mamy.
Uczciwość: `nop2p` to rekonstrukcja ery PCIe, nie sama era PCIe —
resztkowe ~4 GB/s NVL jeździ ścieżkami poza NCCL-em, więc liczba raczej
ZANIŻA karę. Koszt stały 0,039 ms = `all-8 nop2p` @4 KB (38,5 µs). 0,183 ms
= reszta z odejmowania 0,238 − 0,016 − 0,039. Rozmiar porcji na slajdzie 7:
460 KB przy c=32; mikro-benchmark robiony na 512 KB. Obliczenia NIE są
częścią rundy — to osobny składnik kroku (5%). 29,1 GB/s — p2p_bw
GPU0→GPU4 (07-31); DCGM PCIE_RX średnio 7,2–7,9 GB/s przy c≥8 (06-11).
Ring all-reduce: 2(N−1) = 14 kolejnych przesyłów karta→karta, każdy czeka
na poprzedni; część idzie trasą między połówkami serwera i to na nie czeka
cały łańcuch. Na slajdzie świadomie pominięte. UPI = łącze
międzyprocesorowe. Wyspa-4 NVLink @512 KB: 36 µs; nop2p: 130 µs. Ruch
rzeczywisty > 14 GB (spekulacja, pierścień) — nawet 5× więcej daje 2 s
przesyłu, nie 20. Po NVLinku (08-03, c=32): krok 90 ms, komunikacja 61%
= 55 ms = 0,45 ms na rundę → slajd 9.

Źródło: `results/runs/2026-06-11_nvlink_boundary/kimi_ramp/bench/kimi_c32.json`;
`docs/.../2026-06-11-nvlink-boundary-verdict.md` K2;
`results/summaries/2026-08-31-latencja-dostepu-summary.md` (cross-4 512 KB);
`results/runs/2026-07-31_nvlink_install/nvlink/p2p_bw.txt`.

---

## Slajd 9 — Zmiana: mostki NVLink (2 min)

Status: SZKIC 4 (2026-09-04): na slajdzie zdanie „co daje mostek" — zero
przystanków w czwórce, przystanki tylko między czwórkami. SZKIC 3: trzy składniki rundy po obu stronach
(przesył / koszt stały / przystanki), liczba rund tylko w Q&A. Slajd
przepisany jako „przed/po" tego samego rachunku co slajd 8 — te same trzy wiersze rundy, ta sama grupa 8 kart
w mikro-pomiarze (`all-8 nop2p` 238,0 µs → `all-8` 141,6 µs). Busbw
i koszt stały zeszły do notatek. Puenta do zatwierdzenia.

### Na slajdzie

> ## Zmiana: mostki NVLink — bezpośrednie łącze między kartami
>
> [GRAFIKA G4': ten sam schemat co na slajdzie 8, dorysowane mostki:
> karty 0–3 spięte w „wyspę", karty 4–7 w drugą; między wyspami nadal
> PCIe/CPU. Mostki wyróżnione grubszą linią.]
>
> Mostki tworzą **dwie wyspy**: karty 0–3 i karty 4–7. W ramach jednej wyspy
> **każda karta ma bezpośrednie połączenie z każdą inną** — bez pośredników,
> bez switcha i procesora. Pomiędzy wyspami pozostaje stara droga:
> karta → switch → procesor → UPI → procesor → switch → karta.
>
> | | przed: PCIe | po: mostki NVLink |
> |---|---:|---:|
> | Odpowiedź 256 tokenów dla 32 użytkowników (zmierzone) | **24,10 s** | **11,50 s** |
> | Jedna runda w pracującym serwerze | **0,873 ms** | **0,452 ms** |
> | &nbsp;&nbsp;w tym komunikacja trasą, zmierzona osobno (8 kart, 459 kB) | 0,238 ms | 0,142 ms |
> | &nbsp;&nbsp;&nbsp;&nbsp;w tym przesył 459 kB łączem między czwórkami (29,1 GB/s — bez zmian) | 0,016 ms | 0,016 ms |
> | &nbsp;&nbsp;&nbsp;&nbsp;w tym koszt stały: start rundy, uzgodnienie kart (zmierzone) | 0,039 ms | 0,041 ms |
> | &nbsp;&nbsp;&nbsp;&nbsp;w tym przystanki po drodze | 0,183 ms | **0,085 ms** |
> | &nbsp;&nbsp;w tym czekanie na ostatnią kartę | 0,635 ms | **0,310 ms** |
>
> **Mostki nie przyspieszyły przesyłu ani startu rundy. Usunęły połowę
> przystanków — a krótsza runda to o połowę krótsze czekanie na ostatnią
> kartę. Odpowiedź 2,1× szybciej.**

### Notes

Producent serwera przewiduje opcję: mostki NVLink, które łączą cztery
sąsiednie karty bezpośrednio, z pominięciem switchy PCIe i procesorów.
Zamontowaliśmy dwa — jeden na karty zero do trzy, drugi na cztery do
siedem. Co fizycznie daje mostek? Własny przewód między każdą parą kart
w czwórce. Przypomnijmy slajd ósmy: przekazanie z karty do karty szło
przez switch i procesor, a każde z tych urządzeń najpierw odbierało całą
porcję, a dopiero potem wysyłało ją dalej — to były przystanki. Z mostkiem
karta zero wysyła porcję prosto do karty trzy, po własnym przewodzie, i
nikt po drodze jej nie odbiera. Zero przystanków wewnątrz czwórki.
Przystanki zostały tylko tam, gdzie porcja przechodzi między czwórkami —
tam droga jest stara, przez procesory i UPI. Kimi pracuje na wszystkich
ośmiu kartach, czyli na dwóch czwórkach, więc w każdej rundzie część
przekazań nadal jedzie starą drogą — i dlatego przystanki spadły
o połowę, a nie do zera.

Powtórzyliśmy dokładnie ten sam rachunek co przed chwilą i to jest cała
tabela.

Odpowiedź na dwieście pięćdziesiąt sześć tokenów przy trzydziestu dwóch
użytkownikach: dwadzieścia cztery sekundy przed, jedenaście i pół po.
Dwa razy szybciej.

Runda w pracującym serwerze: osiemset siedemdziesiąt trzy tysięczne
milisekundy przed, czterysta pięćdziesiąt dwie po.

Sama komunikacja po trasie, zmierzona tak samo jak poprzednio — te same
osiem kart, ta sama porcja, zmienione tylko łącze: dwieście trzydzieści
osiem tysięcznych przed, sto czterdzieści dwie po. I spójrzcie, co w tych
trzech składnikach się zmieniło, a co nie. Przesył: bez zmian, szesnaście
tysięcznych — bo najdłuższa trasa nadal przechodzi między czwórkami starym
łączem, dwadzieścia dziewięć gigabajtów na sekundę przed i po. Żeby nie
było nieporozumienia: wewnątrz czwórki przesył jest czternaście razy
szybszy, zmierzyliśmy to. Ale runda na ośmiu kartach musi przejść między
czwórkami, a tam łącze zostało stare — i to ono wyznacza tempo całej
rundy. Dlatego Kimi na ośmiu kartach z tej przepustowości nie korzysta. Koszt
stały: bez zmian, około czterdziestu tysięcznych — mostki nie skracają
startu rundy. Zmieniły się przystanki: ze stu osiemdziesięciu trzech
tysięcznych do osiemdziesięciu pięciu — bo wewnątrz czwórek przystanków
już nie ma, zostały tylko na przejściach między czwórkami.

I najważniejsze: czekanie na ostatnią kartę spadło z sześciuset
trzydziestu pięciu tysięcznych do trzystu dziesięciu. Ponad dwukrotnie.
To nie jest osobny efekt — to konsekwencja. Karta, która szybciej kończy
swoją rundę, wcześniej dociera do następnej, więc pozostałe krócej na nią
czekają. Krótsza runda działa dwa razy: raz na sobie, drugi raz na
czekaniu.

Dlaczego tylko dwa razy, a nie więcej? Bo mostek łączy cztery karty,
a Kimi potrzebuje ośmiu. Po modernizacji komunikacja to nadal
sześćdziesiąt jeden procent czasu — z osiemdziesięciu czterech. Sufit
istnieje i wiemy, gdzie leży.

W notes (jeśli pytanie z sali): przy pełnej siatce w wyspie vLLM włącza
własny kernel all-reduce, który skraca też koszt stały — dlatego model
mieszczący się w jednej czwórce zyskuje więcej niż Kimi.

Q&A (nie na głos): po NVLinku (08-03, `kimi/bench/kimi_c32.json`): TPOT
med 44,90 ms → 256 × 44,90 = 11,50 s; ITL med 90,22 ms → 2,01 tokena na
krok → 127 kroków × 122 = 15 545 rund. Trace 08-03: komunikacja 61,1%
spanu (rank0) / 59,7% (rank7), compute 30,2% → 11,50 × 0,611 = 7,02 s
/ 15 545 = 0,452 ms na rundę. Mikro 08-31 @512 KB, ta sama para co na
slajdzie 8: `all-8 nop2p` 238,0 µs → `all-8` 141,6 µs (1,68×). Koszt
stały: `all-8 nop2p` @4 KB 38,5 µs → `all-8` @4 KB 41,1 µs — bez zmian
w granicach szumu. Przesył: łącze między czwórkami to nadal PCIe/UPI,
p2p_bw GPU0→GPU4 29,1 GB/s po montażu (07-31) — identyczne jak przed;
w czwórce 132,8 GB/s. Przystanki = reszta: 0,142 − 0,016 − 0,041 = 0,085
ms. Dowód „zero przystanków w czwórce": ta sama runda 512 KB w samej
czwórce (`wyspa-4`) = 36,3 µs, czyli prawie sam koszt stały; na ośmiu
kartach 141,6 µs — cała różnica to przejścia między czwórkami. Liczba rund po NVLinku inna niż przed (15 545 vs 23 172), bo silnik
trafia 2,01 tokena na krok zamiast 1,35 — dlatego slajd 9 porównuje
tylko czas rundy i sekundy odpowiedzi, nie liczbę rund. Czekanie
= różnica: 0,452 − 0,142 = 0,310 ms → 4,82 s (przed: 14,71 s). Zysk
całkowity 24,10 / 11,50 = 2,10× — zgodny z benchowym 2,08×. Przepustowość
przy dużych porcjach (8 MB): wyspa-4 197,5 GB/s vs nop2p 13,8 (14×), ale
pełna ósemka tylko 14,9 GB/s — ruch między wyspami psuje wynik i to
tłumaczy, czemu Kimi dostaje 2×, a nie 14×. Koszt stały bez zmian
(~30–40 µs po obu stronach) — mostki skracają jazdę, nie wsiadanie;
dlatego przy jednym użytkowniku zysk jest minimalny (slajd 10). Custom
all-reduce vLLM: aktywny tylko dla pełnej siatki (TP4 w wyspie), nie dla
TP8 — dawka 1,0–1,2× przy c64, szum ±6%. Uczciwość: `nop2p` to
rekonstrukcja ery PCIe, nie sama era PCIe.

Źródło: `results/summaries/2026-08-03-nvlink-day-summary.md` §2;
`results/runs/2026-08-03_nvlink_gap_fill/kimi/bench/kimi_c32.json`;
`results/summaries/2026-08-31-latencja-dostepu-summary.md` §1.

---

## Slajd 10 — Efekt: przed i po mostkach (2,5 min) — PODSUMOWANIE

Status: SZKIC 4 (2026-09-04, wg użytkownika): dwa wykresy w tok/s (Qwen
TP4 i TP8 bez słupka kontrolnego TP1; pod nim Kimi TP8 tylko c=32), pod
nimi tabela zysku = puenta slajdu, pod nią koszt. Zdanie z odpowiedzią na
tytuł tylko w notatkach. Wyjątek od reguły „≤1 wykres" — decyzja
użytkownika. Dryf Qwen TP1 tylko w Q&A.

### Na slajdzie

> ## Efekt: przepustowość przed i po mostkach
>
> [WYKRES W5a — Qwen, 64 użytkowników naraz, tok/s: dwie pary słupków
> przed (szary) / po (niebieski): **4 karty 680 → 2129** ·
> **8 kart 257 → 1625**. Liczby nad słupkami.]
>
> [WYKRES W5b — Kimi, 8 kart, 32 użytkowników naraz, tok/s: jedna para
> słupków przed (szary) / po (niebieski): **285 → 608**. Liczby nad
> słupkami.]
>
> | | przed | po | zysk |
> |---|---:|---:|---:|
> | Qwen, 4 karty, 64 użytkowników | 680 tok/s | 2129 tok/s | **3,1×** |
> | Qwen, 8 kart, 64 użytkowników | 257 tok/s | 1625 tok/s | **6,3×** |
> | Kimi, 8 kart, 32 użytkowników | 285 tok/s | 608 tok/s | **2,1×** |
>
> Łączny koszt: **2 mostki × ~4,5 tys. zł ≈ 9 tys. zł na serwer**.

### Notes

Wracamy do przepustowości, od której zaczęliśmy na slajdzie trzecim. Ta
sama praca, ten sam serwer, zmienione tylko łącze.

Górny wykres to model testowy Qwen przy sześćdziesięciu czterech
użytkownikach naraz. Cztery karty: sześćset osiemdziesiąt tokenów na
sekundę przed, ponad dwa tysiące po — trzy razy. Osiem kart: dwieście
pięćdziesiąt siedem przed — pamiętacie, więcej kart było wolniej — tysiąc
sześćset po. Sześć razy. Osiem kart nadal nie wygrywa z czterema, bo runda
musi przejść między czwórkami, ale przestało być gorzej niż na jednej.

Dolny wykres to Kimi na ośmiu kartach przy trzydziestu dwóch
użytkownikach naraz: dwieście osiemdziesiąt pięć tokenów na sekundę
przed, sześćset osiem po — to jest ten rachunek ze slajdów osiem
i dziewięć. Dwa razy.

Tabela zbiera zysk — to jest puenta tego slajdu. I koszt: dwa mostki po
około cztery i pół tysiąca złotych, dziewięć tysięcy na serwer.

I odpowiedź na pytanie z tytułu. Sto procent zajętości, trzydzieści
procent mocy. Wąskim gardłem nie był żaden zasób karty — ani jednostki
liczące, ani pamięć, ani przepustowość łącza. Było czekanie kart na
siebie, sto dwadzieścia dwa razy na każdy token. Mostki skróciły rundę,
a krótsza runda to krótsze czekanie — dlatego dają od dwóch do sześciu
razy pod obciążeniem. Dla jednego użytkownika prawie nic — Kimi z dwóch
i dwóch dziesiątych sekundy na jedną i dziewięć — bo tam karty prawie nie
czekają na siebie. Jeśli wasz serwer obsługuje jedną osobę naraz,
oszczędźcie te dziewięć tysięcy.
Jeśli obsługuje kilkanaście — to najtańsza modernizacja, jaką znam.
Dziękuję.

Q&A (nie na głos): tok/s = `output_throughput` z benchy. Qwen c=64, SWE
custom, 600 promptów, 256-out, MTP-3 w obu erach, ten sam obraz vLLM
v0.20.0: przed = 06-11 (`qwen-tp-curve`: TP1/2/4/8 = 1202/1404/680/257),
po = 08-31 (grid, ciepłe: 1710/2050/2129/1625); replikacja TP4 c64 07-31:
2022/1989. **UWAGA — konfund:** TP1 nie dotyka mostków, a też urosło
1202 → 1710 (+42%) między czerwcem a sierpniem, przy tym samym obrazie
i tej samej konfiguracji; kara zimnego benchu (08-03) tłumaczy 10–15%,
nie 42% — reszta niewyjaśniona. Uczciwe porównanie Qwen: względem TP1
tej samej ery — przed: TP4 = 0,57× TP1, TP8 = 0,21× TP1; po: TP4 = 1,25×
TP1, TP8 = 0,95× TP1. Wniosek jakościowy (TP8 z „gorzej niż jedna karta"
na „prawie jak jedna") się utrzymuje; surowe 6,3× może zawierać dryf.
Kimi TP8: przed 06-11 (c1/c8/c16/c32 = 75/86/73/285), po = 07-31 c1 110,
08-03 `ramp_c8` 328 (jeden bieg, Grafana), 08-03 gap_fill c16 501, c32
608. c=16 przed = 73 tok/s to anomalia ery PCIe potwierdzona trzema
powtórkami (73/71/67). Odpowiedź w sekundach (TPOT × 256): c1 2,2 → 1,9
s; c8 20,1 → 4,5; c16 48,8 → 6,7; c32 24,1 → 11,5. Cena mostka ~4,5 tys.
zł/szt. — wg użytkownika.

Źródło: `results/summaries/2026-06-11-qwen-tp-curve.md`;
`results/summaries/2026-08-31-latencja-dostepu-summary.md` §2;
`results/runs/2026-06-11_nvlink_boundary/kimi_ramp/bench/kimi_c{1,8,16,32}.json`;
`results/runs/2026-07-31_nvlink_install/kimi/bench/kimi_c1.json`;
`results/runs/2026-08-03_nvlink_gap_fill/kimi/bench/kimi_c{16,32}.json`;
`results/runs/2026-08-03_domkniecie_grafana/grafana/bench/ramp_c8.json`.

---

## Slajdy zapasowe (tylko Q&A) — kolejność wg użytkownika 2026-09-04

- **Z1 — Kimi przed i po mostkach (c=32):** wykres W7 (pobór mocy w czasie,
  8 linii przed w szarym + 8 linii po w niebieskim, limit 600 W) + tabela
  rozkładu czasu kroku: komunikacja 83,9% → 61,1%, obliczenia 4,6% → 30,2%.
  Liczniki DCGM: moc 192 → 303 W, SM 0,19 → 0,37, HBM 0,065 → 0,132, PCIe RX
  8,0 → 4,8 GB/s przy NVL RX 9,0. Cały zysk 2,1× ze skrócenia komunikacji;
  Amdahl 1/(0,161 + 0,839/2,9) = 2,2×; dalszy sufit 2,6×. Uczciwość: okna
  mocy mają różną długość (361 vs 168 s) — na wykresie linie „po" kończą się
  wcześniej. Źródło: 08-03 §2; `2026-06-11_nvlink_boundary/kimi_ramp/
  kimi_c32_dcgmi.txt` i `2026-08-03_nvlink_gap_fill/kimi/kimi_c32_dcgmi.txt`.
- **Z2 — Qwen po mostkach (c=32):** wykres W6 (tok/s: 1/2/4/8 kart =
  2015 / 2467 / 2990 / 1974) + pod nim udział komunikacji 0 / 12 / 18 /
  58% (jakościowo). Źródło: 08-31 §2–3.
(Z3 — tabela decyzyjna — usunięta 2026-09-04 wg użytkownika; na slajdach
zapasowych bez dat sesji i bez wzmianek o kontroli narzutu profilera.)

## Wykresy i grafiki — WYKONANE (2026-09-04)

Generator: `generate_charts.py` (matplotlib → `charts/*.svg`); diagramy G1–G4'
inline SVG w `index_src.html`; sklejka: `build_index.py` → `index.html`
(bez notatek — decyzja użytkownika; notatki zostają w tym pliku).

| id | slajd | treść | dane |
|---|---|---|---|
| G1 | 1 | 8 kart, klamra Kimi nad ósemką, klamry Qwen 1/2/4/8 GPU | — |
| W0' | 2 | moc w czasie: 8 linii Kimi (niebieski) + Qwen 1 karta (zielony) + limit 600 W | `kimi_c32_dcgmi.txt` (06-11), `tp1_c64_long_dcgmi.txt` (09-04) |
| W1' | 3 | 4 słupki tok/s, 1/2/4/8 kart, c64, era PCIe | `batched_c64.json` (06-10), `qwen_tp_curve` (06-11) |
| W2' | 4 | słupki grupowane 4 liczniki × (Qwen 1 kreskowany, Qwen 8, Kimi 8) | stałe z podsumowań (czerwcowe) |
| G2 | 5 | oś czasu kroku, 3 kolory, klamra nad kernelami, legenda | — |
| W3' | 6 | pasek 10 / 84 / 5 / inne | verdict K2 (06-11) |
| G3 | 7 | warstwa: 4 karty → scalenie → 4 karty → scalenie, licznik 122 | — |
| G4 / G4' | 8 / 9 | topologia PCIe / + mostki w czwórkach | — |
| W5a | 10 | Qwen 4 i 8 kart, c64, przed/po tok/s | `qwen_tp_curve` (06-11), `bench_tp4isl`/`bench_tp8` (08-31) |
| W5b | 10 | Kimi 8 kart, c32, przed/po tok/s | `kimi_c32.json` (06-11, 08-03) |
| W6 | Z2 | Qwen 1/2/4/8 kart, c32, po mostkach, tok/s | `bench_tp{1,2isl,4isl,8}/*_c32.json` (08-31) |
| W7 | Z1 | Kimi 8 kart c32, pobór mocy w czasie, przed i po mostkach | `kimi_c32_dcgmi.txt` (06-11) i (08-03 gap_fill) |

## Budżet czasu

0: 1 · 1: 1,5 · 2: 1,5 · 3 (krzywa TP): 2 · 4 (DCGM): 2 · 5: 2,5 · 6: 2 · 7: 2,5 · 8: 1,5 ·
9: 2 · 10: 2,5 = **21 min** → na próbie ciąć notes slajdów 3 i 6.
