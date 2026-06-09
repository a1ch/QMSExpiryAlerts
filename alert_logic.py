"""Pure functions that decide which documents need an alert today."""
from datetime import datetime
from zoneinfo import ZoneInfo


def parse_expiry(raw, tz):
    """Parse an ISO-8601 SharePoint date into a local calendar date."""
    dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo(tz)).date()


def categorize(documents, tz, warn_days, today=None):
    """Bucket documents into warn-day thresholds and an 'expired' group.

    Rules:
      * a document is flagged at each exact warn-day threshold (e.g. 30, 7)
      * once expired (days remaining <= 0) it is flagged on every run (daily)
    Returns: {"warn": {day: [docs]}, "expired": [docs]}
    """
    tzinfo = ZoneInfo(tz)
    today = today or datetime.now(tzinfo).date()
    warn_set = set(warn_days)

    buckets = {"warn": {d: [] for d in warn_days}, "expired": []}
    for doc in documents:
        try:
            expiry = parse_expiry(doc["expiry_raw"], tz)
        except (ValueError, TypeError):
            logging_skip(doc)
            continue
        days = (expiry - today).days
        enriched = {**doc, "expiry_date": expiry.isoformat(), "days": days}
        if days <= 0:
            buckets["expired"].append(enriched)
        elif days in warn_set:
            buckets["warn"][days].append(enriched)
    return buckets


def logging_skip(doc):
    import logging

    logging.warning("Skipping item with unparseable expiry: %s", doc.get("file_name"))


def has_alerts(buckets):
    if buckets["expired"]:
        return True
    return any(docs for docs in buckets["warn"].values())
