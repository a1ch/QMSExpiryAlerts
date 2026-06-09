"""Timer-triggered Azure Function: QMS document expiry alerts.

Runs on a schedule, reads the SharePoint QMS Documents library live, and emails
an alert for every controlled document that is 30 or 7 days from its
Document Expiry Date, plus a daily reminder for anything already expired.
"""
import logging

import azure.functions as func

from alert_logic import categorize, has_alerts
from emailer import build_message
from graph_client import GraphClient
from settings import Settings

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
