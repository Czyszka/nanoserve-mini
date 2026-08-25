# Claude Code na klientach — uruchomienie z kitu i podstawy użycia

Kit: `benchmarks/claude_code_kit/` → `dist/claude_code_kit.zip` (budowany
`build_kit.py`, szczegóły w tamtejszym README). Klient działa **offline** —
Claude Code łączy się z Ollamą w LAN (natywne Anthropic Messages API), bez
konta Anthropic i bez internetu.

## 1. Uruchomienie na komputerze klienckim

### Wymagania wstępne

- Windows 10/11; brak instalacji — wszystko (Node, Claude Code, Python) jest w zipie.
- Dostęp LAN do serwera Ollamy **v0.14.0+** (adres wpisany w kit przy budowie).
- Po stronie serwera (jednorazowo, nie na kliencie): `OLLAMA_HOST=0.0.0.0`
  i kontekst ≥ 32k (`OLLAMA_CONTEXT_LENGTH`) — mniejszy utnie system prompt
  Claude Code i wyniki będą bezużyteczne.

### Kroki

1. Rozpakuj `claude_code_kit.zip` w dowolne miejsce, np. `C:\claude_kit`.
2. Uruchom `setup.bat --persist` — kopiuje konfigurację `.claude` do profilu
   użytkownika (istniejąca dostaje backup), zapisuje zmienne środowiskowe na
   stałe (`setx`) i odpala smoke test połączenia z Ollamą. Inne opcje:
   `--skip-smoke`, `--skip-userdir`.
3. Dodaj katalog kitu do PATH użytkownika (PowerShell):

   ```powershell
   [Environment]::SetEnvironmentVariable("Path",
     [Environment]::GetEnvironmentVariable("Path","User") + ";C:\claude_kit", "User")
   ```

   Uwaga: nie używaj `setx PATH "%PATH%;..."` — skleja PATH systemowy
   z użytkownika i tnie do 1024 znaków.
4. **Otwórz nowe okno** cmd/terminala. Od teraz w dowolnym katalogu projektu
   działa po prostu `claude` (rozwiązuje się do `claude.bat` z kitu, który
   sam ustawia adres serwera/model/token na czas sesji).

Smoke test przeszedł = łączność i generacja działają. Nie testuje pełnej pętli
narzędziowej — ta zależy od jakości tool-callingu modelu na Ollamie.

### Typowe problemy

| Objaw | Przyczyna |
|---|---|
| smoke timeout | serwer Ollamy nie nasłuchuje na LAN albo zły adres w kicie |
| odpowiedzi od rzeczy / obcięte | za małe okno kontekstu na serwerze (<32k) |
| `claude` nierozpoznane w cmd | katalog kitu nie jest w PATH albo stare okno terminala (otwórz nowe) |
| klient prosi o logowanie | w PATH jest inna, globalna instalacja Claude Code przed kitem (`where claude` pokaże kolejność) |

## 2. Podstawy pracy

### Zasady ogólne

- Uruchamiaj `claude` **w katalogu głównym projektu** — klient widzi wtedy
  strukturę repo i plik `CLAUDE.md`.
- Jedno zadanie = jedno polecenie. Zamiast „popraw projekt": „napraw test
  `test_parser` w `tests/`".
- Czytaj diffy przed zatwierdzeniem — klient pyta o zgodę przed zapisem plików
  i uruchamianiem komend.
- `CLAUDE.md` w repo = stałe instrukcje projektu (konwencje, komendy
  walidacji); czytany na starcie każdej sesji. Nowy projekt: `/init` generuje
  szkielet.

### Typowe zadania

| Zadanie | Jak |
|---|---|
| Analiza projektu | „opisz architekturę tego repo", „gdzie jest obsługa X?" |
| Bugfix | wklej błąd/traceback + „napraw"; klient sam znajdzie pliki |
| Nowa funkcja | najpierw tryb planu (`Shift+Tab`): akceptujesz plan, potem wykonuje |
| Refaktor | wskaż plik/funkcję i cel; po zmianie poproś o uruchomienie testów |
| Testy | „uruchom testy i napraw czerwone" |
| Git | „zrób commit" — opis wygeneruje z diffa |

### Komendy w sesji

| Komenda | Działanie |
|---|---|
| `/help` | lista komend |
| `/init` | generuje `CLAUDE.md` dla projektu |
| `/clear` | nowa rozmowa (czysty kontekst) |
| `/compact` | kompresja długiej rozmowy |
| `Shift+Tab` | tryb planu / auto-akceptacja edycji |
| `Esc` | przerwanie bieżącej odpowiedzi |

### Higiena sesji

- Po zamkniętym temacie `/clear` — długi kontekst degraduje jakość, a na
  modelu z Ollamy szczególnie (okno 32k wyczerpuje się szybko).
- Rzeczy do zapamiętania na stałe dopisuj do `CLAUDE.md`, nie powtarzaj
  w każdej sesji.
- Nie wklejaj sekretów do rozmowy; klient nie potrzebuje `.env`.
