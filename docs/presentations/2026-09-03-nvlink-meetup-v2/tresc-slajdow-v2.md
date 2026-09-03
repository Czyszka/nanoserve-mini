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

Status: tytuł ZAAKCEPTOWANY; reszta SZKIC.

### Na slajdzie

> # 100% GPU-Util, a tylko 30% limitu mocy.
> # Co jest wąskim gardłem?
>
> Badania wydajnościowe serwera 8×H200 i ich efekty — studium przypadku NVLink

### Notes

To jest prawdziwy odczyt z naszego serwera: osiem kart H200, każda pokazuje
sto procent obciążenia, a pobiera jedną trzecią mocy. Przez kilka tygodni
szukaliśmy, co jest wąskim gardłem. Opowiem, co znaleźliśmy, co zmieniliśmy
w serwerze i ile to dało — w sekundach, dla użytkownika. Odpowiedź na
pytanie z tytułu będzie na ostatnim slajdzie, w jednym zdaniu.

---

## Slajd 1 — Stanowisko pomiarowe (1,5 min)

Status: SZKIC.

### Na slajdzie

> ## Stanowisko pomiarowe
>
> [GRAFIKA G1: serwer → 8 kart w rzędzie; nad kartami 0–7 klamra „Kimi-K2.6:
> 1 bilion parametrów, 554 GB wag — potrzebuje wszystkich 8 kart";
> nad kartą 0 osobno „Qwen3.6-35B — mieści się na jednej karcie (model testowy)"]
>
> - serwer: 2× CPU, 8× NVIDIA H200 NVL (143 GB każda), karty połączone
>   magistralą PCIe 5.0 — stan wyjściowy
> - silnik: vLLM w kontenerach Docker
> - obciążenie: własny benchmark — zadania programistyczne (SWE), 256 tokenów
>   odpowiedzi

### Notes

Środowisko to serwer laboratoryjny z ośmioma kartami H200. Na starcie karty
rozmawiały ze sobą wyłącznie przez magistralę PCIe — tak jak dyski czy karty
sieciowe. Główny model to Kimi, bilion parametrów; same wagi zajmują 554 GB,
więc nie da się go uruchomić na mniej niż ośmiu kartach. Drugi model, Qwen,
mieści się na jednej karcie — używamy go jako narzędzia badawczego, bo
możemy go uruchamiać na jednej, dwóch, czterech albo ośmiu kartach i
porównywać. Obciążenie generujemy własnym benchmarkiem: zadania
programistyczne, odpowiedzi po 256 tokenów, zawsze po rozgrzewce silnika.

Źródło: v1 slajd 2; `infrastructure.md` §2.2.

---

## Slajd 2 — Anomalia (1,5 min)

Status: SZKIC. Decyzja 3: bez definicji GPU-Util (ta na slajdzie 5).

### Na slajdzie

> ## Anomalia
>
> [ZRZUT: nvidia-smi — 8 wierszy, kolumny GPU-Util 100% i moc ~175 W / 600 W;
> `../2026-07-31-nvlink-meetup/nvidia_smi_crop.png`]
>
> **Osiem kart: 100% obciążenia — i po ~30% limitu mocy. Przez cały benchmark.**
>
> Kto widział coś takiego u siebie?

### Notes

Tak wyglądał serwer pod pełnym obciążeniem — 64 równoległych zapytań do
Kimi. nvidia-smi, narzędzie, na które każdy patrzy pierwsze, pokazuje sto
procent na każdej karcie. A w kolumnie mocy: sto siedemdziesiąt, sto
osiemdziesiąt watów, przy limicie sześciuset. To nie był chwilowy przestój
między zadaniami — ten stan trwał przez cały benchmark. Karta, która
naprawdę liczy, ciągnie czterysta, pięćset watów. Zapamiętajmy ten obraz:
wrócimy do niego, kiedy będziemy wiedzieli, co te karty właściwie robiły.

Źródło: zrzut z rekonstrukcji nop2p 08-03 (172–181 W); historyczne PCIe:
111–185 W (dcgmi 06-11) — w notes nie rozróżniamy.

---

## Slajd 3 — Pomiary DCGM: żaden zasób nie pracuje (2 min)

Status: SZKIC.

### Na slajdzie

> ## Żaden zasób karty nie jest wykorzystany
>
> Narzędzie: **DCGM** (liczniki sprzętowe NVIDIA, odczyt z hosta, co 1 s)
>
> [WYKRES W2': cztery poziome paski 0–100%, Kimi pod obciążeniem:
> GPU-Util **100%** · pobór mocy **30%** limitu · jednostki liczące (SM)
> aktywne **20%** czasu · pamięć karty (HBM) aktywna **8%** czasu;
> szary pasek odniesienia: „ten sam typ karty, model na 1 karcie:
> moc 73%, SM 68%, HBM 39%"]
>
> **GPU-Util mówi 100%. Liczniki mówią: nic nie jest nasycone.**

### Notes

nvidia-smi ma jedną metrykę obciążenia. DCGM, drugie narzędzie NVIDIA, ma
kilkadziesiąt liczników sprzętowych — czytamy je z hosta, co sekundę, bez
ingerencji w kontenery. Trzy z nich odpowiadają na pytanie „czy karta jest
zajęta naprawdę". Moc: trzydzieści procent limitu. Jednostki liczące,
czyli te bloki na karcie, które mnożą macierze: aktywne przez dwadzieścia
procent czasu. Pamięć karty: aktywna przez osiem procent czasu. Dla
porównania szary pasek: ten sam typ karty, ale model, który mieści się na
jednej karcie — moc siedemdziesiąt procent, jednostki liczące prawie
siedemdziesiąt. Czyli kartę da się obciążyć. Tylko w tej konfiguracji,
z modelem rozłożonym na osiem kart, nic na karcie nie pracuje blisko
granicy. To nie jest wąskie gardło w klasycznym sensie — żaden zasób nie
jest wysycony. Musimy szukać gdzie indziej.

Źródło: v1 slajd 5 (Kimi TP8 c64: 199 W, SM 0,20, DRAM 0,070); odniesienie
Qwen TP1 c64 era PCIe (436 W, SM 0,665, DRAM 0,39).

---

## Slajd 4 — Więcej kart = wolniej (2 min)

Status: SZKIC. Decyzja 1: tu definicja TP i c.

### Na slajdzie

> ## Druga anomalia: więcej kart = wolniej
>
> Model za duży na jedną kartę tniemy na N kart — każda liczy swój kawałek
> (**tensor parallelism, TP=N**). Qwen mieści się na jednej, więc możemy
> go uruchomić na 1, 2, 4 i 8 kartach i porównać.
>
> [WYKRES W1': cztery słupki, tokeny/s dla 64 równoległych zapytań (**c=64**):
> 1 karta **1202** · 2 karty **1404** · 4 karty **680** · 8 kart **257**]
>
> **Cztery karty są 2× wolniejsze niż jedna. Osiem — 5× wolniejsze.**
> Coś między kartami zjada czas.

### Notes

Druga obserwacja jest jeszcze dziwniejsza. Bierzemy model testowy, który
mieści się na jednej karcie, i uruchamiamy go na jednej, dwóch, czterech
i ośmiu. Miara: ile tokenów na sekundę serwer produkuje dla 64 równoległych
zapytań. Dwie karty dają siedemnaście procent więcej niż jedna — słabo,
ale w górę. Cztery karty: o połowę mniej niż jedna. Osiem: pięć razy mniej.
Dokładanie sprzętu spowalnia. Dla Kimi nie możemy zrobić takiej krzywej —
działa tylko na ośmiu — ale to właśnie tam siedzimy na co dzień: na prawym
końcu tego wykresu. Pytanie, na które musimy odpowiedzieć: co takiego
dzieje się między kartami, że im więcej ich jest, tym gorzej.

Źródło: v1 slajd 12 / W1 (`2026-06-11-qwen-tp-curve.md`). Uwaga w Q&A:
TP=4/8 dla Qwena to konfiguracje badawcze, nie produkcyjne.

---

## Slajd 5 — Z czego składa się krok i co liczy GPU-Util (2,5 min)

Status: SZKIC. Decyzja 3: definicja GPU-Util tutaj.

### Na slajdzie

> ## Jeden token = jeden krok. Z czego składa się krok?
>
> [GRAFIKA G2: oś czasu jednego kroku (~10–100 ms) jako pasek podzielony
> na odcinki w trzech kolorach: **obliczenia** (mnożenia macierzy) ·
> **komunikacja** (karty wymieniają wyniki — i czekają na siebie) ·
> **przerwy** (silnik na CPU przygotowuje następny krok);
> pod paskiem klamra na całą długość: „GPU-Util = 100%, bo *cokolwiek*
> trwało"]
>
> - model generuje tekst token po tokenie; każdy token to jeden **krok**
> - krok to ciąg małych programów na karcie (**kerneli**): obliczenia,
>   komunikacja, kopie
> - **GPU-Util** liczy, przez jaki % czasu *jakikolwiek* kernel trwał —
>   nie, co robił
>
> **Kernel, który czeka na inną kartę, liczy się do 100% tak samo jak
> kernel, który liczy.**

### Notes

Żeby zrozumieć obie anomalie, trzeba zajrzeć do środka jednego kroku.
Model generuje odpowiedź token po tokenie; każdy token to jeden krok, u nas
od kilku do stu milisekund. Krok nie jest jedną operacją — to setki małych
programów uruchamianych na karcie po kolei, nazywanych kernelami. Część
z nich liczy: mnożenia macierzy. Część komunikuje: karty wymieniają się
wynikami i czekają, aż wszystkie skończą. A między nimi są przerwy, kiedy
karta nie robi nic, bo silnik na procesorze przygotowuje następny krok.
I teraz definicja: GPU-Util z nvidia-smi to procent czasu, w którym na
karcie trwał jakikolwiek kernel. Metryka nie rozróżnia, co kernel robi.
Kernel, który w pętli czeka na dane od sąsiedniej karty, podnosi ją
dokładnie tak samo jak kernel liczący macierz. Stąd sto procent przy
trzydziestu procentach mocy: karta cały czas „coś robiła", ale tym czymś
mogło być czekanie. Który z trzech kolorów dominuje — pokaże pomiar.

Źródło: v1 slajd 4 (definicja NVML), grafika D2.

---

## Slajd 6 — Rozkład czasu kroku: profil (2 min)

Status: SZKIC. Dane: profil Kimi ery PCIe (ilościowy); seria Qwen TP1→8
po NVLinku jako slajd zapasowy (jakościowy).

### Na slajdzie

> ## Pomiar: w kroku dominuje czekanie na inne karty
>
> Narzędzie: **torch profiler** — rejestrator osi czasu karty: co dokładnie
> i jak długo wykonywała w każdej milisekundzie
>
> [WYKRES W3': dwa poziome słupki skumulowane 0–100%, Kimi na 8 kartach:
> **1 użytkownik:** przerwy (silnik) 63% · komunikacja 23% · obliczenia 9%
> **16 użytkowników:** przerwy 10% · **komunikacja 84%** · obliczenia 5%]
>
> **Pod obciążeniem karty przez 84% kroku czekają na siebie.
> Liczą przez 5%.**

### Notes

Torch profiler to rejestrator: włączamy go na kilkadziesiąt sekund
i dostajemy pełną oś czasu każdej karty. Potem sumujemy, ile czasu zajął
każdy kolor z poprzedniego slajdu. Dwa pomiary Kimi na ośmiu kartach.
Pierwszy: jeden użytkownik. Największa część kroku to przerwy — sześćdziesiąt
trzy procent czasu karta nie wykonuje nic, czeka na silnik. Komunikacja
dwadzieścia trzy procent, obliczenia dziewięć. Drugi pomiar: szesnastu
użytkowników naraz. Przerwy prawie znikają — silnik ma co robić — i na
wierzch wychodzi komunikacja: osiemdziesiąt cztery procent kroku karty
wymieniają wyniki i czekają na siebie. Obliczenia: pięć procent. To jest
odpowiedź na obraz z nvidia-smi: sto procent zajętości, bo kernel
komunikacyjny trwa; trzydzieści procent mocy, bo czekanie nie grzeje.
Zostaje pytanie, dlaczego komunikacja jest aż tak droga.

Źródło: v1 slajdy 10/12 (`2026-06-11-nvlink-boundary-verdict.md` K2;
trace c16 narzut ~2%). W notes NIE mówimy o anomalii c=16.

---

## Slajd 7 — Dlaczego komunikacja: 122 dogadania na token (2,5 min)

Status: SZKIC (wersja z rundy 4, bez zmian).

### Na slajdzie

> ## Gdzie znika czas: karty muszą się dogadać 122 razy na każde słowo
>
> [GRAFIKA G3: 4 karty w rzędzie; klamra „jedna warstwa modelu"; po warstwie
> strzałki między wszystkimi kartami z podpisem „dodajemy wyniki
> (all-reduce)"; licznik „× 61 warstw × 2 = **122 razy na token**"]
>
> Każde dogadanie kosztuje:
>
> - **stałe ~30 µs** — start, uzgodnienie, czekanie na najwolniejszą kartę
>   (zawsze, nawet dla 1 użytkownika)
> - **+ przesył danych** — tym dłuższy, im więcej użytkowników naraz
>   i im wolniejsze łącze
>
> **1 użytkownik → prawie sam koszt stały. 32 użytkowników → przesył
> dominuje. Szybsze łącze skraca tylko przesył.**

### Notes

Model jest pocięty na osiem kart, więc po każdej warstwie karty muszą dodać
do siebie swoje wyniki częściowe — to operacja all-reduce, wykonuje ją
biblioteka NCCL. Warstw jest sześćdziesiąt jeden, dodawanie robi się dwa
razy na warstwę, więc na jeden token karty dogadują się sto dwadzieścia
dwa razy. I żadna nie może liczyć dalej, dopóki nie skończy ostatnia.

Każde dogadanie ma dwa koszty. Pierwszy jest stały: uruchomić operację,
ustalić, że wszystkie karty są gotowe, poczekać na najwolniejszą. Około
trzydziestu mikrosekund, niezależnie od tego, ile danych przesyłamy.
Drugi koszt to sam przesył — zależy od tego, ile danych i jak szybkie
łącze. A ile danych zależy od liczby użytkowników: jeden użytkownik to
kilkanaście kilobajtów na dogadanie, przesył trwa mikrosekundę i ginie w
koszcie stałym. Trzydziestu dwóch użytkowników to pół megabajta — przesył
trwa dziesiątki mikrosekund, tyle co koszt stały albo więcej.

Stąd cała reszta. Dla jednego użytkownika krok to sto dwadzieścia dwa razy
koszt stały, którego żadne łącze nie skraca. Dla wielu użytkowników krok
to głównie przesył — i tu szybsze łącze może pomóc. To samo tłumaczy
niski ruch na PCIe, o którym za chwilę: przez większość rundy karty nie
przesyłają, tylko czekają.

Źródło: koszt stały — sesja 08-31 (28–54 µs, wyspa/nop2p); 122 —
notatka decyzyjna §4; rozmiar wiadomości c × 7168 × 2 B.

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
| W2' | 3 | 4 paski % (util/moc/SM/HBM) + pasek odniesienia | v1 W2 |
| W1' | 4 | 4 słupki tok/s TP1/2/4/8 c64 PCIe | v1 W1 (bez linii efektywności) |
| G2 | 5 | oś czasu kroku, 3 kolory, klamra GPU-Util | v1 D2 |
| W3' | 6 | 2 słupki skumulowane Kimi c1 / c16 | v1 W3 |
| G3 | 7 | 4 karty, all-reduce, licznik 122 | v1 D3 (uproszczony) |
| G4 / G4' | 8 / 9 | topologia przed / po (ten sam rysunek + mostki) | v1 D1 / D1-PO |
| W5a | 10 | Kimi: sekundy przed/po dla 1/8/16/32 | nowy |
| W5b | 10 | Qwen TP4 c64 przed/po tok/s | v1 W5 (połowa) |

## Budżet czasu

0: 1 · 1: 1,5 · 2: 1,5 · 3: 2 · 4: 2 · 5: 2,5 · 6: 2 · 7: 2,5 · 8: 1 ·
9: 2 · 10: 2,5 = **20,5 min** → na próbie ciąć notes slajdów 3 i 6.
