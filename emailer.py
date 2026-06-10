"""Builds the HTML alert email as a Microsoft Graph sendMail payload.

Styled to match the Stream-Flo Group "SharePoint Daily Digest" template:
navy group header, tri-color company ribbon, count pills, a summary card,
left-border item cards (colored by urgency), and a three-company footer.
"""
import html
from datetime import date, datetime

GROUP_NAME = "Stream-Flo Group"
ACCENT = "#003366"  # navy - links, header gradient, borders

# (display name, accent color, legal name) - shown in the ribbon and footer.
GROUP_BRANDS = [
    ("Stream-Flo", "#003366", "Stream-Flo USA LLC"),
    ("Master Flo", "#0066b3", "Master Flo Valve USA Inc."),
    ("Dycor", "#0d7a7a", "Dycor Technologies"),
]

# Urgency palette
EXPIRED_COLOR = "#b00020"   # red - past expiry / due today
WARN_COLOR = "#c77700"      # amber - expiring within a warn window


def _enc(s):
    return html.escape(str(s if s is not None else ""))


def _darken(hex_color, factor=0.72):
    """Darken a hex color (header gradient base, sub-bar)."""
    try:
        h = hex_color.lstrip("#")
        if len(h) != 6:
            return "#002a57"
        r = int(int(h[0:2], 16) * factor)
        g = int(int(h[2:4], 16) * factor)
        b = int(int(h[4:6], 16) * factor)
        return f"#{r:02X}{g:02X}{b:02X}"
    except Exception:
        return "#002a57"


def _tint(hex_color, amount=0.88):
    """Lighten a hex color toward white for soft chip/pill backgrounds."""
    try:
        h = hex_color.lstrip("#")
        if len(h) != 6:
            return "#eef2f7"

        def mix(c):
            return round(c + (255 - c) * amount)

        r = mix(int(h[0:2], 16))
        g = mix(int(h[2:4], 16))
        b = mix(int(h[4:6], 16))
        return f"#{r:02X}{g:02X}{b:02X}"
    except Exception:
        return "#eef2f7"


def _fmt_date(iso):
    """Format an ISO 'YYYY-MM-DD' string as 'Jun 9, 2026'."""
    try:
        d = datetime.strptime(str(iso), "%Y-%m-%d").date()
    except Exception:
        return _enc(iso)
    try:
        return d.strftime("%b %-d, %Y")
    except ValueError:  # Windows lacks %-d
        return d.strftime("%b %d, %Y")


def _days_label(days):
    """Return (text, color) describing how close to expiry a document is."""
    if days is None:
        return "", WARN_COLOR
    if days < 0:
        n = abs(days)
        return f"Expired {n} day{'s' if n != 1 else ''} ago", EXPIRED_COLOR
    if days == 0:
        return "Expires today", EXPIRED_COLOR
    return f"Expires in {days} day{'s' if days != 1 else ''}", WARN_COLOR


def _pill(text, color):
    soft = _tint(color, 0.88)
    return (
        f'<span style="display:inline-block; background:{soft}; color:{color}; '
        'font-size:12px; font-weight:700; letter-spacing:0.3px; padding:6px 14px; '
        f'border-radius:999px; margin:0 8px 8px 0;">{_enc(text)}</span>'
    )


def _summary_row(label, value, last):
    pad = "0" if last else "0 0 8px"
    return (
        f'<tr><td style="padding:{pad}; width:160px; color:#64748b; font-weight:600; '
        f'vertical-align:top;">{_enc(label)}</td>'
        f'<td style="padding:{pad}; color:#1e293b; vertical-align:top;">{_enc(value)}</td></tr>'
    )


def _doc_card(doc, accent):
    name = _enc(doc.get("file_name") or doc.get("title") or "(unnamed)")
    number = _enc(doc.get("doc_number") or "")
    url = _enc(doc.get("web_url") or "#")
    expiry = _fmt_date(doc.get("expiry_date") or "")
    label, label_color = _days_label(doc.get("days"))
    eyebrow = number if number else "Controlled document"
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="margin:0 0 10px; background:#ffffff; border:1px solid #eceff4; '
        f'border-left:4px solid {accent}; border-radius:10px;"><tr>'
        '<td style="padding:14px 16px;">'
        f'<div style="font-size:11px; font-weight:700; color:{accent}; letter-spacing:0.5px; '
        f'margin:0 0 4px;">{eyebrow}</div>'
        f'<a href="{url}" style="font-size:15px; font-weight:600; color:#0f172a; '
        f'text-decoration:none;">{name}</a>'
        '<div style="font-size:12.5px; color:#64748b; margin-top:6px;">'
        '<span style="color:#475569; font-weight:600;">Expiry</span> '
        f'{expiry} &nbsp;&middot;&nbsp; '
        f'<span style="color:{label_color}; font-weight:700;">{label}</span>'
        '</div></td></tr></table>'
    )


def _section(title, color, docs):
    if not docs:
        return ""
    cards = "".join(_doc_card(d, color) for d in sorted(docs, key=lambda x: x.get("days", 0)))
    return (
        '<tr><td style="padding:20px 36px 4px;">'
        '<div style="font-size:11px; font-weight:700; letter-spacing:1.4px; '
        'text-transform:uppercase; color:#94a3b8; border-top:1px solid #eceff4; '
        f'padding-top:18px;">{_enc(title)} ({len(docs)})</div></td></tr>'
        f'<tr><td style="padding:8px 36px 8px;">{cards}</td></tr>'
    )


def build_body(buckets, warn_days):
    accent = ACCENT
    accent_dark = _darken(accent, 0.72)
    expired = buckets["expired"]
    warn = buckets["warn"]
    n_expired = len(expired)
    n_warn = sum(len(warn.get(d, [])) for d in warn_days)
    company_names = "  &middot;  ".join(_enc(g[0]) for g in GROUP_BRANDS)
    today_str = date.today().strftime("%b %d, %Y")

    summary_bits = []
    if n_expired:
        summary_bits.append(f"{n_expired} expired")
    if n_warn:
        summary_bits.append(f"{n_warn} expiring soon")
    preheader = ", ".join(summary_bits) if summary_bits else "No documents due"

    sb = []
    sb.append('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/>')
    sb.append('<meta name="viewport" content="width=device-width, initial-scale=1"/>')
    sb.append('<meta name="color-scheme" content="light only"/>')
    sb.append("<title>QMS Document Expiry Alert</title></head>")
    sb.append(
        '<body style="margin:0; padding:0; width:100%; background:#eef2f7; '
        "font-family:'Segoe UI',Arial,sans-serif; font-size:15px; line-height:1.5; "
        'color:#1e293b; -webkit-font-smoothing:antialiased;">'
    )

    # Hidden preheader (inbox preview text)
    sb.append(
        '<div style="display:none; max-height:0; overflow:hidden; opacity:0; mso-hide:all;">'
        f"QMS controlled documents &mdash; {_enc(preheader)}</div>"
    )

    sb.append(
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="background:#eef2f7; padding:32px 16px;"><tr><td align="center">'
    )
    sb.append(
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" '
        'style="width:600px; max-width:600px; background:#ffffff; border-radius:14px; '
        'border:1px solid #e3e8ef; box-shadow:0 8px 24px rgba(15,23,42,0.08); overflow:hidden;">'
    )

    # Tri-color ribbon (one segment per company)
    sb.append(
        '<tr><td style="padding:0;"><table role="presentation" width="100%" '
        'cellpadding="0" cellspacing="0"><tr>'
    )
    for g in GROUP_BRANDS:
        sb.append(
            f'<td style="height:6px; line-height:6px; font-size:0; background:{g[1]};">&nbsp;</td>'
        )
    sb.append("</tr></table></td></tr>")

    # Group header
    sb.append(
        f'<tr><td style="background-color:{accent}; '
        f"background-image:linear-gradient(135deg,{accent} 0%,{accent_dark} 100%); "
        'padding:32px 36px 26px;">'
    )
    sb.append(
        '<div style="font-size:27px; font-weight:800; letter-spacing:0.4px; color:#ffffff; '
        f'line-height:1.1;">{_enc(GROUP_NAME)}</div>'
    )
    sb.append(
        '<div style="width:46px; height:3px; background:rgba(255,255,255,0.55); '
        'border-radius:2px; margin:14px 0 0;"></div>'
    )
    sb.append(
        '<div style="font-size:13px; font-weight:600; color:rgba(255,255,255,0.9); '
        f'margin-top:12px; letter-spacing:0.6px;">{company_names}</div>'
    )
    sb.append("</td></tr>")

    # Sub-bar
    sb.append(f'<tr><td style="background:{accent_dark}; padding:9px 36px;">')
    sb.append(
        '<span style="color:rgba(255,255,255,0.92); font-size:11px; font-weight:600; '
        'letter-spacing:1.6px; text-transform:uppercase;">QMS Document Expiry Alert</span>'
    )
    sb.append("</td></tr>")

    # Body intro
    sb.append('<tr><td style="padding:30px 36px 8px;">')
    sb.append(
        '<div style="font-size:11px; font-weight:700; letter-spacing:1.4px; '
        'text-transform:uppercase; color:#94a3b8; margin:0 0 6px;">Quality Management System</div>'
    )
    sb.append(
        '<div style="font-size:21px; font-weight:700; color:#0f172a; margin:0 0 12px; '
        'line-height:1.25;">Controlled Document Expiry</div>'
    )

    # Count pills
    sb.append("<div>")
    if n_expired:
        sb.append(_pill(f"{n_expired} expired", EXPIRED_COLOR))
    if n_warn:
        sb.append(_pill(f"{n_warn} expiring soon", WARN_COLOR))
    if not n_expired and not n_warn:
        sb.append(_pill("No documents due", ACCENT))
    sb.append("</div>")

    # Summary card
    sb.append(
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="margin:18px 0 0; background:#f8fafc; border:1px solid #e6ebf2; '
        'border-radius:10px;"><tr><td style="padding:16px 18px;">'
    )
    sb.append(
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="font-size:13px;">'
    )
    sb.append(_summary_row("Documents expired", str(n_expired), False))
    sb.append(_summary_row("Documents expiring", str(n_warn), False))
    sb.append(_summary_row("Generated", today_str, True))
    sb.append("</table></td></tr></table>")

    sb.append(
        '<p style="font-size:14px; color:#475569; margin:18px 0 0;">The following QMS controlled '
        "documents are approaching or past their <strong>Document Expiry Date</strong>.</p>"
    )
    sb.append("</td></tr>")

    # Sections (Expired, then each warn window)
    sb.append(_section("Expired", EXPIRED_COLOR, expired))
    for day in warn_days:
        sb.append(_section(f"Expiring in {day} days", WARN_COLOR, warn.get(day, [])))

    # Footer: all three companies, each with its color dot
    sb.append(
        '<tr><td style="padding:22px 36px 26px; background:#fafbfc; border-top:1px solid #eceff4;">'
    )
    sb.append(
        '<div style="font-size:11px; color:#94a3b8; line-height:1.6;">Automated notice from the '
        "Stream-Flo Group QMS Document Expiry Alerts system. Documents without a Document Expiry "
        "Date value are not tracked. Please do not reply to this email.</div>"
    )
    sb.append('<div style="font-size:11px; color:#94a3b8; margin-top:12px;">')
    for i, g in enumerate(GROUP_BRANDS):
        if i > 0:
            sb.append(" &nbsp;&nbsp; ")
        sb.append(
            '<span style="display:inline-block; width:8px; height:8px; border-radius:2px; '
            f'background:{g[1]}; margin-right:6px;"></span>'
        )
        sb.append(f'<span style="color:#64748b;">{_enc(g[2])}</span>')
    sb.append("</div></td></tr>")

    sb.append("</table></td></tr></table></body></html>")
    return "".join(sb)


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
