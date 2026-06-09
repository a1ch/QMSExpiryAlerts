"""Configuration loaded from environment / Azure app settings."""
import os
import re


def _get(name, default=None, required=False):
    val = os.environ.get(name, default)
    if required and (val is None or str(val).strip() == ""):
        raise RuntimeError(f"Missing required app setting: {name}")
    return val


def _split(raw):
    return [p.strip() for p in re.split(r"[;,]", raw or "") if p.strip()]


class Settings:
    """Strongly-typed view over the app settings used by the function."""

    def __init__(self):
        # Azure AD app registration (client-credentials flow)
        self.tenant_id = _get("TENANT_ID", required=True)
        self.client_id = _get("CLIENT_ID", required=True)
        self.client_secret = _get("CLIENT_SECRET", required=True)

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
