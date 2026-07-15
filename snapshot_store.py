"""Weekly AVL snapshot persistence in Azure Blob Storage.

The supplier-change digest is stateful: to know what changed since last week we
compare the current AVL against the previous run's snapshot. Snapshots are kept
as JSON blobs in the Function App's own storage account (the same account the
Functions runtime already uses via ``AzureWebJobsStorage``), so there is no new
infrastructure to provision.

Layout in the container (default ``avl-snapshots``):
    latest.json              - the snapshot the next run diffs against
    archive/YYYY-MM-DD.json   - dated copy kept for audit/history
"""
import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


def _client(settings):
    """Build a BlobServiceClient from AzureWebJobsStorage.

    Supports both a classic connection string and an identity-based setup
    (``AzureWebJobsStorage__accountName`` / ``...__blobServiceUri`` with a
    managed identity), which is what Flex Consumption apps use.
    """
    from azure.storage.blob import BlobServiceClient

    conn = os.environ.get("AzureWebJobsStorage")
    if conn and conn.lower() not in ("", "managedidentity"):
        return BlobServiceClient.from_connection_string(conn)

    # Identity-based connection (no secret in app settings).
    account = os.environ.get("AzureWebJobsStorage__accountName")
    service_uri = os.environ.get("AzureWebJobsStorage__blobServiceUri")
    if not service_uri and account:
        service_uri = f"https://{account}.blob.core.windows.net"
    if not service_uri:
        raise RuntimeError(
            "No storage connection found. Set AzureWebJobsStorage (connection "
            "string) or AzureWebJobsStorage__blobServiceUri for identity access."
        )

    from azure.identity import DefaultAzureCredential

    mi_client_id = (os.environ.get("MANAGED_IDENTITY_CLIENT_ID") or "").strip()
    cred = (
        DefaultAzureCredential(managed_identity_client_id=mi_client_id)
        if mi_client_id
        else DefaultAzureCredential()
    )
    return BlobServiceClient(account_url=service_uri, credential=cred)


def _container(settings):
    svc = _client(settings)
    container = svc.get_container_client(settings.snapshot_container)
    try:
        container.create_container()
    except Exception:  # noqa: BLE001 - already exists is the common case
        pass
    return container


def load_previous(settings):
    """Return the previous snapshot as a list of records, or None if first run."""
    try:
        container = _container(settings)
        blob = container.get_blob_client(settings.snapshot_blob)
        if not blob.exists():
            logger.info("No previous snapshot (%s); first run.", settings.snapshot_blob)
            return None
        raw = blob.download_blob().readall()
        data = json.loads(raw)
        return data.get("suppliers", data) if isinstance(data, dict) else data
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not load previous snapshot: %s", exc)
        return None


def save_current(settings, suppliers):
    """Persist the current snapshot as latest.json plus a dated archive copy."""
    container = _container(settings)
    payload = json.dumps(
        {
            "generated": datetime.utcnow().isoformat() + "Z",
            "count": len(suppliers),
            "suppliers": suppliers,
        },
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")

    container.get_blob_client(settings.snapshot_blob).upload_blob(
        payload, overwrite=True
    )
    dated = f"archive/{datetime.utcnow():%Y-%m-%d}.json"
    try:
        container.get_blob_client(dated).upload_blob(payload, overwrite=True)
    except Exception as exc:  # noqa: BLE001 - archive is best-effort
        logger.warning("Could not write archive snapshot %s: %s", dated, exc)
    logger.info("Saved snapshot (%d suppliers) to %s.", len(suppliers), settings.snapshot_blob)
