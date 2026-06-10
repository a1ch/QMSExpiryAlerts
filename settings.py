"""Configuration loaded from environment / Azure app settings.

The Azure AD app-registration secrets (tenant id, client id, client secret)
are resolved in one of two ways:

* **On Azure** - if ``KEY_VAULT_URI`` is set, the function reads the three
  secrets straight from Key Vault at runtime using its **managed identity**
  (``azure-keyvault-secrets`` + ``azure-identity``). This deliberately bypasses
  app-setting ``@Microsoft.KeyVault(...)`` references, whose platform-side
  resolution is unreliable on the Flex Consumption plan (a failed reference is
  silently replaced with the literal reference string, which then surfaces as
  ``ValueError: Invalid tenant ID``).

* **Local dev / tests** - if ``KEY_VAULT_URI`` is not set, the three values are
  read from plain environment variables (``TENANT_ID`` / ``CLIENT_ID`` /
  ``CLIENT_SECRET``), which Doppler injects via ``doppler run``.
"""
import logging
import os
import re

logger = logging.getLogger(__name__)


def _get(name, default=None, required=False):
    val = os.environ.get(name, default)
    if required and (val is None or str(val).strip() == ""):
        raise RuntimeError(f"Missing required app setting: {name}")
    return val


def _split(raw):
    return [p.strip() for p in re.split(r"[;,]", raw or "") if p.strip()]


def _load_aad_secrets():
    """Return ``(tenant_id, client_id, client_secret)``.

    Reads from Key Vault via managed identity when ``KEY_VAULT_URI`` is set,
    otherwise falls back to plain environment variables for local development.
    """
    vault_uri = (os.environ.get("KEY_VAULT_URI") or "").strip()

    if not vault_uri:
        # Local dev / tests: Doppler (or local.settings.json) supplies these.
        return (
            _get("TENANT_ID", required=True),
            _get("CLIENT_ID", required=True),
            _get("CLIENT_SECRET", required=True),
        )

    # Imported lazily so local runs/tests don't need the Key Vault package.
    from azure.identity import ManagedIdentityCredential
    from azure.keyvault.secrets import SecretClient

    # Use a user-assigned identity if its client id is provided; otherwise the
    # app's system-assigned identity.
    mi_client_id = (os.environ.get("MANAGED_IDENTITY_CLIENT_ID") or "").strip()
    if mi_client_id:
        credential = ManagedIdentityCredential(client_id=mi_client_id)
        identity_desc = f"user-assigned ({mi_client_id})"
    else:
        credential = ManagedIdentityCredential()
        identity_desc = "system-assigned"

    # Secret names are configurable because Doppler->Key Vault rewrites "_"->"-"
    # and naming has varied; defaults match the current vault.
    tenant_name = _get("KV_SECRET_TENANT_ID", "AZURE-TENANT-ID")
    client_name = _get("KV_SECRET_CLIENT_ID", "AZURE-CLIENT-ID")
    secret_name = _get("KV_SECRET_CLIENT_SECRET", "AZURE-CLIENT-SECRET")

    logger.info(
        "Loading AAD secrets from Key Vault %s using %s identity "
        "(secrets: %s, %s, %s).",
        vault_uri, identity_desc, tenant_name, client_name, secret_name,
    )

    client = SecretClient(vault_url=vault_uri, credential=credential)

    def _fetch(name):
        try:
            value = client.get_secret(name).value
        except Exception as exc:  # noqa: BLE001 - surface a clear, safe message
            raise RuntimeError(
                f"Failed to read secret '{name}' from {vault_uri} using the "
                f"{identity_desc} managed identity. Confirm the secret name "
                f"exists and that this identity has the 'Key Vault Secrets "
                f"User' role on the vault. Underlying error: {type(exc).__name__}"
            ) from exc
        if value is None or value.strip() == "":
            raise RuntimeError(f"Secret '{name}' in {vault_uri} is empty.")
        return value.strip()

    return _fetch(tenant_name), _fetch(client_name), _fetch(secret_name)


class Settings:
    """Strongly-typed view over the app settings used by the function."""

    def __init__(self):
        # Azure AD app registration (client-credentials flow)
        self.tenant_id, self.client_id, self.client_secret = _load_aad_secrets()

        # SharePoint target (defaults point at the QMS Documents library)
        self.site_id = _get("SHAREPOINT_SITE_ID", required=True)
        self.list_id = _get("QMS_LIST_ID", required=True)
        self.expiry_field = _get("EXPIRY_FIELD", "Document_x0020_Expiry_x0020_Date")

        # Email delivery via Microsoft Graph sendMail
        self.sender = _get("ALERT_SENDER", required=True)
        self.recipients = _split(_get("ALERT_RECIPIENTS", required=True))

        # Behaviour
        self.timezone = _get("ALERT_TIMEZONE", "America/Edmonton")
        self.warn_days = sorted({int(d) for d in _split(_get("WARN_DAYS", "30,7"))}, reverse=True)

        self.graph_base = _get("GRAPH_BASE", "https://graph.microsoft.com/v1.0")
