# Claude Code — instalacja z paczki i podstawy użycia

## 1. Instalacja na stanowisku

### Wymagania wstępne

- Node.js ≥ 18 (`node --version`) — tylko dla instalacji z paczki npm.
- Git na `PATH`.
- Konto claude.ai (Pro/Max) **albo** klucz API Anthropic.
- Dostęp sieciowy do `api.anthropic.com` (sam klient po instalacji nie potrzebuje npm).

### Instalacja z przygotowanej paczki

Paczka: `claude-code-<wersja>.tgz` (tarball npm).

1. Skopiuj paczkę na dysk, np. `C:\narzedzia\` (Windows) lub `~/narzedzia/` (Linux).
2. Zainstaluj globalnie:

   ```bash
   npm install -g C:\narzedzia\claude-code-<wersja>.tgz     # Windows
   npm install -g ~/narzedzia/claude-code-<wersja>.tgz      # Linux
   ```

3. Weryfikacja: `claude --version`.

Alternatywa online (gdy maszyna ma dostęp do internetu):

```powershell
irm https://claude.ai/install.ps1 | iex        # Windows PowerShell
```

```bash
curl -fsSL https://claude.ai/install.sh | bash  # Linux/macOS
```

### Pierwsze uruchomienie i logowanie

1. Wejdź do katalogu projektu i uruchom `claude`.
2. Przy pierwszym starcie wybierz logowanie: konto claude.ai (przeglądarka)
   lub klucz API (`ANTHROPIC_API_KEY` w zmiennych środowiska).
3. Zatwierdź zaufanie do katalogu projektu, gdy klient zapyta.

Konfiguracja trzymana jest w `~/.claude/` (globalna) i `.claude/` w repo
(projektowa — commitowana, wspólna dla zespołu).

## 2. Podstawy pracy

### Zasady ogólne

- Uruchamiaj `claude` **w katalogu głównym repo** — klient widzi wtedy strukturę
  projektu, `CLAUDE.md` i ustawienia zespołowe.
- Jedno zadanie = jedno polecenie. Zamiast „popraw projekt": „napraw test
  `test_parser_ttft` w `benchmarks/scripts_tests/`".
- Czytaj diffy przed zatwierdzeniem edycji; klient pyta o zgodę przed zapisem
  plików i komendami.
- `CLAUDE.md` w repo to stałe instrukcje projektu (konwencje, komendy
  walidacji) — klient czyta go na starcie każdej sesji. Nowy projekt: `/init`
  wygeneruje szkielet.

### Typowe zadania

| Zadanie | Jak |
|---|---|
| Analiza projektu | „opisz architekturę tego repo", „gdzie jest obsługa X?" |
| Bugfix | wklej błąd/traceback + „napraw"; klient sam znajdzie pliki |
| Nowa funkcja | najpierw tryb planu (`Shift+Tab`): klient proponuje plan, akceptujesz, potem wykonuje |
| Refaktor | wskaż plik/funkcję i cel; poproś o uruchomienie testów po zmianie |
| Testy | „uruchom testy i napraw czerwone" |
| Git | „zrób commit", „przygotuj PR" — opisy generuje z diffa |
| Review | „zrób code review zmian na tym branchu" |

### Przydatne komendy w sesji

| Komenda | Działanie |
|---|---|
| `/help` | lista komend |
| `/init` | generuje `CLAUDE.md` dla projektu |
| `/model` | zmiana modelu |
| `/clear` | nowa rozmowa (czysty kontekst) |
| `/compact` | kompresja długiej rozmowy (gdy sesja spuchła) |
| `Shift+Tab` | przełączanie trybu planu / auto-akceptacji edycji |
| `Esc` | przerwanie bieżącej odpowiedzi |

### Higiena sesji

- Długa rozmowa degraduje jakość — po zamkniętym temacie `/clear`.
- Rzeczy, które klient ma pamiętać na stałe (konwencje, pułapki), dopisuj do
  `CLAUDE.md`, nie powtarzaj w każdej sesji.
- Sekrety: klient nie potrzebuje `.env` — nie wklejaj tokenów do rozmowy.
