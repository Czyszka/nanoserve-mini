# Notatka projektowa: lokalny AI support dla zespołu na serwerze 8xH200

## 1. Cel projektu

Celem projektu jest uruchomienie lokalnego środowiska AI support dla zespołu programistycznego na serwerze 8xH200 oraz przygotowanie technicznej podstawy do dalszego wykorzystania lokalnych modeli LLM w pracy zespołu.

Projekt zakłada przejście z obecnego rozwiązania opartego o Ollama i stację 2xA6000 na wydajniejsze środowisko oparte o vLLM oraz serwer 8xH200. Obecne środowisko potwierdziło, że lokalne modele LLM są przydatne w pracy zespołu, ale zaczyna być ograniczeniem pod względem wydajności, obsługi większych modeli, liczby równoległych użytkowników i możliwości prowadzenia wiarygodnych benchmarków.

Po 12 tygodniach oczekiwanym efektem jest działające środowisko lokalnej inferencji LLM, dostępne przez:

- Open WebUI jako ogólny chat dla użytkowników zespołu,
- Claude Code CLI jako wsparcie pracy programistycznej,
- wtyczkę do IDE / VS Code korzystającą z lokalnego endpointu,
- benchmarki modeli i promptów,
- podstawowy monitoring w Grafanie,
- workload testowy radiogramów KF jako trudny przypadek do oceny modeli LLM.

Projekt ma charakter wdrożeniowo-badawczy. Z jednej strony dostarcza zespołowi praktyczny AI support, z drugiej pozwala zbudować metodykę oceny modeli, promptów i kosztu inferencji na lokalnej infrastrukturze GPU.

## 2. Aktualny stan

Obecnie w zespole funkcjonuje pierwszy proof-of-concept lokalnego AI supportu:

- Open WebUI działa jako interfejs chatowy dla użytkowników,
- backend jest oparty o Ollama,
- modele są uruchamiane na stacji 2xA6000,
- Claude Code CLI działa z lokalnymi modelami przez małą aplikację Python,
- aplikacja pobiera listę dostępnych modeli, pozwala użytkownikowi wybrać model i uruchamia Claude Code z odpowiednią konfiguracją.

To rozwiązanie potwierdziło sens dalszego rozwoju lokalnego AI supportu, ale obecna infrastruktura jest niewystarczająca dla kolejnego etapu.

Główne ograniczenia obecnego rozwiązania:

- ograniczona wydajność przy większej liczbie użytkowników,
- ograniczona możliwość uruchamiania dużych modeli open-source,
- brak pełnej obserwowalności działania modeli,
- brak ustandaryzowanych benchmarków TTFT, TPOT, latency i throughput,
- brak systematycznego porównywania modeli, promptów i konfiguracji,
- ograniczona możliwość testowania długich kontekstów oraz bardziej złożonych zadań reasoningowych.

## 3. Uzasadnienie wykorzystania serwera 8xH200

Serwer 8xH200 pozwala przejść z prostego proof-of-concept do realnego środowiska lokalnej inferencji LLM dla zespołu.

Projekt wymaga tego zasobu, ponieważ docelowo środowisko ma obsługiwać:

- wielu użytkowników jednocześnie,
- większe modele open-source,
- lokalne endpointy dla Open WebUI, Claude Code CLI i IDE,
- dłuższe konteksty,
- zadania programistyczne wymagające analizy kodu,
- testy jakości promptów na własnym workloadzie domenowym,
- porównania modeli,
- benchmarki wydajnościowe,
- przyszłe eksperymenty z dużymi modelami MoE, jeżeli będą możliwe do uruchomienia lokalnie.

Celem nie jest samo uruchomienie modelu na mocniejszym sprzęcie. Celem jest zbudowanie powtarzalnego procesu oceny modeli, promptów i kosztu inferencji. Dzięki temu będzie można świadomie odpowiedzieć na pytania:

- który model nadaje się do danego typu zadań,
- jakie są opóźnienia przy realnym użyciu,
- jak rośnie koszt obliczeniowy wraz z długością promptu,
- jak zachowuje się model przy wielu równoległych użytkownikach,
- kiedy warto używać dużego modelu, a kiedy wystarczy mniejszy model lub regułowy mechanizm,
- które scenariusze mają sens jako dalsze wdrożenia dla zespołu.

## 4. Docelowa architektura

Docelowo serwer 8xH200 będzie centralnym backendem inference dla lokalnych modeli LLM.

```text
Użytkownicy zespołu
   |
   |-- Open WebUI
   |-- Claude Code CLI
   |-- VS Code / IDE plugin
   |-- aplikacje wewnętrzne / workloady testowe
        |
        v
Lokalny endpoint LLM / API proxy
        |
        v
vLLM inference backend
        |
        v
Serwer 8xH200
        |
        v
Monitoring: Prometheus / Grafana
```

Warstwa użytkownika pozostaje możliwie prosta. Użytkownik korzysta z Open WebUI, Claude Code CLI albo wtyczki IDE. Zmiana dotyczy głównie backendu: zamiast kierować zapytania do Ollamy na stacji 2xA6000, ruch będzie kierowany do vLLM działającego na serwerze 8xH200.

## 5. Zakres projektu

### 5.1 vLLM jako backend modeli

vLLM będzie głównym backendem inference. Jego zadaniem będzie:

- uruchamianie lokalnych modeli open-source,
- obsługa wielu równoległych zapytań,
- streaming odpowiedzi,
- lepsze zarządzanie pamięcią i KV cache,
- wystawienie endpointu możliwego do użycia przez Open WebUI, Claude Code CLI i IDE,
- dostarczenie metryk potrzebnych do benchmarków i monitoringu.

### 5.2 Open WebUI jako chat dla zespołu

Open WebUI pozostaje głównym interfejsem chatowym dla użytkowników zespołu.

W ramach projektu zostanie wykonane przepięcie backendu z Ollamy na vLLM lub warstwę proxy kierującą ruch do vLLM. Celem jest zachowanie znanego interfejsu użytkownika przy jednoczesnym zwiększeniu wydajności i możliwości uruchamiania większych modeli.

### 5.3 Claude Code CLI jako narzędzie programistyczne

Claude Code CLI będzie wykorzystywane jako wsparcie codziennej pracy programistycznej.

Obecnie istnieje już aplikacja Python, która uruchamia Claude Code z lokalnymi modelami. W ramach projektu zostanie dostosowana do nowego backendu vLLM/H200.

Zakładane zastosowania:

- analiza kodu,
- generowanie testów,
- refaktoryzacja,
- analiza błędów,
- pomoc przy debugowaniu,
- praca z dokumentacją techniczną,
- wsparcie przy review kodu.

Zakres projektu w przypadku Claude Code CLI nie obejmuje modyfikowania wewnętrznej logiki promptów tego narzędzia. Celem jest integracja z lokalnym backendem modeli, wybór modelu, sprawdzenie wydajności i przygotowanie wygodnego sposobu użycia przez programistów.

### 5.4 Integracja z IDE / VS Code

W ramach projektu zostanie sprawdzona integracja z IDE, przede wszystkim VS Code.

Zakładany wariant techniczny to konfiguracja wtyczki tak, aby korzystała z lokalnego endpointu modelu. Celem jest zapewnienie programistom AI supportu bez opuszczania środowiska pracy.

### 5.5 Benchmarki modeli oraz prompt evaluation dla workloadu radiogramów KF

Istotną częścią projektu będzie przygotowanie benchmarków wydajnościowych oraz metodyki oceny modeli na workloadzie radiogramów KF.

W przypadku narzędzi programistycznych, takich jak Claude Code CLI, projekt koncentruje się głównie na integracji z lokalnym backendem vLLM oraz sprawdzeniu wydajności i stabilności działania. Prompty i wewnętrzna logika Claude Code CLI są w dużej mierze zaszyte w narzędziu, dlatego nie zakładamy tam własnego prompt engineeringu jako głównego zakresu prac.

Prompt evaluation będzie realizowane przede wszystkim dla radiogramów KF, ponieważ jest to własny, kontrolowany workload domenowy. Pozwala on sprawdzić, jak różne modele i warianty promptów radzą sobie z nietypowym szykiem zdania, relacją nadawca-odbiorca oraz skrótową strukturą komunikatów radiowych.

Mierzone będą m.in.:

- TTFT, czyli czas do pierwszego tokenu,
- TPOT, czyli czas generowania kolejnych tokenów,
- end-to-end latency,
- throughput,
- liczba tokenów wejściowych i wyjściowych,
- concurrency,
- zużycie pamięci GPU,
- wpływ długości promptu na opóźnienia,
- wpływ promptów reasoningowych na jakość odpowiedzi,
- poprawność rozpoznania nadawcy i odbiorcy,
- poprawność interpretacji przestawnego szyku,
- poprawność klasyfikacji typu radiogramu,
- liczba przypadków obsługiwanych szybką ścieżką,
- liczba przypadków wymagających wolnej ścieżki LLM.

### 5.6 Grafana / monitoring

Projekt zakłada przygotowanie podstawowego monitoringu w Grafanie.

Monitoring będzie służył do obserwacji:

- liczby zapytań,
- latency,
- throughput,
- obciążenia GPU,
- użycia pamięci,
- zachowania systemu przy wielu użytkownikach,
- różnic między modelami i konfiguracjami.

Celem jest możliwość świadomego podejmowania decyzji technicznych na podstawie danych, a nie tylko subiektywnej oceny jakości odpowiedzi.

## 6. Workload testowy: radiogramy KF

Jako jeden z praktycznych workloadów testowych zostaną wykorzystane radiogramy KF.

Ten typ danych jest wartościowym przypadkiem testowym, ponieważ różni się od typowych zadań językowych:

- ma niestandardowy i często przestawny szyk zdania,
- relacja nadawca-odbiorca może być odwrotna względem intuicyjnych zadań językowych,
- komunikaty są skrótowe i kontekstowe,
- poprawna analiza wymaga rozpoznania struktury komunikatu, a nie tylko streszczenia tekstu,
- modele LLM mogą popełniać błędy przez założenia wyniesione z typowych danych językowych.

Radiogramy KF będą używane jako kontekst do porównania modeli, promptów i strategii analizy. Nie jest to osobny projekt produkcyjny w pierwszym etapie, ale praktyczny workload sprawdzający, jak modele radzą sobie z nietypową strukturą językową.

W ramach tego workloadu zostanie sprawdzona koncepcja szybkiej i wolnej ścieżki.

### 6.1 Szybka ścieżka

Szybka ścieżka obsługuje znane i powtarzalne struktury radiogramów.

Aplikacja próbuje dopasować radiogram do znanych reguł, parserów lub warunków. Jeżeli dopasowanie jest pewne, wynik powstaje bez użycia dużego modelu LLM.

Zalety:

- niskie opóźnienie,
- niski koszt obliczeniowy,
- powtarzalność,
- łatwość testowania,
- brak konieczności uruchamiania dużego modelu dla znanych przypadków.

### 6.2 Wolna ścieżka

Wolna ścieżka obsługuje przypadki nowe, niejednoznaczne lub nieobsłużone przez istniejące reguły.

W takim przypadku radiogram trafia do modelu LLM, który może:

- przeanalizować strukturę komunikatu,
- wskazać nadawcę i odbiorcę,
- wyjaśnić nietypowy szyk,
- zaproponować sposób interpretacji,
- wygenerować kandydat reguły,
- przygotować propozycję testu regresyjnego.

Po weryfikacji przez człowieka i przejściu testów taka reguła może zostać dodana do szybkiej ścieżki.

W ten sposób LLM nie musi analizować od zera każdego podobnego radiogramu. Model jest używany głównie do nowych lub trudnych przypadków, a powtarzalne przypadki są stopniowo przenoszone do tańszej, deterministycznej ścieżki.

Jest to istotna optymalizacja obliczeniowa: koszt wolnej ścieżki jest ponoszony tylko wtedy, gdy pojawia się nowy lub nieobsłużony typ komunikatu.

## 7. Roadmapa firmowa - 12 tygodni

### Faza 1: uruchomienie vLLM i pierwszy baseline

**Tygodnie 1-3**

Cele:

- uruchomić vLLM na serwerze 8xH200,
- uruchomić pierwszy lokalny model open-source,
- wystawić lokalny endpoint inference,
- wykonać pierwsze testy request/response,
- zmierzyć pierwsze TTFT, TPOT, latency i throughput,
- przygotować zapis konfiguracji środowiska,
- uruchomić minimalną integrację z Open WebUI,
- uruchomić minimalny test Claude Code CLI przez nowy endpoint,
- rozpocząć przygotowanie monitoringu.

Efekt po fazie:

- działający techniczny baseline,
- potwierdzenie, że vLLM na H200 może zastąpić obecny backend oparty o Ollamę,
- pierwsze wyniki benchmarków,
- pierwszy działający przepływ użytkownik -> Open WebUI/Claude Code -> vLLM -> H200.

### Faza 2: integracje użytkowe, benchmarki i prompt evaluation dla radiogramów KF

**Tygodnie 4-7**

Cele:

- dopracować Open WebUI jako chat zespołowy z backendem vLLM,
- dopracować aplikację uruchamiającą Claude Code CLI z wyborem modelu,
- sprawdzić integrację z IDE / VS Code,
- przygotować benchmarki wydajnościowe dla lokalnych modeli,
- przygotować zestaw testowych radiogramów KF,
- przygotować wersjonowane prompty dla analizy radiogramów KF,
- porównać wybrane modele na workloadzie radiogramów,
- zmierzyć wpływ długości promptu i odpowiedzi na TTFT/TPOT,
- sprawdzić zachowanie systemu przy concurrency,
- zdefiniować pierwszą wersję szybkiej i wolnej ścieżki dla radiogramów.

Efekt po fazie:

- pierwsza używalna wersja AI supportu dla zespołu,
- Open WebUI działające na nowym backendzie,
- Claude Code CLI działające z lokalnym endpointem vLLM,
- przetestowana integracja IDE,
- benchmark harness dla modeli,
- zestaw testowych radiogramów KF,
- wersjonowane prompty dla radiogramów,
- pierwsze porównanie modeli na workloadzie radiogramów KF.

### Faza 3: profilowanie, analiza wydajności i testy trudnych workloadów

**Tygodnie 8-10**

Cele:

- pogłębić analizę wydajności inference,
- sprawdzić zachowanie systemu przy bardziej wymagających workloadach,
- użyć radiogramów KF jako trudnego przypadku testowego,
- porównać koszty szybkiej i wolnej ścieżki,
- sprawdzić wpływ promptów reasoningowych na latency i liczbę tokenów,
- przeanalizować użycie pamięci GPU i KV cache,
- przygotować podstawowy dashboard Grafana,
- wykonać kontrolowany eksperyment techniczny związany z wydajnością GPU, jeżeli będzie to zasadne w kontekście pomiarów.

Efekt po fazie:

- lepsze zrozumienie kosztu inferencji dla realnych zadań,
- dane porównujące różne modele i typy promptów,
- pierwsza ocena, kiedy użycie dużego modelu ma sens, a kiedy lepsza jest ścieżka regułowa,
- podstawowy dashboard do obserwacji działania systemu,
- wstępny opis kosztu szybkiej i wolnej ścieżki dla radiogramów KF.

### Faza 4: stabilizacja, wdrożenie pilotażowe i raport końcowy

**Tygodnie 11-12**

Cele:

- uporządkować konfigurację vLLM,
- ustabilizować integracje z Open WebUI, Claude Code CLI i IDE,
- przygotować instrukcję korzystania z AI supportu,
- przygotować podsumowanie benchmarków,
- przygotować końcowy dashboard Grafana,
- uporządkować prompty i workloady testowe,
- opisać wnioski z testów radiogramów KF,
- przygotować rekomendację dalszego rozwoju.

Efekt końcowy po 12 tygodniach:

- działający lokalny AI support dla zespołu,
- Open WebUI korzystające z backendu vLLM/H200,
- Claude Code CLI korzystające z lokalnych modeli,
- przetestowana integracja IDE / VS Code,
- zestaw benchmarków modeli i promptów,
- dashboard Grafana,
- workload testowy radiogramów KF,
- opis szybkiej i wolnej ścieżki,
- raport techniczny z rekomendacją dalszych prac.

## 8. Kryteria sukcesu

Projekt uznajemy za zakończony sukcesem, jeżeli po 12 tygodniach:

1. vLLM działa na serwerze 8xH200.
2. Open WebUI korzysta z nowego backendu.
3. Claude Code CLI może korzystać z lokalnego endpointu modeli.
4. Istnieje przetestowana integracja z IDE / VS Code.
5. Zespół może korzystać z lokalnego AI supportu przez Open WebUI, Claude Code CLI i IDE.
6. Istnieje benchmark harness dla modeli oraz workloadu radiogramów KF.
7. Mierzone są TTFT, TPOT, latency, throughput i concurrency.
8. Istnieje podstawowy monitoring w Grafanie.
9. Istnieje zestaw wersjonowanych promptów dla analizy radiogramów KF.
10. Istnieje workload testowy radiogramów KF.
11. Została sprawdzona koncepcja szybkiej i wolnej ścieżki.
12. Powstał raport końcowy z rekomendacją dalszego rozwoju.

## 9. Zakładany nakład pracy

Zakładany czas pracy to 2 dni tygodniowo przez 12 tygodni.

Czas ten będzie przeznaczony na:

- konfigurację vLLM i serwera,
- integrację z istniejącymi narzędziami,
- przygotowanie benchmarków,
- testowanie modeli,
- analizę wyników,
- przygotowanie dashboardów,
- przygotowanie dokumentacji,
- raport końcowy.

## 10. Wartość dla zespołu

Projekt dostarcza bezpośrednią wartość dla zespołu programistycznego:

- przejście na mocniejszy i bardziej skalowalny backend LLM,
- możliwość korzystania z lokalnych modeli open-source,
- brak konieczności opierania podstawowego AI supportu o zewnętrzne API,
- lepsza wydajność niż obecne środowisko 2xA6000,
- integracja AI supportu z narzędziami używanymi przez programistów,
- metodyka porównywania modeli i promptów na własnym workloadzie,
- monitoring działania modeli,
- dane potrzebne do dalszych decyzji infrastrukturalnych,
- praktyczny workload testowy na radiogramach KF,
- podstawa pod dalsze zastosowania lokalnych modeli w zespole.

## 11. Podsumowanie

Projekt ma na celu przejście z obecnego proof-of-concept lokalnego AI supportu do stabilniejszego, mierzalnego i wydajniejszego środowiska opartego o vLLM oraz serwer 8xH200.

Po 12 tygodniach zespół powinien mieć działające środowisko lokalnej inferencji LLM dostępne przez Open WebUI, Claude Code CLI i IDE, a także zestaw benchmarków, dashboard Grafana oraz pierwsze wyniki oceny modeli i promptów na workloadzie radiogramów KF.

Radiogramy KF zostaną wykorzystane jako trudny workload testowy, pozwalający sprawdzić jakość modeli przy nietypowym szyku zdania i ocenić koncepcję szybkiej oraz wolnej ścieżki analizy. Efektem projektu będzie nie tylko mocniejszy backend dla lokalnych modeli, ale również praktyczna metodyka oceny, kiedy i w jaki sposób wykorzystywać modele LLM w pracy zespołu.
