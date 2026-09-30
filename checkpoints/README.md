# Checkpointy projektu CloudNotes

Kod aplikacji jest taki sam na wszystkich etapach. Checkpoint opisuje stan **infrastruktury i konfiguracji** po danym laboratorium:

- jakie zasoby istnieją,
- jakie App Settings ma aplikacja,
- jak wygląda architektura.

Student, który nie ukończył laboratorium, odtwarza zasoby z wybranego checkpointu i ustawia podane zmienne. Nie musi niczego zmieniać w kodzie.

Pliki `*.env` w checkpointach są szablonami. Wartości w nawiasach ostrych, np. `<SUFFIX>` albo `<HASLO>`, trzeba zastąpić własnymi. Nie wolno commitować plików z prawdziwymi sekretami.

Polecenia odtwarzające zasoby dla każdego checkpointu są częścią instrukcji odpowiedniego laboratorium (`labs/NN-*/material.md`, sekcja o stanie startowym).

Nazwy zasobów są zgodne z [shared/conventions.md](../../shared/conventions.md).

## cp02-vm

Po L02. Zasoby tymczasowe w `rg-lab02-$SUFFIX` są usuwane na końcu laboratorium, więc kolejne zajęcia nie zależą od tego checkpointu.

```text
Internet -> Public IP -> NSG -> VM -> gunicorn -> CloudNotes (SQLite i pliki na dysku VM)
```

Konfiguracja: [cp02-vm/app-settings.env](cp02-vm/app-settings.env).

## cp03-app-service

Po L03. Aplikacja działa w trybie lokalnym, więc dane są w `/tmp` instancji i znikają po restarcie.

```text
Client -> App Service (CloudNotes, SQLite i pliki w /tmp)
```

Zasoby w `rg-cloudnotes-$SUFFIX`: App Service Plan `plan-cloudnotes-$SUFFIX`, Web App `app-cloudnotes-$SUFFIX`.

Konfiguracja: [cp03-app-service/app-settings.env](cp03-app-service/app-settings.env).

## cp04-blob

Po L04. Załączniki i raporty są w Blob Storage. Notatki nadal są w lokalnym SQLite.

```text
Client -> App Service -> Blob Storage
```

Nowe zasoby: Storage Account `stcloudnotes$SUFFIX` z containerami `attachments` i `reports`.

Konfiguracja: [cp04-blob/app-settings.env](cp04-blob/app-settings.env).

## cp05-database

Po L05. Cały stan aplikacji jest poza instancją compute. Z tego checkpointu startują również L06 i L07.

```text
                 Managed Database (PostgreSQL)
                        |
Client -> App Service --+
                        |
                   Blob Storage
```

Nowe zasoby: Azure Database for PostgreSQL Flexible Server `psql-cloudnotes-$SUFFIX` (Burstable B1ms), baza `cloudnotes`.

Konfiguracja: [cp05-database/app-settings.env](cp05-database/app-settings.env).

## cp08-key-vault

Po L08. Sekrety są w Key Vault. Aplikacja ma system-assigned managed identity z rolą `Key Vault Secrets User` na zakresie Key Vault. W App Settings nie ma już haseł ani kluczy.

```text
App Service -> Managed Identity -> Key Vault
App Service -> PostgreSQL
App Service -> Blob Storage
```

Nowe zasoby: Key Vault `kv-cloudnotes-$SUFFIX` z sekretami `database-url` i `storage-connection-string`.

Konfiguracja: [cp08-key-vault/app-settings.env](cp08-key-vault/app-settings.env), sekrety: [cp08-key-vault/key-vault-secrets.env](cp08-key-vault/key-vault-secrets.env).

## cp09-monitoring

Po L09. Aplikacja wysyła telemetrię do Application Insights.

Nowe zasoby: Log Analytics workspace `log-cloudnotes-$SUFFIX`, Application Insights `appi-cloudnotes-$SUFFIX`, prosty alert.

Konfiguracja: [cp09-monitoring/app-settings.env](cp09-monitoring/app-settings.env).

## cp10-queue-function

Po L10. Docelowa architektura kursu.

```text
                                            Blob Storage
                                                 ^
                                                 |
Users -> App Service -> Queue (report-jobs) -> Function
            |
            +------ PostgreSQL
            |
            +------ Blob Storage
            |
            +------ Key Vault
            |
            +------ Application Insights
```

Nowe zasoby: kolejka `report-jobs` w `stcloudnotes$SUFFIX`, Function App `func-cloudnotes-$SUFFIX` z kodem z `project/function/`.

Konfiguracja aplikacji nie zmienia się względem cp09, bo kolejka korzysta z tego samego Storage Account. Konfiguracja Function App: [cp10-queue-function/function-settings.env](cp10-queue-function/function-settings.env).

## cp11-container

Po L11. Ten sam kod działa jako kontener w Azure Container Apps. Obraz jest w Azure Container Registry.

```text
source code -> image -> Container Registry -> Container Apps -> PostgreSQL, Blob Storage
```

Nowe zasoby: Container Registry `crcloudnotes$SUFFIX`, środowisko `cae-cloudnotes-$SUFFIX`, Container App `ca-cloudnotes-$SUFFIX`.

Konfiguracja kontenera: [cp11-container/container-env.env](cp11-container/container-env.env).
