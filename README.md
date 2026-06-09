# QMS Document Expiry Alerts

A timer-triggered **Azure Function (Python v2)** that reads the SharePoint
**QMS Documents** library live and emails an alert when a controlled document is
approaching or past its **Document Expiry Date**.

## Alert rules

For every list item that **has a value** in the `Document Expiry Date`
(`Document_x0020_Expiry_x0020_Date`) field:

| Condition | Behaviour |
|-----------|-----------|
| Exactly **30 days** before expiry | One alert |
| Exactly **7 days** before expiry  | One alert |
| Expiry date is **today or in the past** | Alert on **every run** (daily) until fixed |

Documents **without** a Document Expiry Date value are ignored. Thresholds are
configurable via the `WARN_DAYS` setting. The function only sends an email when
at least one document matches; otherwise it logs and exits (no spam).

> Note: the 30/7-day notices fire on the *exact* day. Because the function runs
> daily this is reliable, but if a scheduled run is missed (outage) that day's
> 30/7 notice is skipped. Expired items keep alerting daily regardless. This can
> be made fully catch-up/stateful later if needed.

## How it works

1. Authenticates to Microsoft Graph with the **client-credentials** flow
   (`azure-identity` -> app registration).
2. Pages through `/sites/{siteId}/lists/{listId}/items?$expand=fields` and keeps
   items where the expiry field is set (filtered client-side, so no indexed
   column is required).
3. Buckets them by days-to-expiry in the configured timezone.
4. Builds an HTML summary and sends it via Graph `sendMail`.

## Files

| File | Purpose |
|------|---------|
| `function_app.py` | Timer trigger + orchestration |
| `graph_client.py` | Graph auth, list paging, sendMail |
| `alert_logic.py`  | Pure date-threshold bucketing |
| `emailer.py`      | HTML email / sendMail payload |
| `settings.py`     | App-setting loader |
| `host.json`, `requirements.txt` | Function host config + deps |
| `local.settings.json` | Local run settings (git-ignored) |
| `azure-app-settings.template.txt` | Blank template to paste secrets into |
| `tests/` | Offline unit tests for the threshold logic |

## One-time Azure AD app registration

Create an app registration (Entra ID > App registrations) and grant
**Application** permissions (admin consent required):

- `Sites.Read.All` - read the QMS library. *(Prefer `Sites.Selected` granted on
  just this site if you want least-privilege.)*
- `Mail.Send` - send the alert email as the `ALERT_SENDER` mailbox.

Create a client secret and note the **Tenant ID**, **Client ID**, **Secret**.

> Tip: with `Mail.Send` application permission, any account can technically send
> as any mailbox. To lock it to only the alerts mailbox, apply an Exchange
> **Application Access Policy** scoped to `ALERT_SENDER`.

## Configuration

Fill these in `azure-app-settings.template.txt`, then add them as Function App
**environment variables** (or Key Vault references):

| Setting | Example | Notes |
|---------|---------|-------|
| `TENANT_ID` | `00000000-...` | |
| `CLIENT_ID` | `00000000-...` | |
| `CLIENT_SECRET` | *(secret)* | Use Key Vault in production |
| `ALERT_SENDER` | `qms-alerts@streamflo.com` | Mailbox the email is sent from |
| `ALERT_RECIPIENTS` | `a@streamflo.com; b@streamflo.com` | `;` or `,` separated |
| `SHAREPOINT_SITE_ID` | *(pre-filled)* | QMS / Quality site |
| `QMS_LIST_ID` | *(pre-filled)* | QMS Documents library |
| `EXPIRY_FIELD` | `Document_x0020_Expiry_x0020_Date` | Internal column name |
| `ALERT_TIMEZONE` | `America/Edmonton` | Used for "days until" math |
| `WARN_DAYS` | `30,7` | Pre-expiry thresholds |
| `EXPIRY_ALERT_SCHEDULE` | `0 0 13 * * *` | NCRONTAB (13:00 UTC = 07:00 MDT) |

## Run locally

```bash
python -m venv .venv && . .venv/bin/activate    # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
# fill in local.settings.json values first
func start
```

Run the offline logic tests (no Azure needed):

```bash
python tests/test_alert_logic.py
```

## Deploy

```bash
# one Function App (Linux, Python 3.11) + storage required
func azure functionapp publish <your-function-app-name>
```

Then set the app settings above in the portal (or via `az functionapp config
appsettings set`). The schedule fires automatically once deployed.
