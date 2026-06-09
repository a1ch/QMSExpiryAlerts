"""Builds the HTML alert email as a Microsoft Graph sendMail payload."""
import html


def _doc_row(doc):
    name = html.escape(str(doc.get("file_name") or doc.get("title") or "(unnamed)"))
    number = html.escape(str(doc.get("doc_number") or ""))
    url = html.escape(str(doc.get("web_url") or "#"))
    expiry = html.escape(str(doc.get("expiry_date") or ""))
    days = doc.get("days")
    if days is None:
        days_label = ""
    elif days < 0:
        days_label = f"{abs(days)} day(s) ago"
    elif days == 0:
        days_label = "today"
    else:
        days_label = f"in {days} day(s)"
    return (
        "<tr>"
        f'<td style="padding:6px 12px;border:1px solid #ddd;"><a href="{url}">{name}</a></td>'
        f'<td style="padding:6px 12px;border:1px solid #ddd;">{number}</td>'
        f'<td style="padding:6px 12px;border:1px solid #ddd;">{expiry}</td>'
        f'<td style="padding:6px 12px;border:1px solid #ddd;">{days_label}</td>'
        "</tr>"
    )


def _section(title, color, docs):
    if not docs:
        return ""
    rows = "".join(_doc_row(d) for d in sorted(docs, key=lambda x: x.get("days", 0)))
    return (
        f'<h3 style="color:{color};margin:18px 0 6px;">{html.escape(title)} '
        f"({len(docs)})</h3>"
        '<table style="border-collapse:collapse;font-family:Segoe UI,Arial,sans-serif;'
        'font-size:13px;width:100%;">'
        '<tr style="background:#f3f3f3;">'
        '<th style="padding:6px 12px;border:1px solid #ddd;text-align:left;">Document</th>'
        '<th style="padding:6px 12px;border:1px solid #ddd;text-align:left;">Number</th>'
        '<th style="padding:6px 12px;border:1px solid #ddd;text-align:left;">Expiry date</th>'
        '<th style="padding:6px 12px;border:1px solid #ddd;text-align:left;">Expires</th>'
        f"</tr>{rows}</table>"
    )


def build_body(buckets, warn_days):
    parts = [
        '<div style="font-family:Segoe UI,Arial,sans-serif;color:#222;">',
        '<p style="font-size:14px;">The following QMS controlled documents are '
        "approaching or past their <strong>Document Expiry Date</strong>.</p>",
    ]
    parts.append(_section("Expired", "#b00020", buckets["expired"]))
    for day in warn_days:
        parts.append(
            _section(f"Expiring in {day} days", "#c77700", buckets["warn"].get(day, []))
        )
    parts.append(
        '<p style="font-size:11px;color:#888;margin-top:18px;">'
        "Automated notice from the QMS Document Expiry Alerts Azure Function. "
        "Documents without a Document Expiry Date value are not tracked.</p></div>"
    )
    return "".join(p for p in parts if p)


def build_subject(buckets, warn_days):
    expired = len(buckets["expired"])
    warning = sum(len(buckets["warn"].get(d, [])) for d in warn_days)
    bits = []
    if expired:
        bits.append(f"{expired} expired")
    if warning:
        bits.append(f"{warning} expiring")
    summary = ", ".join(bits) if bits else "no items"
    return f"[QMS] Document expiry alert - {summary}"


def build_message(buckets, recipients, warn_days, save_to_sent=False):
    return {
        "message": {
            "subject": build_subject(buckets, warn_days),
            "body": {"contentType": "HTML", "content": build_body(buckets, warn_days)},
            "toRecipients": [
                {"emailAddress": {"address": addr}} for addr in recipients
            ],
        },
        "saveToSentItems": save_to_sent,
    }
