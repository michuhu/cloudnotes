# Checkpointy projektu CloudNotes

Kod aplikacji jest taki sam na wszystkich etapach. Checkpoint opisuje stan **infrastruktury i konfiguracji** po danym laboratorium:

- jakie zasoby istnieją,
- jakie App Settings ma aplikacja,
- jak wygląda architektura.

Student, który nie ukończył laboratorium, odtwarza zasoby z wybranego checkpointu i ustawia podaną konfigurację. Nie musi niczego zmieniać w kodzie.

Checkpointy nie używają plików `.env`. Konfiguracja każdego etapu jest podana jako jawne polecenie Azure CLI. Wartości w nawiasach ostrych trzeba zastąpić własnymi, razem z nawiasami:

| Placeholder | Skąd wziąć wartość |
| --- | --- |
| `<SUFFIX>` | identyfikator wybrany w L01 |
| `<HASLO>` | hasło administratora PostgreSQL ustawione w L05 |
| `<CONNECTION_STRING_STORAGE_ACCOUNT>` | wynik polecenia `az storage account show-connection-string --resource-group rg-cloudnotes --name stcloudnotes<SUFFIX> --query connectionString --output tsv` |
| `<CONNECTION_STRING_APPLICATION_INSIGHTS>` | wynik polecenia `az monitor app-insights component show --resource-group rg-cloudnotes --app appi-cloudnotes-<SUFFIX> --query connectionString --output tsv` |

Wartości zawierające znaki `;` i `&` (connection stringi, `DATABASE_URL`) zawsze umieszczamy w cudzysłowie. Nie wolno commitować poleceń z prawdziwymi sekretami.

Polecenia odtwarzające zasoby dla każdego checkpointu są częścią instrukcji odpowiedniego laboratorium (`labs/NN-*/material.md`, sekcja o stanie startowym).

Nazwy zasobów są zgodne z konwencjami kursu (Resource Group projektu: `rg-cloudnotes`).

## cp02-vm

Po L02. Zasoby tymczasowe w `rg-lab02` są usuwane na końcu laboratorium, więc kolejne zajęcia nie zależą od tego checkpointu.

```text
Internet -> Public IP -> NSG -> VM -> gunicorn -> CloudNotes (SQLite i pliki w /tmp na dysku VM)
```

Zasoby w `rg-lab02`: VNet `vnet-lab02` (`10.20.0.0/16`) z podsiecią `snet-app` (`10.20.1.0/24`), NSG `nsg-lab02` przypisany do podsieci, publiczny adres `pip-lab02`, VM `vm-lab02` (`Standard_B2ats_v2`, Ubuntu 24.04). CloudNotes działa jako usługa `systemd` z Gunicornem na porcie 8000.

Konfiguracja jest zapisana bezpośrednio w unicie `systemd` jako linia:

```ini
Environment=APP_ENVIRONMENT=vm
```

## cp03-app-service

Po L03. Aplikacja działa w trybie lokalnym, więc dane są w `/tmp` instancji i znikają po restarcie.

```text
Client -> App Service (CloudNotes, SQLite i pliki w /tmp)
```

Zasoby w `rg-cloudnotes`: App Service Plan `plan-cloudnotes-<SUFFIX>`, Web App `app-cloudnotes-<SUFFIX>`.

Konfiguracja:

```bash
az webapp config appsettings set --resource-group rg-cloudnotes --name app-cloudnotes-<SUFFIX> --settings APP_ENVIRONMENT=app-service
```

## cp04-blob

Po L04. Załączniki i raporty są w Blob Storage. Notatki nadal są w lokalnym SQLite.

```text
Client -> App Service -> Blob Storage
```

Nowe zasoby: Storage Account `stcloudnotes<SUFFIX>` z containerami `attachments` i `reports`.

Konfiguracja:

```bash
az webapp config appsettings set --resource-group rg-cloudnotes --name app-cloudnotes-<SUFFIX> --settings APP_ENVIRONMENT=app-service STORAGE_CONNECTION_STRING="<CONNECTION_STRING_STORAGE_ACCOUNT>"
```

## cp05-database

Po L05. Cały stan aplikacji jest poza instancją compute. Z tego checkpointu startują również L06 i L07.

```text
                 Managed Database (PostgreSQL)
                        |
Client -> App Service --+
                        |
                   Blob Storage
```

Nowe zasoby: Azure Database for PostgreSQL Flexible Server `psql-cloudnotes-<SUFFIX>` (Burstable B1ms), baza `cloudnotes`.

Konfiguracja:

```bash
az webapp config appsettings set --resource-group rg-cloudnotes --name app-cloudnotes-<SUFFIX> --settings APP_ENVIRONMENT=app-service STORAGE_CONNECTION_STRING="<CONNECTION_STRING_STORAGE_ACCOUNT>" DATABASE_URL="postgresql://cloudnotesadmin:<HASLO>@psql-cloudnotes-<SUFFIX>.postgres.database.azure.com:5432/cloudnotes?sslmode=require"
```

## cp08-key-vault

Po L08. Sekrety są w Key Vault. Aplikacja ma system-assigned managed identity z rolą `Key Vault Secrets User` na zakresie Key Vault. W App Settings nie ma już haseł ani kluczy.

```text
App Service -> Managed Identity -> Key Vault
App Service -> PostgreSQL
App Service -> Blob Storage
```

Nowe zasoby: Key Vault `kv-cloudnotes-<SUFFIX>` z sekretami `database-url` i `storage-connection-string`.

Sekrety:

```bash
az keyvault secret set --vault-name kv-cloudnotes-<SUFFIX> --name database-url --value "postgresql://cloudnotesadmin:<HASLO>@psql-cloudnotes-<SUFFIX>.postgres.database.azure.com:5432/cloudnotes?sslmode=require"
az keyvault secret set --vault-name kv-cloudnotes-<SUFFIX> --name storage-connection-string --value "<CONNECTION_STRING_STORAGE_ACCOUNT>"
```

Konfiguracja aplikacji. Sekrety z poprzedniego etapu są usuwane z App Settings:

```bash
az webapp config appsettings delete --resource-group rg-cloudnotes --name app-cloudnotes-<SUFFIX> --setting-names STORAGE_CONNECTION_STRING DATABASE_URL
az webapp config appsettings set --resource-group rg-cloudnotes --name app-cloudnotes-<SUFFIX> --settings APP_ENVIRONMENT=app-service KEY_VAULT_URL=https://kv-cloudnotes-<SUFFIX>.vault.azure.net/
```

## cp09-monitoring

Po L09. Aplikacja wysyła telemetrię do Application Insights.

Nowe zasoby: Log Analytics workspace `log-cloudnotes-<SUFFIX>`, Application Insights `appi-cloudnotes-<SUFFIX>`, prosty alert.

Konfiguracja:

```bash
az webapp config appsettings set --resource-group rg-cloudnotes --name app-cloudnotes-<SUFFIX> --settings APP_ENVIRONMENT=app-service KEY_VAULT_URL=https://kv-cloudnotes-<SUFFIX>.vault.azure.net/ APPLICATIONINSIGHTS_CONNECTION_STRING="<CONNECTION_STRING_APPLICATION_INSIGHTS>"
```

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

Nowe zasoby: kolejka `report-jobs` w `stcloudnotes<SUFFIX>`, Function App `func-cloudnotes-<SUFFIX>` z kodem z katalogu `function/`.

Konfiguracja aplikacji nie zmienia się względem cp09, bo kolejka korzysta z tego samego Storage Account. Konfiguracja Function App:

```bash
az functionapp config appsettings set --resource-group rg-cloudnotes --name func-cloudnotes-<SUFFIX> --settings CLOUDNOTES_STORAGE="<CONNECTION_STRING_STORAGE_ACCOUNT>" REPORT_DELAY_SECONDS=5 APPLICATIONINSIGHTS_CONNECTION_STRING="<CONNECTION_STRING_APPLICATION_INSIGHTS>"
```

## cp11-container

Po L11. Ten sam kod działa jako kontener w Azure Container Apps. Obraz jest w Azure Container Registry.

```text
source code -> image -> Container Registry -> Container Apps -> PostgreSQL, Blob Storage
```

Nowe zasoby: Container Registry `crcloudnotes<SUFFIX>`, środowisko `cae-cloudnotes-<SUFFIX>`, Container App `ca-cloudnotes-<SUFFIX>`.

Konfiguracja kontenera:

```bash
az containerapp update --resource-group rg-cloudnotes --name ca-cloudnotes-<SUFFIX> --set-env-vars APP_ENVIRONMENT=container-apps STORAGE_CONNECTION_STRING="<CONNECTION_STRING_STORAGE_ACCOUNT>" DATABASE_URL="postgresql://cloudnotesadmin:<HASLO>@psql-cloudnotes-<SUFFIX>.postgres.database.azure.com:5432/cloudnotes?sslmode=require"
```
