"""Thin Microsoft Graph client for reading the QMS library and sending mail."""
import logging

import requests
from azure.identity import ClientSecretCredential

logger = logging.getLogger(__name__)

_SELECT_FIELDS = [
    "FileLeafRef",
    "Title",
    "Document_x0020_Number",
    "OneFloDocumentNumber",
]


class GraphClient:
    def __init__(self, settings):
        self.s = settings
        self._cred = ClientSecretCredential(
            tenant_id=settings.tenant_id,
            client_id=settings.client_id,
            client_secret=settings.client_secret,
        )

    def _headers(self):
        token = self._cred.get_token("https://graph.microsoft.com/.default").token
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    def get_documents_with_expiry(self):
        """Return every list item that has a non-empty expiry-date field.

        Filtering is done client-side so it does not depend on the column
        being indexed in SharePoint.
        """
        field = self.s.expiry_field
        select = ",".join(_SELECT_FIELDS + [field])
        url = (
            f"{self.s.graph_base}/sites/{self.s.site_id}/lists/{self.s.list_id}/items"
            f"?$expand=fields($select={select})&$top=200"
        )

        headers = self._headers()
        results = []
        while url:
            resp = requests.get(url, headers=headers, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("value", []):
                fields = item.get("fields", {}) or {}
                raw = fields.get(field)
                if not raw:
                    continue  # rule: only documents that HAVE the expiry field set
                results.append(
                    {
                        "id": item.get("id"),
                        "web_url": item.get("webUrl"),
                        "file_name": fields.get("FileLeafRef"),
                        "title": fields.get("Title"),
                        "doc_number": fields.get("Document_x0020_Number")
                        or fields.get("OneFloDocumentNumber"),
                        "expiry_raw": raw,
                    }
                )
            url = data.get("@odata.nextLink")
        return results

    def send_mail(self, sender, message):
        url = f"{self.s.graph_base}/users/{sender}/sendMail"
        headers = {**self._headers(), "Content-Type": "application/json"}
        resp = requests.post(url, headers=headers, json=message, timeout=60)
        resp.raise_for_status()
