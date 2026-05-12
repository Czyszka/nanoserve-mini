# Jak praktycznie czytać artykuły

Źródło metody: S. Keshav, "How to Read a Paper", ACM SIGCOMM Computer Communication
Review, Vol. 37, No. 3, July 2007. Ten dokument adaptuje metodę trzech przejść do
`nanoserve-mini`, czyli czytania pod kątem LLM inference, vLLM, benchmarków,
obserwowalności i późniejszego profilowania kerneli.

## Cel

Nie czytamy artykułów po to, żeby przepisać ich streszczenie. Po każdej istotnej pracy
powinny zostać trzy rzeczy:

- decyzja, czy paper jest ważny dla obecnej fazy projektu,
- krótka notatka z twierdzeniami, dowodami i ograniczeniami,
- jeden możliwy eksperyment albo pomiar, który da się wykonać w `nanoserve-mini`.

Najważniejsza zasada: nie zaczynaj od liniowego czytania od pierwszej do ostatniej
strony. Czytaj w przejściach i po każdym przejściu zdecyduj, czy głębsze czytanie ma
sens teraz.

## Przed czytaniem: ustaw cel (dodatek projektowy)

Czas: 2-3 minuty.

Zanim otworzysz paper, zapisz:

- dlaczego czytasz go właśnie teraz,
- z którą fazą roadmapy się łączy,
- czego szukasz: modelu mentalnego, metryki, algorytmu, baseline'u, ograniczenia vLLM
  czy pomysłu na eksperyment,
- ile czasu maksymalnie chcesz na niego poświęcić.

Jeżeli nie da się odpowiedzieć na "dlaczego teraz?", paper zwykle powinien poczekać.

## Przejście 1: kwalifikacja

Czas: 5-10 minut.

Czytaj tylko:

- tytuł, abstrakt i wstęp,
- nagłówki sekcji i podsekcji,
- konkluzję,
- bibliografię, żeby rozpoznać znane prace i nazwiska.

Po tym przejściu odpowiedz na pięć pytań:

- **Category:** jaki to typ pracy: measurement, system, scheduling, kernel, survey,
  analiza istniejącego systemu, prototype?
- **Context:** z jakimi pracami się łączy i które pojęcia trzeba znać wcześniej?
- **Correctness:** czy założenia wyglądają sensownie? Dla paperów LLM inference: czy
  pasują do GPU servingu, workloadów i ograniczeń systemowych?
- **Contributions:** co autorzy twierdzą, że wnoszą?
- **Clarity:** czy paper jest napisany tak, że da się odtworzyć argument?

Decyzja po przejściu 1:

- **skip:** poza zakresem albo zbyt słabe założenia,
- **background:** zostaw krótki opis i wróć, gdy pojawi się konkretny problem,
- **pass 2:** czytaj dalej, bo praca wpływa na aktualną fazę,
- **pass 3 later:** oznacz jako ważną pracę do głębokiego czytania przed implementacją
  lub write-upem.

## Przejście 2: zrozumienie argumentu

Czas: 30-60 minut.

Czytaj całość uważnie, ale jeszcze nie rekonstruuj każdego dowodu ani detalu
implementacyjnego. Celem jest umieć wyjaśnić komuś główną tezę i dowody.

W trakcie czytania notuj na marginesie albo w pliku kluczowe twierdzenia,
wątpliwości, brakujące pojęcia i liczby. Końcowe 8-12 zdań ma powstać z tych
notatek, nie z pamięci.

Zwróć uwagę na:

- definicje metryk: TTFT, TPOT, throughput, latency percentiles, memory usage, cost,
  utilization,
- workload: długości promptów, długości outputów, concurrency, arrival process, model,
  batch size, cache hit ratio,
- baseline: czy porównują z vLLM, Orca, FasterTransformer, TensorRT-LLM, własnym
  systemem, naive batchingiem,
- hardware i software: GPU, CPU, interconnect, wersje frameworków, precision,
  serving setup,
- wykresy: osie, jednostki, percentyle, error bars, zakresy eksperymentów,
- ablations: czy pokazują, który komponent rzeczywiście daje zysk,
- ograniczenia: czego nie mierzą, jakich scenariuszy unikają, gdzie wynik może się
  nie przenieść.

Po przejściu 2 ułóż 8-12 zdań:

- problem,
- główny pomysł,
- mechanizm działania,
- najważniejszy wynik liczbowy,
- co autorzy uznają za bottleneck,
- jaki jest trade-off,
- co to znaczy dla `nanoserve-mini`.

Jeżeli po tym przejściu paper dalej jest nieczytelny, wybierz jedną z trzech decyzji:

- **defer/skip:** odłóż paper, jeżeli teraz nie jest wart kosztu poznawczego albo
  wychodzi poza zakres obecnej fazy,
- **background first:** zapisz brakujące pojęcia, przeczytaj materiał wprowadzający
  i wróć później,
- **pass 3 now:** przejdź do rekonstrukcji mimo trudności, jeżeli paper jest krytyczny
  dla eksperymentu, decyzji architektonicznej albo write-upu.

## Przejście 3: rekonstrukcja

Czas: około 4-5 godzin dla początkujących albo około 1 godzina dla doświadczonych
czytelników. Rób tylko dla prac kluczowych dla obecnej fazy albo finalnego write-upu.

Zachowuj się tak, jakbyś miał odtworzyć pracę:

- przepisz algorytm własnymi słowami albo jako pseudokod,
- wypisz wszystkie założenia, także ukryte,
- sprawdź, czy metryki rzeczywiście mierzą deklarowany problem,
- narysuj pipeline systemu: request arrival, prefill, decode, KV cache, scheduler,
  kernel, sieć, storage,
- porównaj projekt autorów z tym, jak działa vLLM,
- zapisz, które elementy da się zmierzyć bez implementacji całego systemu,
- zaznacz brakujące cytowania do prac, które autorzy powinni byli uwzględnić,
- zapisuj pomysły na future work i własne eksperymenty, gdy pojawiają się w trakcie
  rekonstrukcji,
- zapisz jeden minimalny eksperyment w repo.

Po przejściu 3 powinieneś umieć odtworzyć strukturę paperu z pamięci: problem,
założenia, metoda, eksperymenty, wyniki, słabe punkty, brakujące cytowania i pytania
otwarte.

## Jak czytać paper systemowy lub performance

W LLM inference najłatwiej dać się złapać na duże procenty bez kontekstu. Dla każdej
pracy pytaj:

- względem jakiego baseline'u liczą speedup,
- czy porównanie jest fair względem tego samego modelu, workloadu i hardware'u,
- czy optymalizują średnią, p95/p99, koszt, throughput czy jeden wybrany scenariusz,
- czy zysk pochodzi z algorytmu, cache, schedulera, kernela, batchingu, mniejszej
  jakości, mniejszej precyzji albo innej konfiguracji,
- czy autorzy pokazali profiling albo tylko opisali bottleneck słownie,
- czy praca poprawia prefill, decode, pamięć KV, scheduling, kernel, routing,
  observability czy benchmark methodology,
- czy wynik jest czymś, co `nanoserve-mini` ma implementować, czy tylko zjawiskiem,
  które trzeba umieć zmierzyć.

## LLM inference lens

To jest obowiązkowa sekcja każdej notatki o paperze z reading listy projektu.

Najpierw sklasyfikuj optymalizowany etap:

- prefill,
- decode,
- oba,
- scheduling wokół prefill/decode,
- pamięć wokół KV cache i batchingu,
- operacja kernel-level,
- obserwowalność albo metodologia pomiarowa.

Potem przypisz główny cel:

- niższy TTFT,
- niższy TPOT,
- wyższy throughput,
- niższa pamięć,
- niższy koszt,
- lepsze SLO albo tail latency,
- lepsze utilization.

Następnie odpowiedz na pięć pytań praktycznych:

- jaki bottleneck autorzy uznają za najważniejszy,
- jakie liczby, profiling albo eksperymenty pokazują na poparcie tej tezy,
- co poświęcają,
- jaki jest związek z vLLM,
- jaki minimalny eksperyment można uruchomić w `nanoserve-mini`.

Minimalny eksperyment nie musi implementować paperu. Często wystarczy zmierzyć objaw:
TTFT przy długim promptcie, TPOT przy długim decode, wpływ concurrency, wpływ podobnych
prefiksów, tail latency przy mieszanym workloadzie albo wykorzystanie GPU/cache podczas
serii requestów.

## Jak robić mini literature survey

Dla nowego tematu, np. prefix caching albo prefill/decode disaggregation:

1. Znajdź 3-5 ostatnich prac z tematu.
2. Zrób przejście 1 na każdej.
3. Przejrzyj sekcje related work i bibliografie.
4. Jeżeli znajdziesz aktualny, wysokiej jakości survey, przeczytaj go i zatrzymaj pętlę
   survey na teraz. W `nanoserve-mini` takim punktem startowym jest *Efficient LLM
   Serving Survey*.
5. Jeżeli dobrego surveyu nie ma albo potrzebujesz głębszego zejścia, wypisz
   powtarzające się prace, autorów i konferencje.
6. Sprawdź najnowsze prace kluczowych badaczy: Google Scholar, strony autorów, strony
   laboratoriów i repozytoria projektów.
7. Sprawdź recent proceedings topowych konferencji, które powtarzają się w
   bibliografiach.
8. Pobierz kluczowe prace, ale czytaj głęboko tylko te, które wracają w cytowaniach
   albo bezpośrednio łączą się z eksperymentem.
9. Zrób przejście 2 na wybranych pracach.
10. Jeżeli wiele paperów cytuje jedną nieprzeczytaną pracę jako fundament, dodaj ją do
    kolejki i wróć do kroku 2.

Survey jest skończony na potrzeby projektu, gdy masz mapę: główne problemy, główne
systemy, typowe metryki, typowe workloady, powtarzające się bottlenecki i jedną listę
eksperymentów możliwych w `nanoserve-mini`.

## Recommended first use

Domyślnie używaj **lekkiego template'u** `docs/templates/paper-note-lite.md`.
Pełny `docs/templates/paper-note-template.md` zarezerwuj wyłącznie dla prac
fundamentalnych dla `nanoserve-mini` — czyli takich, które są bezpośrednim
fundamentem decyzji architektonicznych albo finalnych write-upów.

**Pełny template** stosuj dla:

- *Efficient LLM Serving Survey*,
- *PagedAttention / vLLM*,
- *Efficiently Scaling Transformer Inference*,
- *Orca*,
- *Sarathi-Serve*,
- *FlashAttention*.

**Lite template** stosuj dla wszystkiego pozostałego: pojedynczych prac
mierzących objaw, alternatywnych systemów, prac stycznych z reading listy,
tła do konkretnego eksperymentu.

Domyślny przepływ pierwszego użycia:

1. Krok przed czytaniem (cel) → przejście 1 (kwalifikacja). Decyzja: skip /
   background / pass 2 / pass 3 later.
2. Jeżeli zostaje przy projekcie, otwórz `paper-note-lite.md`, wypełnij sekcje
   "5-line summary" i "LLM inference lens" w trakcie pass 2. Zostań na lite,
   chyba że paper jest na liście fundamentalnych powyżej.
3. Pełny template włączaj świadomie, dopiero gdy decydujesz, że zrobisz
   pass 3 i paper będzie użyty w write-upie.

Cel jest taki, żeby większość paperów kończyła się na 1 stronie notatki,
a fundamenty dostały pełną notatkę dopiero kiedy realnie wpływają na decyzje.

## Konwencja notatek

- PDF-y trzymaj lokalnie w `docs/learning/papers/`; ten katalog jest ignorowany przez Git.
- Notatki Markdown trzymaj jako commitowalne artefakty, najlepiej zwięzłe.
- Do większości paperów używaj `docs/templates/paper-note-lite.md`. Pełnego
  `docs/templates/paper-note-template.md` używaj tylko dla prac wymienionych
  w sekcji "Recommended first use".
- Po każdym ważnym paperze dopisz w `docs/reading-list.md` 2-3 zdania w sekcji notatek
  własnych albo dodaj osobny plik z pełną notatką, jeżeli paper będzie użyty w write-upie.
- W notatce nie przepisuj całego paperu. Zapisuj decyzje, dowody, ograniczenia i pomiary,
  które wpływają na projekt.
