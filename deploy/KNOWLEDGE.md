# PI-LAB — Baza wiedzy / Knowledge Studio MVP

## Zakres

- Dodawanie źródeł **przez wklejenie treści** (tytuł + tekst) oraz **wgrywanie plików** TXT, MD, CSV, JSON, DOCX i PDF z warstwą tekstową.
- Maksymalny rozmiar pliku: 5 MiB; maksymalna treść po ekstrakcji: 250 000 znaków; maksymalnie 100 stron PDF; limit wypakowanej struktury DOCX: 20 MiB.
- Tekst dzielony na fragmenty z nakładką około 250 znaków, indeksowany lokalnie w SQLite FTS5.
- Stan `pending` po imporcie; wymagane ręczne zatwierdzenie źródła (`approved`). Możliwe wycofanie zatwierdzenia i trwałe usunięcie tekstu z indeksem.
- Podgląd wyekstrahowanej treści, lista źródeł projektu oraz lokalne wyszukiwanie fragmentów.
- **Do modelu trafiają wyłącznie fragmenty zatwierdzonych źródeł**, jeśli aktywny jest projekt i zaznaczono kontekst. Mechanizm wykorzystuje leksykalne wyszukiwanie, nie embeddings/semantic RAG.

## Użytkowanie

1. Połącz się z Gateway, wybierz lub utwórz projekt i przejdź do **Baza wiedzy**.
2. Wklej tytuł i treść lub wybierz plik (obsługiwane rozszerzenia powyżej).
3. Po imporcie wybierz **Podgląd**, zweryfikuj tekst i wybierz **Zatwierdź**.
4. Wyszukuj fragmenty w **Wyszukiwanie i kontrola retrievalu**.
5. W oknie rozmowy wybierz ten sam projekt i pozostaw **Kontekst projektu** włączony. W podglądzie pamięci możesz zobaczyć wybrane fragmenty, zanim wyślesz pytanie do modelu.

## Dane i bezpieczeństwo

- Wszystkie treści oraz FTS są w bazie `DATABASE_PATH`, domyślnie `/var/lib/ai-gateway/gateway.db` na natywnym LXC. **Nie zapisujemy oryginalnego pliku** — jedynie tekst.
- Import nie wykonuje makr, JavaScript, zewnętrznych URL, OCR ani wywołań LLM. Obrazy i skanowane PDF wymagają odrębnego OCR.
- Tekst pochodzi z niezaufanego źródła. Import nie nadaje instrukcjom w dokumentach uprawnień do sterowania Gateway, ale prompt injection w modelach pozostaje ryzykiem.
- Ręczna aprobata dotyczy **całego źródła**, nie każdego fragmentu osobno.
- Profile w tej wersji nie stanowią odrębnych kont z kontrolą dostępu. Projekty i dokumenty są współdzielone przez osoby znające hasło Gateway.
- Przy wybraniu OpenAI/Gemini/Groq zatwierdzone, dopasowane fragmenty dokumentów **są przesyłane do zewnętrznego dostawcy** razem z pytaniem. Opcja „Tylko lokalnie” lub serwerowe `FORCE_LOCAL_ONLY=true` blokują chmurę.
- Nie importuj tajnych kluczy, danych klientów ani danych wrażliwych, jeśli nie akceptujesz ryzyka przechowywania i ewentualnego przesłania do chmury.

## API (wymaga X-Gateway-Password)

- `GET /api/knowledge?project_id=...` — lista źródeł.
- `POST /api/knowledge/paste` — JSON `{"project_id":"...","title":"...","content":"..."}`.
- `POST /api/knowledge/upload` — multipart `project_id` i `file`.
- `GET /api/knowledge/{source_id}?project_id=...` — podgląd treści.
- `PATCH /api/knowledge/{source_id}?project_id=...` — `{"status":"approved"}` lub `{"status":"pending"}`.
- `DELETE /api/knowledge/{source_id}?project_id=...` — usunięcie.
- `POST /api/knowledge/search` — `{"project_id":"...","question":"..."}`; w trybie inspekcji pokazuje także oczekujące źródła.
- `POST /api/context/preview` — teraz zwraca `facts`, `sources` i scalony `system_message`.

## Migracja LXC

Przed aktualizacją zatrzymaj usługę i wykonaj kopię SQLite. Następnie pobierz `main`, uruchom `bash scripts/install-lxc.sh`, uruchom usługę i wykonaj `Ctrl+F5` w przeglądarce. Tabele wiedzy są tworzone addytywnie na starcie, bez usuwania rozmów i dotychczasowych faktów.

## Co dalej?

OCR skanów, obsługa większych plików/załączników, embeddingi i retrieval hybrydowy, podział na strony/sekcje w metadanych, szczegółowe cytowania, pliki źródłowe do pobrania, wersjonowanie oraz per-user autoryzacja.
