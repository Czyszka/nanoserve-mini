# Uzasadnienie LiteLLM Proxy jako warstwy multi-model dla T4

## Givens i zakres badania

Przyjmuję jako dane wejściowe z briefu, a nie przedmiot badania, że projekt to portfolio LLM inference lab, faza pierwsza to baseline serving + multi-model proxy na 8×H200, decyzja o użyciu LiteLLM Proxy jest już zamrożona, a write-up ma ją uzasadnić, nie otwierać wyboru od nowa. Ten research dotyczy więc wyłącznie tego, gdzie wiedza zewnętrzna realnie wzmacnia uzasadnienie: wymagań DB dla per-user virtual keys, realnych opcji logowania ponad stdout, jakości alternatyw dla pojedynczego endpointu OpenAI-compatible przed wieloma backendami oraz tego, co da się uczciwie powiedzieć o narzucie dodatkowego hopu proxy. 

## Decyzja

LiteLLM Proxy jest sensowną decyzją dla T4 jako cienka, self-hostowana warstwa „jeden endpoint OpenAI-compatible przed wieloma backendami”, ponieważ dokładnie do takiego zastosowania jest projektowany: jako centralny gateway z jedną powierzchnią API zgodną z OpenAI, obsługą wielu providerów/backendów, wspólną autoryzacją i routingiem po modelu, a także mechanizmami, które pomagają przeżyć różnice między backendami, jak `drop_params`. To dobrze pasuje do fazy „serving baseline + multi-model proxy”, gdzie najważniejsze jest uproszczenie interfejsu klienta i odseparowanie aplikacji od wiedzy o portach/backendach. Jednocześnie, w Waszej aktualnej postaci wdrożenia — jeden `master_key`, brak DB-backed key management i logowanie sprowadzone do stdout kontenera — LiteLLM realizuje dziś tylko część DoD: „jeden endpoint” i „routing po model”, ale nie „API keys per user” ani „logi” w sensie trwałych, per-request danych operacyjnych. citeturn8search9turn27search2turn28search0turn28search3turn38search2

## Uzasadnienie

### Per-user virtual keys rzeczywiście wymagają bazy

W dokumentacji LiteLLM obsługa virtual keys nie jest przedstawiona jako opcjonalny dodatek bez stanu, tylko jako funkcja wymagająca Postgresa: strona o virtual keys wprost podaje `Need a postgres database`, `DATABASE_URL` i `master key`, a następnie prowadzi przez `/key/generate`. Osobna dokumentacja DB mówi równie jasno, że PostgreSQL służy do przechowywania virtual keys, organizacji, zespołów, użytkowników, budżetów i per-request usage tracking. Innymi słowy: jeśli celem DoD jest „API keys per user”, to w LiteLLM nie dochodzi się do tego przez sam `master_key`, tylko przez włączenie warstwy key-management backed by DB. citeturn15view2turn15view3turn10view0turn10view1turn35search8turn35search17

To, co odblokowuje DB, jest ważniejsze niż samo „generowanie kluczy”. Z dokumentacji wynika, że z DB przychodzą przynajmniej: per-key spend, per-user spend, per-team spend, budżety osobiste, budżety teamowe, budżety członków zespołów oraz rate-limity i model access dla userów/teamów. W praktyce oznacza to, że Postgres nie jest wyłącznie magazynem sekretów, ale stanem kontroli dostępu i rozliczalności. To właśnie jest brakujący element między Waszym obecnym „single master key” a DoD z per-user API keys. citeturn10view1turn10view2turn10view3turn10view4turn35search9turn35search11

Redis nie zastępuje tej bazy. Dokumentacja LiteLLM opisuje Redis jako cache autoryzacji virtual keys, który redukuje liczbę odczytów z DB i współdzieli cache między workerami/podami, szczególnie po deployach i cold startach. To ważne z perspektywy skali i T8, ale nie zmienia bazowej architektury: DB pozostaje systemem rekordowym dla kluczy, userów, teamów, budżetów i usage. citeturn15view0turn15view1turn37search1turn39search2turn39search5

### Logowanie „ponad stdout” jest w LiteLLM realne, ale trzeba je włączyć

LiteLLM ma znacznie więcej opcji logowania niż goły stdout kontenera. Oficjalna dokumentacja logowania wymienia m.in. Langfuse, OpenTelemetry, bucket storage, AWS SQS, DynamoDB, DataDog, MLflow, niestandardowe callbacki i webhooki. Dokumentacja callbacków rozróżnia `input_callback`, `success_callback` i `failure_callback`, a callback custom loggera pozwala wejść w hooki pre-call, post-call, success i failure. To oznacza, że LiteLLM ma realny mechanizm per-request observability, ale nie dzieje się to „samo” z samego uruchomienia proxy. citeturn9view2turn12view0turn12view1turn14view6turn36search6

Jeżeli celem jest request-level logging, są co najmniej trzy sensowne ścieżki. Pierwsza to DB/UI logs: dokumentacja UI logs mówi, że success logs i error logs są śledzone domyślnie, ale request/response content nie jest zapisywany domyślnie i wymaga `store_prompts_in_spend_logs: true`. Druga to zewnętrzny sink typu Langfuse, gdzie wystarczy skonfigurować `success_callback: ["langfuse"]` oraz klucze środowiskowe. Trzecia to OpenTelemetry, gdzie trzeba dodać `callbacks: ["otel"]` oraz odpowiednie zmienne dla eksportera OTLP; dodatkowo można świadomie wyłączyć content capture przez `callback_settings.otel.message_logging: false`. citeturn14view0turn11view5turn13view1turn13view0turn13view2turn13view3

Ważne jest też to, że LiteLLM daje dostęp do bogatego payloadu logowania. Standard logging payload zawiera identyfikator, trace id, status i koszt odpowiedzi, a custom callback może dostać zarówno `response_cost`, jak i `metadata`; dodatkowo proxy-only logging może odczytać `proxy_server_request`, czyli URL, nagłówki i request body przychodzące do proxy. To znaczy, że z perspektywy DoD „logi” nie muszą oznaczać jedynie printów z kontenera — LiteLLM może stać się źródłem ustrukturyzowanych, per-request zdarzeń do Langfuse, OTel albo własnego API/webhooka. citeturn36search0turn10view6turn12view1turn37search6turn39search7

### Wersja ma znaczenie, a Wasza jest stara na tyle, by traktować DB enablement ostrożnie

To nie jest bezpieczny obszar na „czytałem kiedyś, chyba działa”. Na exact-version frontcie dokumentacja release notes dla `main-v1.66.0-stable` potwierdza, że ta wersja miała już logging/cost tracking dla realtime i działające budżety key/user/team dla realtime, więc nie mówimy o prehistorycznym wydaniu bez danych operacyjnych. Jednocześnie istnieje publiczny issue od użytkownika zgłaszający na `v1.66.0-stable`/`v1.66.1` problem z migracjami Prisma i brakującą kolumną `team_member_permissions`; późniejsze docs LiteLLM mają już osobny troubleshooting dla Prisma migrations. To nie dowodzi, że Wasze wdrożenie na pewno się wyłoży, ale uczciwie pokazuje, że włączenie DB-backed key management na dokładnie tym tagu trzeba traktować jako zmianę wymagającą smoke testów migracji, a nie tylko dopisania `DATABASE_URL`. citeturn26view0turn25search0turn25search2

## Uczciwy zakres

LiteLLM uzasadnia decyzję o warstwie multi-model, ale nie rozwiązuje wszystkiego naraz. Po pierwsze, „request logs” i „audit logs” to nie jest to samo. Request/spend/error logs są częścią normalnych mechanizmów proxy i DB/integrations, natomiast audit logs zmian administracyjnych w dokumentacji są opisane oddzielnie i są wiązane z ofertą enterprise. Gdy więc w write-upie pojawia się słowo „logi”, trzeba precyzyjnie odróżnić logi operacyjne per request od audit trail dla zmian admin/key/team. citeturn14view0turn14view2turn39search1turn39search4

Po drugie, LiteLLM w tym uzasadnieniu powinien być pokazany jako cienki gateway model-aware oparty o jawne nazwy modeli, nie jako pełny system inteligentnego routingu treści zapytania. Owszem, obecne docs i nowsze release notes pokazują rozwój w stronę tag-based policies, model discovery i coraz bogatszych funkcji platformowych, ale to nie jest potrzebne, żeby uzasadnić T4. W T4 wystarczy teza: jedna powierzchnia OpenAI-compatible, stała semantyka klienta, routing po `model`, możliwość dojścia do per-user keys i per-request logging po dołożeniu brakującej infrastruktury stanu. citeturn26view1turn33search1turn33search16turn27search2

## Trade-off wobec kolejnego etapu

Najuczciwszy wniosek o narzucie LiteLLM jako dodatkowego hopu jest taki: overhead istnieje, LiteLLM sam daje narzędzie do jego pomiaru, ale dostępne publiczne liczby są zbyt syntetyczne, żeby bezpośrednio przepisać je na Wasz układ z 8×H200 i konkretnymi backendami. Oficjalny benchmark LiteLLM podaje `8ms P95 latency at 1k RPS`, ale wprost zaznacza, że chodzi o testy przeciwko fake OpenAI endpoint na maszynach 4 CPU / 8 GB RAM. Dokumentacja dodaje też, że każda odpowiedź zawiera nagłówek `x-litellm-overhead-duration-ms`, czyli sam produkt sugeruje mierzyć overhead na własnej ścieżce requestu, a nie ufać jednemu marketingowemu numerowi. citeturn9view5turn37search2turn36search4

To jest ważne także dlatego, że charakterystyka wydajności LiteLLM jest wersjo-zależna. W nowszym `v1.72.0` twórcy przestawili domyślny transport na aiohttp i opisują skok throughputu oraz inne liczby latency, co samo w sobie jest sygnałem, że nie wolno mieszać wyników z różnych wersji w jednym uzasadnieniu. Dla T8 poprawny wniosek brzmi więc nie „proxy overhead jest mały”, tylko „proxy overhead trzeba zmierzyć na pinned `main-v1.66.0-stable`, na Waszych promptach, Waszych długościach generacji i Waszym concurrency”. citeturn38search13turn38search0turn36search1

Literatura wokół semantic routing wzmacnia jeszcze jedną rzecz: większe zyski wydajnościowe zwykle pochodzą nie z samego „czy jest dodatkowy hop”, tylko z jakości polityki routingu. Paper „When to Reason” dla vLLM semantic router pokazuje poprawę accuracy przy jednoczesnym spadku latency o 47,1% i token usage o 48,5% względem podejścia „zawsze reasoning”, ale to jest zysk z inteligentnej selekcji ścieżki modelowej, a nie dowód, że sam gateway hop jest darmowy. Dla T4 to dobry argument, by nie mylić dwóch tematów: LiteLLM uzasadnia cienką warstwę jednolitego wejścia; pytanie o zaawansowany content-aware routing należy do następnego etapu. citeturn23search11

## Odrzucone alternatywy

### Bezpośrednie porty vLLM

vLLM samo w sobie daje OpenAI-compatible server i pozwala aliasować nazwę modelu przez `--served-model-name`, ale nie rozwiązuje problemu „jeden endpoint przed wieloma backendami”. Każda instancja vLLM pozostaje osobnym serwerem, a klient albo musi znać właściwy port/base URL, albo trzeba dobudować coś przed nim. To dlatego bezpośrednie porty są sensownym baseline serving, ale słabym uzasadnieniem dla warstwy multi-model w T4. citeturn19view0turn21view0

### NGINX i podobne reverse proxy bez warstwy AI

NGINX potrafi być AI proxy, ale oficjalny przykład pokazuje, że kiedy chcesz naprawdę wystawić wspólną semantykę OpenAI nad różnymi backendami, wchodzisz w njs, parsowanie body oraz transformację requestów i odpowiedzi. Innymi słowy: zwykły reverse proxy daje HTTP routing, ale model-aware OpenAI semantics trzeba sobie dopisać. To jest dokładnie ten przypadek, którego brief chce uniknąć: dostajesz ogólną infrastrukturę sieciową, a nie gotowe uzasadnienie dla warstwy „model-aware OpenAI gateway”. citeturn29view0turn29view1turn29view2

### Envoy AI Gateway, Kong AI Gateway i Traefik AI Gateway

Te rozwiązania są już prawdziwymi gatewayami AI, a nie wyłącznie proxy HTTP. Envoy AI Gateway definiuje „unified AI API”, potrafi wyciągnąć model z treści requestu przed decyzją routingu i używa do tego własnego filtra/ext-proc oraz CRD. Kong AI Gateway potrafi routować po `model` z request body przez `model_alias`, ale model alias routing wymaga AI Proxy Advanced i minimum Kong Gateway 3.14; plugin AI Proxy Advanced jest dokumentowany jako część oferty enterprise. Traefik AI Gateway z kolei potrafi „promote any route” do OpenAI-compatible Responses API i ma governance dla `model` i parametrów, ale jest wyraźnie osadzony w Traefik Hub/Kubernetes. Wszystkie trzy są więc mocnymi kandydatami na późniejszy, cięższy control plane, ale dla T4 byłyby większą zmianą operacyjną niż potrzeba do etapu baseline. citeturn31view2turn31view1turn31view3turn30search0turn30search2turn34search2turn34search10

### vLLM Semantic Router

vLLM Semantic Router jest bardzo ciekawą alternatywą przyszłościową, bo właśnie tam pojawia się routing semantyczny, polityki koszt/prywatność/latencja i obsługa wielu heterogenicznych backendów w OpenAI API style. Tyle że to już nie jest odpowiedź na pytanie „czy potrzebujemy cienkiej warstwy multi-model przed vLLM w fazie pierwszej”, tylko odpowiedź na pytanie „kiedy chcemy przejść z name-based routing do content-aware decision routing”. Produkcyjny stack semantic routera idzie też przez Envoy/Gateway API, czyli znowu pcha Was w cięższy control plane. citeturn23search3turn23search12turn23search4

### Bramki typu OpenRouter

OpenRouter faktycznie daje pojedynczy endpoint, OpenAI-like normalizację odpowiedzi, provider routing, fallbacki i nawet kontrolę Zero Data Retention. Problem polega na tym, że jest to z definicji zewnętrzna bramka SaaS dla wielu providerów, a nie self-hostowana warstwa przed własnymi backendami vLLM na H200. W briefie T4 uzasadniacie własny inference lab i własne serving endpoints; OpenRouter rozwiązuje inny problem architektoniczny. citeturn32view0turn32view1turn32view2turn32view3

## Powiązanie z dalszym zadaniem

Najmocniejszy „future link” do zadania #39 nie powinien reopenować wyboru LiteLLM, tylko naturalnie domknąć brakujące stopnie dojrzałości. Najpierw trzeba dowieźć to, czego dziś brakuje względem DoD przy zachowaniu zamrożonej decyzji: Postgres-backed key management dla per-user API keys oraz prawdziwe logowanie per request przez DB/UI, Langfuse, OTel albo custom callback sink. Dopiero po tym ma sens pytać, czy kolejny etap wymaga już cięższego control plane, np. richer governance z Envoy/Kong/Traefik albo semantic routing w stylu vLLM SR. Ten porządek jest spójny z tym, jak LiteLLM samo pozycjonuje proxy: najpierw centralny gateway z auth, spend i loggingiem; dopiero potem bardziej zaawansowane polityki i observability. citeturn35search17turn10view0turn14view0turn13view0turn13view1turn31view2turn30search2turn34search2turn23search3

W praktyce oznacza to, że #39 warto opisać jako przejście od „thin model router” do „managed inference control plane”, a nie jako alternatywny wybór dla T4. T4 broni się jako etap redukcji złożoności klienta i ujednolicenia semantyki OpenAI. #39 powinno dopiero pytać, czy macie już empiryczne uzasadnienie dla bardziej zaawansowanego routingu, wyższej klasy governance i bardziej rozbudowanej observability. citeturn27search2turn23search4turn23search11

## Otwarte kwestie

Największa nierozstrzygnięta rzecz to nie funkcjonalność LiteLLM, tylko dokładna cena wydajnościowa na Waszym pinned buildzie i Waszych promptach. Oficjalne liczby LiteLLM są syntetyczne i oparte o fake upstream, a późniejsze release notes pokazują, że charakterystyka wydajności zmieniała się między wersjami. Uczciwe uzasadnienie do T4 powinno więc wprost mówić, że teza „LiteLLM jako cienka warstwa ma akceptowalny narzut” jest hipotezą do potwierdzenia w T8, a nie faktem już zmierzonym na 8×H200. citeturn37search2turn36search4turn38search13

Druga otwarta kwestia jest operacyjna i wersyjna: w publicznych zgłoszeniach istnieje przynajmniej jeden problem migracyjny zahaczający o `v1.66.0-stable`, więc wdrożenie DB-backed virtual keys na dokładnie tej wersji wymaga większej ostrożności niż sugerowałaby wyłącznie lektura docs. To nie unieważnia decyzji o LiteLLM, ale wzmacnia uczciwy trade-off: wybór jest architektonicznie sensowny, natomiast exact-version rollout do pełnego DoD może wymagać większej dyscypliny wdrożeniowej niż w nowszych release’ach. citeturn25search0turn25search2