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

# Fields pulled from the Corporate AVL (CorpAVLV2) for the supplier digest.
_AVL_SELECT_FIELDS = [
    "id",
    "Title",
    "CDBPKey",
    "BPNumber",
    "ApprovalRating",
    "QMSSupplier",
    "ScopeMatrix",
    "ApprovalMatrix",
    "CriticalScopeText",
    "CompanyCode",
    "OrganizationName",
    "City",
    "Region",
    "Country",
    "Auditor",
    "NotesQuality",
    "Modified",
]


def _as_list(value):
    """Normalize a SharePoint multi-choice value into a sorted list of strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return sorted(str(v).strip() for v in value if str(v).strip())
    text = str(value).strip()
    return [text] if text else []


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

    def get_qms_suppliers(self):
        """Return normalized records for every QMS supplier in the Corporate AVL.

        Reads the CorpAVLV2 list and keeps only rows where ``QMSSupplier`` is
        "Yes" (filtered client-side so no indexed column is required). Each
        record is a flat dict keyed for stable week-over-week diffing.
        """
        select = ",".join(_AVL_SELECT_FIELDS)
        url = (
            f"{self.s.graph_base}/sites/{self.s.avl_site_id}"
            f"/lists/{self.s.avl_list_id}/items"
            f"?$expand=fields($select={select})&$top=500"
        )

        headers = self._headers()
        results = []
        while url:
            resp = requests.get(url, headers=headers, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("value", []):
                fields = item.get("fields", {}) or {}
                if str(fields.get("QMSSupplier", "")).strip().lower() != "yes":
                    continue
                results.append(
                    {
                        # stable identity across snapshots: business-partner key,
                        # falling back to the list item id.
                        "key": str(
                            fields.get("CDBPKey")
                            or fields.get("BPNumber")
                            or item.get("id")
                        ),
                        "item_id": item.get("id"),
                        "web_url": item.get("webUrl"),
                        "name": fields.get("Title"),
                        "approval": (fields.get("ApprovalRating") or "").strip(),
                        "scope": _as_list(fields.get("ScopeMatrix")),
                        "approval_matrix": _as_list(fields.get("ApprovalMatrix")),
                        "critical_scope": (fields.get("CriticalScopeText") or "").strip(),
                        "company_code": str(fields.get("CompanyCode") or "").strip(),
                        "org": (fields.get("OrganizationName") or "").strip(),
                        "city": (fields.get("City") or "").strip(),
                        "region": (fields.get("Region") or "").strip(),
                        "country": (fields.get("Country") or "").strip(),
                        "auditor": (fields.get("Auditor") or "").strip(),
                        "notes_quality": (fields.get("NotesQuality") or "").strip(),
                        "modified": fields.get("Modified"),
                    }
                )
            url = data.get("@odata.nextLink")
        return results

    def send_mail(self, sender, message):
        url = f"{self.s.graph_base}/users/{sender}/sendMail"
        headers = {**self._headers(), "Content-Type": "application/json"}
        resp = requests.post(url, headers=headers, json=message, timeout=60)
        resp.raise_for_status()
