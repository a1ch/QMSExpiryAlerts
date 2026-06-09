# Deployment — Azure Function with Doppler → Key Vault secrets

This guide stands up the QMS Document Expiry Alerts function in Azure and wires
secrets through **Doppler → Azure Key Vault → Key Vault references**. The
function code is unchanged: it reads plain environment variables, and Azure
resolves Key Vault references into those env vars at runtime.

```
 Doppler (source of truth)
     |  (sync integration)
     v
 Azure Key Vault  ──referenced by──>  Function App settings
     ^                                      |
     |  read via managed identity           v
     └──────────────────────────────  Function runtime (os.environ)
```

You fill in every blank yourself — none of these steps read your Doppler.

---

## What is a secret vs. plain config

| Setting | Put it in Doppler (→ Key Vault) | Plain app setting |
|---------|:---:|:---:|
| `CLIENT_SECRET` | ✅ (required — this is the only true secret) | |
| `TENANT_ID` | ✅ recommended | or plain |
| `CLIENT_ID` | ✅ recommended | or plain |
| `ALERT_SENDER` | | ✅ |
| `ALERT_RECIPIENTS` | | ✅ |
| `SHAREPOINT_SITE_ID` | | ✅ (pre-filled value) |
| `QMS_LIST_ID` | | ✅ (pre-filled value) |
| `EXPIRY_FIELD` | | ✅ |
| `ALERT_TIMEZONE` | | ✅ |
| `WARN_DAYS` | | ✅ |
| `EXPIRY_ALERT_SCHEDULE` | | ✅ |

At minimum keep `CLIENT_SECRET` in Doppler/Key Vault; the auth trio together is
cleanest.

---

## 1. Create the Function App

Create (or reuse) in the Azure Portal:

1. A **Resource group** (e.g. `rg-qms-alerts`).
2. A **Function App**:
   - Runtime stack: **Python 3.11**
   - OS: **Linux**
   - Plan: **Consumption** (or Flex Consumption) is fine for a daily timer.
   - A storage account is created automatically.

Deploy the code once it exists:

```bash
cd C:\Users\ShawnStubbs\Claude\QMSExpiryAlerts
func azure functionapp publish <your-function-app-name>
```

---

## 2. Give the Function App an identity

Function App → **Settings → Identity → System assigned** → toggle **On** → Save.
Copy the **Object (principal) ID** it shows — you'll grant it Key Vault access.

---

## 3. Create the Key Vault

1. Create a **Key Vault** (e.g. `kv-qms-alerts`) in the same region/resource group.
2. Set its permission model to **Azure role-based access control (RBAC)**
   (Key Vault → Settings → Access configuration).

### Grant the function read access

Key Vault → **Access control (IAM)** → **Add role assignment**:

- Role: **Key Vault Secrets User**
- Assign access to: **Managed identity** → your Function App
- Save.

> If you keep the vault on the legacy **access-policy** model instead of RBAC,
> add an access policy granting the Function App identity **Get** and **List**
> on secrets.

---

## 4. Connect Doppler to the Key Vault (you do this in Doppler)

In the Doppler dashboard, on the project/config that holds these secrets:

1. **Integrations → Sync → Azure Key Vault**.
2. Authorize Doppler to your Azure subscription (Doppler creates/uses a service
   principal — follow its prompts).
3. Choose the target **Key Vault** (`kv-qms-alerts`) and the Doppler **config**
   to sync.
4. Save. Doppler performs an initial sync, writing each secret into the vault.

### ⚠️ Naming gotcha — underscores become dashes

Azure Key Vault secret names allow only letters, numbers, and dashes. Doppler's
sync converts `_` → `-` automatically:

| Doppler secret | Key Vault secret name |
|----------------|-----------------------|
| `CLIENT_SECRET` | `CLIENT-SECRET` |
| `TENANT_ID` | `TENANT-ID` |
| `CLIENT_ID` | `CLIENT-ID` |

Your **app setting name** stays `CLIENT_SECRET` (that's what the code reads); only
the Key Vault secret it points at uses the dashed form.

---

## 5. Point app settings at Key Vault references

Function App → **Settings → Environment variables → App settings**. For each
secret, set the **value** to a Key Vault reference (not the secret itself):

```
@Microsoft.KeyVault(SecretUri=https://kv-qms-alerts.vault.azure.net/secrets/CLIENT-SECRET)
```

or the equivalent:

```
@Microsoft.KeyVault(VaultName=kv-qms-alerts;SecretName=CLIENT-SECRET)
```

So you would add, for example:

| App setting name | Value |
|------------------|-------|
| `CLIENT_SECRET` | `@Microsoft.KeyVault(SecretUri=.../secrets/CLIENT-SECRET)` |
| `TENANT_ID` | `@Microsoft.KeyVault(SecretUri=.../secrets/TENANT-ID)` |
| `CLIENT_ID` | `@Microsoft.KeyVault(SecretUri=.../secrets/CLIENT-ID)` |

Add the **plain** settings normally (real values, no reference):

```
SHAREPOINT_SITE_ID = streamflogroup.sharepoint.com,8038b92e-9f86-46c8-ba49-8a13f78ce602,baec0237-66e5-4a7d-ab2e-560e69763e17
QMS_LIST_ID        = c11c5e08-fed4-476d-bbba-7ea56947383d
EXPIRY_FIELD       = Document_x0020_Expiry_x0020_Date
ALERT_SENDER       = (the from mailbox)
ALERT_RECIPIENTS   = (semicolon/comma separated)
ALERT_TIMEZONE     = America/Edmonton
WARN_DAYS          = 30,7
EXPIRY_ALERT_SCHEDULE = 0 0 13 * * *
```

Save and let the app restart.

> Leaving the SecretUri **without** a version (no trailing GUID) means the
> function always picks up the latest version after a restart.

---

## 6. Verify

1. Function App → Environment variables: each reference shows a green
   **Key Vault Reference** resolved status. A red icon means the managed identity
   can't read that secret (recheck step 2–3) or the secret name is wrong
   (recheck the dash conversion in step 4).
2. Function App → **QmsExpiryAlerts → Code + Test → Test/Run**, or wait for the
   timer, then check **Monitor / Application Insights** logs for
   `Fetched N document(s) with an expiry date set.`
3. Confirm an alert email arrives (or `No documents at an alert threshold today`
   when nothing is due).

---

## Secret rotation

When you rotate a secret in Doppler, it re-syncs to Key Vault. Key Vault
references are cached by the Functions host and refresh periodically (up to ~24h).
To pick up a rotated secret immediately, **restart the Function App**.

---

## Local development with Doppler (optional)

To run locally with Doppler injecting the env vars (no Key Vault involved):

```bash
doppler login
doppler setup            # pick the project + config
doppler run -- func start
```

Because the code reads `os.environ`, Doppler-injected variables work the same as
Azure-resolved ones. Do **not** commit real values to `local.settings.json`
(it is git-ignored). A committed `doppler.yaml` only stores the project/config
*names*, never secrets, so it is safe to add if you want pinned defaults.
