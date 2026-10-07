# CloudNotes - projekt przewodni

CloudNotes to prosta aplikacja webowa do notatek. Użytkownik dodaje notatkę, opcjonalnie dołącza plik i może zlecić wygenerowanie raportu z notatki.

Repozytorium dla studentów: https://github.com/pwmasta/cloud

```bash
git clone https://github.com/pwmasta/cloud.git ~/cloudnotes
cd ~/cloudnotes/src
```

Wszystkie ścieżki w tym pliku są podane względem katalogu głównego repozytorium.

Kod aplikacji jest tylko narzędziem do nauki chmury. Studenci nie muszą go rozwijać. Podczas laboratoriów zmieniamy przede wszystkim **infrastrukturę i konfigurację**, a nie kod.

## Najważniejsza idea: jeden kod, konfiguracja wybiera usługi

Aplikacja ma jeden kod przez cały semestr. To, z jakich usług korzysta, zależy wyłącznie od zmiennych środowiskowych, czyli od App Settings w App Service albo zmiennych kontenera.

| Funkcja | Bez konfiguracji (tryb lokalny) | Po ustawieniu zmiennej (tryb chmurowy) | Od laboratorium |
| --- | --- | --- | --- |
| notatki | SQLite na dysku instancji | PostgreSQL (`DATABASE_URL`) | L05 |
| załączniki i raporty | pliki na dysku instancji | Blob Storage (`STORAGE_CONNECTION_STRING` albo `STORAGE_ACCOUNT_NAME`) | L04 |
| raporty | generowane synchronicznie w żądaniu HTTP | wiadomość w Storage Queue i przetwarzanie w Azure Function | L10 |
| sekrety | zmienne środowiskowe | Key Vault przez managed identity (`KEY_VAULT_URL`) | L08 |
| telemetria | tylko logi na stdout | Application Insights (`APPLICATIONINSIGHTS_CONNECTION_STRING`) | L09 |

Tryb lokalny zapisuje dane w katalogu tymczasowym instancji. To jest celowe. W App Service ten katalog znika przy restarcie i każda instancja ma własny. Dzięki temu studenci widzą problem stanu lokalnego, zanim zobaczą rozwiązanie.

Stopka każdej strony pokazuje identyfikator instancji, czas jej uruchomienia, liczbę obsłużonych żądań i aktywne backendy. To jest główne narzędzie obserwacji w laboratoriach o skalowaniu i awariach.

## Struktura katalogów

```text
cloudnotes/
  README.md
  src/                    aplikacja webowa CloudNotes (Flask)
    app.py                endpointy HTTP
    config.py             odczyt konfiguracji i sekretów
    notes.py              repozytorium notatek: SQLite albo PostgreSQL
    files.py              pliki: dysk lokalny albo Blob Storage
    reports.py            raporty: synchronicznie albo przez kolejkę
    telemetry.py          logowanie i Application Insights
    templates/            szablony HTML
    requirements.txt
    Dockerfile            obraz kontenera (L11)
  function/               Azure Function przetwarzająca kolejkę (L10)
    function_app.py
    host.json
    requirements.txt
  dev/
    compose.yaml          lokalne PostgreSQL, Azurite i host Functions dla prowadzącego
  checkpoints/            stany projektu po kolejnych laboratoriach
```

## Endpointy

| Metoda i ścieżka | Znaczenie |
| --- | --- |
| `GET /` | lista notatek i formularz |
| `POST /notes` | dodanie notatki z opcjonalnym załącznikiem |
| `POST /notes/<id>/delete` | usunięcie notatki, załącznika i raportu |
| `POST /notes/<id>/report` | zlecenie raportu |
| `GET /notes/<id>/report` | podgląd raportu |
| `GET /files/<nazwa>` | pobranie załącznika przez aplikację |
| `GET /api/notes` | notatki w formacie JSON, wygodne do testów przez `curl` |
| `GET /health` | stan zależności, backendy i informacje o instancji. Zwraca `200` albo `503` |
| `GET /debug/error` | kontrolowany wyjątek i odpowiedź `500` (L09) |
| `GET /debug/slow?seconds=3` | wolna odpowiedź, maksymalnie 30 sekund (L09) |
| `GET /debug/cpu?ms=200` | obciążenie CPU, maksymalnie 5000 ms (L06) |

Endpointy `/debug/*` istnieją wyłącznie do ćwiczeń. W prawdziwej aplikacji nie powinny być publicznie dostępne. Warto o tym powiedzieć studentom przy okazji L08.

## Zmienne środowiskowe

| Zmienna | Znaczenie | Wartość domyślna |
| --- | --- | --- |
| `APP_ENVIRONMENT` | nazwa środowiska widoczna w nagłówku strony | `local` |
| `DATA_DIR` | katalog danych trybu lokalnego | katalog tymczasowy systemu + `cloudnotes` |
| `DATABASE_URL` | sekret: adres PostgreSQL, np. `postgresql://user:haslo@host:5432/cloudnotes?sslmode=require` | brak, czyli SQLite |
| `STORAGE_CONNECTION_STRING` | sekret: connection string Storage Account | brak |
| `STORAGE_ACCOUNT_NAME` | nazwa Storage Account przy dostępie przez managed identity | brak |
| `ATTACHMENTS_CONTAINER` | container na załączniki | `attachments` |
| `REPORTS_CONTAINER` | container na raporty | `reports` |
| `REPORT_QUEUE` | kolejka zleceń raportów | `report-jobs` |
| `REPORT_DELAY_SECONDS` | sztuczny czas generowania raportu | `5` |
| `KEY_VAULT_URL` | adres Key Vault, np. `https://kv-cloudnotes-jkow42.vault.azure.net/` | brak |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | włącza wysyłanie telemetrii | brak |
| `HOST`, `PORT` | adres i port serwera deweloperskiego `python3 app.py` | `127.0.0.1`, `5000` |

Zasady rozstrzygania:

- Jeżeli ustawiono `STORAGE_CONNECTION_STRING`, aplikacja używa klucza konta. W przeciwnym razie, jeśli ustawiono `STORAGE_ACCOUNT_NAME`, używa tożsamości (`DefaultAzureCredential`).
- Wartości `DATABASE_URL` i `STORAGE_CONNECTION_STRING` są sekretami. Aplikacja szuka ich najpierw w zmiennych środowiskowych. Jeżeli ich tam nie ma, a ustawiono `KEY_VAULT_URL`, pobiera z Key Vault sekrety `database-url` i `storage-connection-string`.
- Kolejka jest włączana razem ze Storage Account. Bez skonfigurowanego Storage raporty są generowane synchronicznie.

Kolejność ma znaczenie dydaktyczne. W L04 i L05 sekrety są jeszcze jawnie w App Settings. W L08 studenci przenoszą je do Key Vault i usuwają z App Settings bez zmiany kodu.

## Uruchomienie lokalne

Wymagany jest Python 3.10 lub nowszy.

```bash
cd src
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

Aplikacja działa pod adresem `http://localhost:5000`.

Serwer produkcyjny, tak jak w App Service i w kontenerze:

```bash
.venv/bin/gunicorn --bind 0.0.0.0:8000 app:app
```

## Uruchomienie w App Service

App Service dla Pythona wykrywa plik `app.py` z obiektem `app` i uruchamia Gunicorn:

```text
gunicorn --bind=0.0.0.0 --timeout 600 app:app
```

Nie trzeba ustawiać własnej komendy startowej. Zależności z `requirements.txt` instaluje build Oryx podczas wdrożenia. Po buildzie aplikacja działa z katalogu `/tmp/<uid>`, a nie z `/home/site/wwwroot`.

## Kontener

```bash
cd src
docker build -t cloudnotes:local .
docker run --rm -p 8000:8000 -e APP_ENVIRONMENT=container cloudnotes:local
```

Kontener nasłuchuje na porcie `8000`. Port można zmienić zmienną `PORT`.

## Azure Function

Katalog `function/` zawiera jedną funkcję w modelu programowania Python v2:

```text
Queue report-jobs -> generate_report -> Blob reports/note-<id>.txt
```

Funkcja korzysta z ustawienia `CLOUDNOTES_STORAGE`. Jest to connection string albo konfiguracja tożsamości tego samego Storage Account, którego używa aplikacja. Jeżeli treść notatki zawiera `#fail`, funkcja celowo zgłasza błąd. Po 3 próbach (`maxDequeueCount` w `host.json`) wiadomość trafia do kolejki `report-jobs-poison`. Na tym przykładzie w L10 omawiamy retry i poison queue.

Aplikacja wysyła wiadomości zakodowane w Base64, bo tego domyślnie oczekuje queue trigger Azure Functions.

## Środowisko testowe prowadzącego

Katalog `dev/` pozwala sprawdzić cały tryb chmurowy bez subskrypcji Azure. PostgreSQL działa w kontenerze, Azurite emuluje Blob i Queue, a host Azure Functions działa na oficjalnym obrazie.

```bash
cd dev
docker compose up -d
docker compose --profile function up -d function
```

```bash
cd src
DATABASE_URL="postgresql://cloudnotes:cloudnotes@localhost:5432/cloudnotes" STORAGE_CONNECTION_STRING="UseDevelopmentStorage=true" APP_ENVIRONMENT=dev-cloud .venv/bin/gunicorn --bind 127.0.0.1:8000 app:app
```

Na komputerach z procesorem ARM obraz Functions działa w emulacji `linux/amd64`, więc startuje wolniej.

Sprzątanie:

```bash
cd dev
docker compose --profile function down
```

Studenci nie potrzebują tego środowiska. Jest przeznaczone do przygotowania zajęć i sprawdzania zmian w kodzie.

## Ewolucja projektu w laboratoriach

| Laboratorium | Stan projektu po zajęciach | Checkpoint |
| --- | --- | --- |
| L01 | środowisko pracy, brak zasobów projektu | - |
| L02 | `Internet -> VM -> CloudNotes` w trybie lokalnym | `cp02-vm` |
| L03 | `Client -> App Service` w trybie lokalnym | `cp03-app-service` |
| L04 | `Client -> App Service -> Blob Storage` | `cp04-blob` |
| L05 | App Service + Blob Storage + PostgreSQL | `cp05-database` |
| L06 | wiele instancji tej samej aplikacji | `cp05-database` |
| L07 | awarie i restart bez utraty danych | `cp05-database` |
| L08 | sekrety w Key Vault, dostęp przez managed identity | `cp08-key-vault` |
| L09 | Application Insights i alert | `cp09-monitoring` |
| L10 | `App Service -> Queue -> Function -> Blob Storage` | `cp10-queue-function` |
| L11 | ten sam kod jako kontener w Azure Container Apps | `cp11-container` |
| L12 | kilka zasobów tworzonych przez IaC | - |
| L13-L14 | przegląd całej architektury | `cp10-queue-function` |

Opis każdego checkpointu znajduje się w [checkpoints/README.md](checkpoints/README.md).
