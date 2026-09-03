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

> # 100% GPU-Util, a tylko 30% limitu mocy.
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
> (0–3), „8 GPU" (0–7), z podpisem: „Qwen3.6-35B — 67 GB wag → mieści się
> na jednej karcie, więc do testów można go uruchomić na 1, 2, 4 lub 8"]
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

Status: ZAAKCEPTOWANY (2026-09-03): bez c, 111–185 W, W0' z linią Qwen
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
> **Osiem kart z Kimi: 100% obciążenia — a pobór mocy 111–185 W z 600 W,
> przez cały benchmark. Karta, która naprawdę liczy: 400–600 W.**
>
> Kto widział coś takiego u siebie?

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
`2026-08-31_latencja_dostepu/qwen/tp1_c64_dcgmi.txt`, GPU0 (98 próbek,
średnia całego okna 404 W, część aktywna ~430–450 W, max 592 W; do
wykresu tylko część aktywna, przycięta do długości okna Kimi). TP=1 nie
używa łącza między kartami, więc pomiar po NVLinku jest ważny jako
odniesienie. Q&A: to inny model (Qwen), ale ta sama karta i ten sam
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
zrzutu, więc w Q&A mówić „obserwowane, nie archiwizowane". PCIe RX/TX celowo poza slajdem (wraca na slajdzie 8).

---

## Slajd 5 — Jeden token = jeden krok. Z czego składa się krok? (2,5 min)

Status: ZAAKCEPTOWANY (2026-09-03): wzór słowami w kolorach składników
(życzenie użytkownika; symbole tylko w Q&A), definicja GPU-Util tutaj
(decyzja 3), puenta użytkownika. Kolory składników — ustalone raz, wracają
na slajdach 6 i 7: obliczenia ciemnoszary · komunikacja pomarańczowy ·
przerwy jasnoszary (nie niebieski/zielony — te znaczą Kimi/Qwen).

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

Status: ZAAKCEPTOWANY (2026-09-03): jeden pasek — Kimi 8 kart pod
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
trzydzieści procent mocy, bo czekanie nie grzeje. Co dokładnie dzieje się w tych
osiemdziesięciu czterech procentach — następny slajd.

Q&A (nie na głos): profil przy 16 równoległych zapytaniach, era PCIe
(06-11); kontrola narzutu profilera: ITL profilowany vs nie ±2%. Dla
jednego użytkownika rozkład jest inny: 63% przerwy / 23% komunikacja /
9% obliczenia — wtedy rządzi silnik, nie łącze (wraca na slajdzie 10 jako
„1 użytkownik: 1,2×"). Ten sam mechanizm u Qwena na 4 kartach przy 64
użytkownikach: 53% komunikacja.

Źródło: `2026-06-11-nvlink-boundary-verdict.md` K2 (NCCL 83,9%, gaps 10%,
compute 4,6%); c=1 — sesja 06-10 (v1 slajd 10); Qwen TP4 c64 — Q4.

---

## Slajd 7 — Komunikacja między kartami: liczba rund × czas jednej rundy (2,5 min)

Status: W ITERACJI (2026-09-03; wg uwag użytkownika: tytuł „Komunikacja
między kartami: …" z podkreśloną liczbą rund; tabela runda → token →
odpowiedź, bez kolumny czasu, wiersze 1 i 32; puenta „14 GB w sensownym
czasie"; linijka koszt stały + przesył — OPCJONALNA, do decyzji; tylko rundy, bez kart/łącza —
łącze i koszt stały/przesył przechodzą na slajdy 8–9; „token"; wzrost
ilości danych z liczbą użytkowników pokazany; puenta o liczbie rund
i rosnących danych; pasek z warstwami zostaje; bez analogii).

### Na slajdzie

> ## Komunikacja między kartami: <u>liczba rund</u> × czas jednej rundy
>
> [GRAFIKA G3: przepływ jednej warstwy od lewej do prawej: „wejście
> warstwy k" → 4 karty w rzędzie, każda liczy swój kawałek bloku „uwaga" →
> strzałki między wszystkimi kartami „scalenie wyników (all-reduce)" →
> te same 4 karty, każda swój kawałek bloku „FFN/MoE" → drugie scalenie →
> „wejście warstwy k+1". Z boku licznik: „2 scalenia × 61 warstw =
> **122 rundy na każdy token**". Pod spodem: „scalenie jest warunkiem
> przejścia dalej — żadna karta nie liczy warstwy k+1, dopóki nie skończy
> ostatnia".]
>
> Ile danych scala jedna runda? Po jednym wektorze na każdego użytkownika
> obsługiwanego naraz — a rund jest 122 na token i 256 tokenów na odpowiedź:
>
> | użytkowników naraz | na jedną rundę | na jeden token (× 122) | na jedną odpowiedź (× 256) |
> |---:|---:|---:|---:|
> | 1 | 14 KB | 1,7 MB | 0,4 GB |
> | 32 | 460 KB | 56 MB | **14 GB** |
>
> [OPCJONALNIE — jedna linijka pod tabelą, do decyzji: „Każda runda
> kosztuje: **stałe** (start, uzgodnienie, czekanie na najwolniejszą —
> niezależnie od ilości danych) **+ przesył** (zależy od ilości danych
> i od łącza)".]
>
> **Przy 32 użytkownikach mamy do zsynchronizowania 14 GB na jedną
> odpowiedź — w 31 tysiącach porcji, w czasie sensownym dla użytkownika.**

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
użytkownika obsługiwanego w tym kroku. Jeden użytkownik to czternaście
kilobajtów na rundę — nic. Trzydziestu dwóch: prawie pół megabajta — też
niewiele, każdy z nas kopiuje takie pliki bez zastanowienia. Różnica
robi się widoczna, gdy pomnożymy przez to, co już wiemy. Sto dwadzieścia
dwie rundy na token i dwieście pięćdziesiąt sześć tokenów na odpowiedź:
przy jednym użytkowniku czterysta megabajtów na odpowiedź, przy trzydziestu
dwóch — czternaście gigabajtów. Dysk skopiuje tyle w kilkanaście sekund,
ale w jednym ciągu. Tu te czternaście gigabajtów jest pocięte na
trzydzieści jeden tysięcy małych porcji, a po każdej porcji wszystkie
karty czekają na najwolniejszą. I to wszystko musi się
zmieścić w czasie, który użytkownik uzna za sensowny — żeby widział płynny
tekst, każda z tych rund ma na wszystko poniżej milisekundy. To jest to,
co profiler policzył jako osiemdziesiąt cztery procent. Ile trwa jedna
runda i od czego to zależy — to już pytanie o łącze między kartami. Ile trwa jedna taka runda i od czego to
zależy — to już pytanie o łącze między kartami. Następne dwa slajdy.

Q&A (nie na głos): dane na rundę = liczba zapytań × hidden_size (7168) ×
2 bajty (bf16); to ilość danych DO SCALENIA, nie ruch na łączu (ring na
8 kartach przepuszcza przez każdą kartę ~2× tyle); 31 tys. = 122 × 256; 61 warstw i 2 all-reduce/warstwę — z konfiguracji Kimi
i implementacji Megatron-style TP w vLLM; ring all-reduce = 2(N−1)
kroków, każdy w tempie najwolniejszego odcinka. Koszt stały rundy
(~30 µs) i przesył — na slajdzie 9, gdzie są zmierzone.

Źródło: notatka decyzyjna §4 (122 scalenia, 14 KiB); rozmiary wiadomości
policzone z hidden 7168 × 2 B × c; HF config Kimi K2.

---

## Slajd 8 — Jak karty były połączone: PCIe (1 min)

Status: SZKIC.

### Na slajdzie

> ## Stan wyjściowy: karty rozmawiają przez PCIe i procesory
>
> [GRAFIKA G4: 2 CPU połączone łączem; pod każdym CPU 2 switche PCIe;
> pod switchami pary kart (0,1)(2,3) | (4,5)(6,7); wyróżniona trasa
> GPU0 → switch → CPU0 → CPU1 → switch → GPU4]
>
> - PCIe 5.0 x16: nominalnie 128 GB/s (obie strony); zmierzony przesył
>   karta↔karta **25–50 GB/s**
> - średnie użycie łącza pod obciążeniem: **~7 GB/s**
>
> **Łącze nie było zapchane. Było wolne, kiedy już coś nim jechało —
> a przez resztę rundy stało puste.**

### Notes

Tak wyglądała droga danych między kartami na starcie: przez switch PCIe,
czasem przez procesor, a między połówkami serwera przez łącze między dwoma
procesorami. Dwie liczby. Zmierzony przesył między dwiema kartami: od
dwudziestu pięciu do pięćdziesięciu gigabajtów na sekundę, zależnie od
trasy. Średnie użycie łącza pod obciążeniem: siedem gigabajtów na sekundę.
Czyli łącze nie było zapchane — przez większość czasu stało puste, bo
karty czekały na koszt stały. Ale kiedy pół megabajta już jechało, jechało
wolno. Wąskim gardłem nie jest przepustowość „na papierze", tylko czas
przesyłu jednej porcji w każdej ze stu dwudziestu dwóch rund.

Źródło: `infrastructure.md` §2.2 (schemat); P2P 25–50 GB/s (v1 slajd 15
baseline), 7,2–7,9 GB/s (K1/Q1 06-11). UPI bez nazwy na slajdzie.

---

## Slajd 9 — Zmiana: mostki NVLink (2 min)

Status: SZKIC. Custom all-reduce → notes. Busbw wraca na slajd (decyzja 5
cofnięta, patrz `slajdy-v2.md` §E).

### Na slajdzie

> ## Zmiana: mostki NVLink — bezpośrednie łącze między kartami
>
> [GRAFIKA G4': ten sam schemat co na slajdzie 8, dorysowane mostki:
> karty 0–3 spięte w „wyspę", karty 4–7 w drugą; między wyspami nadal
> PCIe/CPU]
>
> Zmierzyliśmy oba koszty rundy, przed i po:
>
> | | PCIe / bez mostków | NVLink w wyspie |
> |---|---:|---:|
> | koszt stały rundy | ~30 µs | ~30 µs — **bez zmian** |
> | przesył dużej porcji (8 MB) | 14 GB/s | **197 GB/s — 14× szybciej** |
>
> Mostek łączy **4 karty**. Kimi na 8 kartach ma dwie wyspy — część
> dogadań nadal idzie starą drogą.

### Notes

Producent serwera przewiduje opcję: mostki NVLink, które łączą cztery
sąsiednie karty bezpośrednio, z pominięciem PCIe i procesorów. Zamontowaliśmy
dwa — jeden na karty zero do trzy, drugi na cztery do siedem. Każda
czwórka to „wyspa": wewnątrz wyspy każda para kart ma własne, bezpośrednie
łącze. Między wyspami droga zostaje stara.

Zmierzyliśmy oba koszty rundy z poprzedniego slajdu. Koszt stały:
trzydzieści mikrosekund przed i trzydzieści po — mostki go nie ruszają, bo
to nie jest czas jazdy, tylko czas wsiadania. Przesył dużej porcji: z
czternastu do prawie dwustu gigabajtów na sekundę, czternaście razy
szybciej. Stąd od razu wiemy, czego się spodziewać: dla jednego użytkownika
prawie nic, bo tam liczy się koszt stały; dla wielu użytkowników — dużo.
I jedna konsekwencja geometrii: Kimi działa na ośmiu kartach, czyli na
dwóch wyspach. Część dogadań musi przejść między wyspami starą drogą,
więc Kimi zyska mniej niż model mieszczący się w jednej wyspie.

W notes (jeśli pytanie z sali): przy pełnej siatce w wyspie vLLM włącza
własny kernel all-reduce, który skraca też koszt stały — dlatego Qwen na
4 kartach zyskał 3×, powyżej tego, co daje sama przepustowość.

Źródło: `2026-08-31-latencja-dostepu-summary.md` §1 (wyspa-4 @8 MB
197,5 vs nop2p 13,8; 16 KB 28–54 µs obie strony). Uczciwość: „bez
mostków" = NCCL z wyłączonym P2P (rekonstrukcja), nie czerwcowe PCIe.

---

## Slajd 10 — Efekt: ile sekund oszczędza użytkownik (2,5 min) — PODSUMOWANIE

Status: SZKIC. Decyzja 8: ostatni slajd. Dwa wykresy jeden pod drugim.

### Na slajdzie

> ## Efekt dla użytkownika: odpowiedź (256 tokenów) przed i po
>
> [WYKRES W5a — Kimi, 8 kart: pary słupków „sekund czekania" per liczba
> użytkowników naraz:
> 1 użytkownik **2,2 → 1,9 s** (1,2×) · 8 **20 → 4,5 s** (4,5×) ·
> 16 **49 → 6,7 s** (7×) · 32 **24 → 11,5 s** (2×)]
>
> [WYKRES W5b — Qwen, 4 karty (jedna wyspa), 64 użytkowników:
> przepustowość **680 → 2022 tok/s (3×)**]
>
> Koszt: 2 mostki × ~4,5 tys. zł ≈ **9 tys. zł**.
>
> **Wąskim gardłem nie był żaden zasób karty — było czekanie kart na
> siebie w 122 rundach na token. Mostki skracają przesył, nie czekanie:
> zysk 2–7× pod obciążeniem, ~0 dla pojedynczego użytkownika.**

### Notes

Wracamy do użytkownika. Górny wykres to Kimi na ośmiu kartach: ile sekund
czeka użytkownik na odpowiedź o długości 256 tokenów, przed i po montażu.
Jeden użytkownik na pustym serwerze: 2,2 sekundy przed, 1,9 po — dwadzieścia
procent, tak jak przewidział koszt stały. Ośmiu użytkowników naraz:
dwadzieścia sekund przed, cztery i pół po. Szesnastu: prawie minuta przed —
serwer z ośmiu kart obsługiwał szesnaście osób wolniej niż jedną — siedem
sekund po. Trzydziestu dwóch: dwadzieścia cztery sekundy przed, jedenaście
i pół po. Dolny wykres to model testowy na czterech kartach w jednej
wyspie: trzy razy więcej tokenów na sekundę — więcej niż Kimi, bo nie
przekracza granicy wysp. Koszt: dwa mostki, około dziewięciu tysięcy
złotych, przy serwerze wartym setki tysięcy.

I odpowiedź na pytanie z tytułu. Wąskim gardłem nie był żaden zasób karty
— ani jednostki liczące, ani pamięć, ani przepustowość łącza na papierze.
Było czekanie kart na siebie, sto dwadzieścia dwa razy na każdy token.
Mostki NVLink skracają przesył, ale nie skracają czekania — dlatego dają
dwa do siedmiu razy pod obciążeniem i prawie nic dla jednego użytkownika.
Jeśli wasz serwer obsługuje jedną osobę naraz, oszczędźcie te dziewięć
tysięcy. Jeśli obsługuje kilkanaście — to najtańsza modernizacja, jaką
znam. Dziękuję.

Źródło: tabela w `slajdy-v2.md` (slajd 10, runda 2): TPOT Kimi 8,7→7,44;
78,5→17,5; 190,5→26,0; 94,1→44,9 ms × 256 tok. Qwen TP4 c64 680→2022.
Zastrzeżenia (Q&A): c=8 „po" = jeden bieg; 49 s przy c=16 to anomalia
ery PCIe (transportowa, zniknęła z mostkami); wszystkie „po" ciepłe.
Cena serwera — do potwierdzenia przez prelegenta lub wyciąć.

---

## Slajdy zapasowe (tylko Q&A)

- **Z1 — Qwen po NVLinku, krzywa TP (c=32):** 2015 / 2467 / 2990 / 1974
  tok/s — 4 karty przestały być karą (vs slajd 4). Źródło: 08-31 §2.
- **Z2 — Profil Qwen po NVLinku, udział komunikacji (c=32):** TP1 0% →
  TP2 12% → TP4 18% → TP8 58% (jakościowo — narzut profilera nie przeszedł
  kontroli). Źródło: 08-31 §3.
- **Z3 — Profil Kimi po NVLinku (c=32):** komunikacja 84% → 61%,
  obliczenia 5% → 30%; cały zysk 2× ze skrócenia komunikacji. Źródło:
  08-03 §2.
- **Z4 — Tabela decyzyjna:** kiedy NVLink 4-way ma sens (notatka
  decyzyjna §3.1): model na 1–2 kartach → nie; TP≥4 + wielu użytkowników
  → tak; pojedynczy czat → ≤1,3×.

## Wykresy i grafiki do zrobienia

| id | slajd | treść | dane |
|---|---|---|---|
| G1 | 1 | serwer + 8 kart, Kimi na 8 / Qwen na 1 | — |
| W2' | 4 | słupki pionowe grupowane: 4 liczniki × (Qwen 1, Qwen 8, Kimi 8) | v1 W2 + qwen-tp-curve |
| W1' | 3 | 4 słupki tok/s TP1/2/4/8 c64 PCIe | v1 W1 (bez linii efektywności) |
| G2 | 5 | oś czasu kroku, 3 kolory (szary/pomarańcz/jasnoszary), klamra nad kernelami + ramka wzoru | v1 D2 |
| W3' | 6 | 1 pasek skumulowany Kimi 8 kart pod obciążeniem (c16) + ramka wzoru | v1 W3 |
| G3 | 7 | 4 karty, warstwa (uwaga/FFN), 2 scalenia, licznik 122 + tabelka danych/rundę | v1 D3 (uproszczony) |
| G4 / G4' | 8 / 9 | topologia przed / po (ten sam rysunek + mostki) | v1 D1 / D1-PO |
| W5a | 10 | Kimi: sekundy przed/po dla 1/8/16/32 | nowy |
| W5b | 10 | Qwen TP4 c64 przed/po tok/s | v1 W5 (połowa) |

## Budżet czasu

0: 1 · 1: 1,5 · 2: 1,5 · 3 (krzywa TP): 2 · 4 (DCGM): 2 · 5: 2,5 · 6: 2 · 7: 2,5 · 8: 1 ·
9: 2 · 10: 2,5 = **20,5 min** → na próbie ciąć notes slajdów 3 i 6.
