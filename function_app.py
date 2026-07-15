"""Timer-triggered Azure Functions for Stream-Flo Group QMS automation.

1. ``QmsExpiryAlerts`` - daily: reads the SharePoint QMS Documents library and
   emails an alert for controlled documents at 30/7 days to expiry (plus a daily
   reminder for anything already expired).

2. ``AvlSupplierChangeDigest`` - weekly (Mon): compares the Corporate AVL
   (CorpAVLV2, QMS suppliers only) against last week's snapshot and emails a
   changes-only digest of suspensions, approvals/reinstatements and scope
   changes, with SFI Edmonton listed first.
"""
import logging

import azure.functions as func

from alert_logic import categorize, has_alerts
from emailer import build_message
from graph_client import GraphClient
from settings import Settings

import snapshot_store
from avl_emailer import build_message as build_avl_message
from avl_logic import diff_snapshots, has_changes

app = func.FunctionApp()


@app.function_name(name="QmsExpiryAlerts")
@app.timer_trigger(
    schedule="%EXPIRY_ALERT_SCHEDULE%",
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True,
)
def qms_expiry_alerts(timer: func.TimerRequest) -> None:
    if timer.past_due:
        logging.warning("Timer is past due; running now.")

    settings = Settings()
    client = GraphClient(settings)

    documents = client.get_documents_with_expiry()
    logging.info("Fetched %d document(s) with an expiry date set.", len(documents))

    buckets = categorize(documents, settings.timezone, settings.warn_days)
    if not has_alerts(buckets):
        logging.info("No documents at an alert threshold today. No email sent.")
        return

    message = build_message(buckets, settings.recipients, settings.warn_days)
    client.send_mail(settings.sender, message)
    logging.info(
        "Alert email sent to %s (expired=%d, warning=%d).",
        ", ".join(settings.recipients),
        len(buckets["expired"]),
        sum(len(v) for v in buckets["warn"].values()),
    )


@app.function_name(name="AvlSupplierChangeDigest")
@app.timer_trigger(
    schedule="%AVL_DIGEST_SCHEDULE%",
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True,
)
def avl_supplier_change_digest(timer: func.TimerRequest) -> None:
    if timer.past_due:
        logging.warning("Timer is past due; running now.")

    settings = Settings()
    client = GraphClient(settings)

    current = client.get_qms_suppliers()
    logging.info("Fetched %d QMS supplier(s) from the Corporate AVL.", len(current))

    previous = snapshot_store.load_previous(settings)
    first_run = previous is None
    changes = diff_snapshots(previous or [], current)

    # First run has no baseline to compare against. By default just store the
    # baseline silently so next week's diff is meaningful (avoids an "all new"
    # blast on the very first run).
    if first_run and not settings.avl_send_on_first_run:
        snapshot_store.save_current(settings, current)
        logging.info(
            "First run: baseline of %d QMS supplier(s) saved; no email sent.",
            len(current),
        )
        return

    if has_changes(changes):
        message = build_avl_message(
            changes, settings.avl_recipients, settings.edmonton_company_code
        )
        client.send_mail(settings.avl_sender, message)
        logging.info(
            "AVL change digest sent to %s (%d change(s)).",
            ", ".join(settings.avl_recipients),
            len(changes),
        )
    else:
        logging.info("No AVL supplier changes since last week. No email sent.")

    # Advance the baseline only after a successful send (or a clean no-change
    # run). If send_mail raised above, we never reach here, so the change set is
    # retried on the next run rather than being silently lost.
    snapshot_store.save_current(settings, current)
