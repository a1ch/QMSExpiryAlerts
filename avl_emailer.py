"""Builds the AVL QMS-supplier change digest as a Graph sendMail payload.

Reuses the Stream-Flo Group digest styling from ``emailer.py`` (navy header,
tri-color company ribbon, count pills, left-border cards, three-company footer)
so the supplier digest is visually consistent with the expiry alerts.
"""
from datetime import date

from avl_logic import (
    CHANGE_LABELS,
    CHANGE_ORDER,
    group_by_type,
    is_edmonton,
    summarize,
)
from emailer import (
    ACCENT,
    GROUP_BRANDS,
    GROUP_NAME,
    _darken,
    _enc,
    _pill,
    _tint,
)

# Color per change type (matches the urgency palette family).
TYPE_COLORS = {
    "suspended": "#b00020",   # red
    "reinstated": "#0d7a4a",  # green
    "status": "#c77700",      # amber
    "scope": "#0066b3",       # blue
    "new": "#003366",         # navy
    "removed": "#64748b",     # slate
}

EDMONTON_BADGE = "#0d7a7a"  # teal - SFI Edmonton marker


def _chips(values, color):
    if not values:
        return '<span style="color:#94a3b8;">(none)</span>'
    out = []
    for v in values:
        soft = _tint(color, 0.9)
        out.append(
            f'<span style="display:inline-block; background:{soft}; color:{color}; '
            'font-size:11.5px; font-weight:600; padding:3px 9px; border-radius:6px; '
            f'margin:0 5px 5px 0;">{_enc(v)}</span>'
        )
    return "".join(out)


def _delta_row(label, before_html, after_html):
    return (
        '<div style="font-size:12.5px; color:#475569; margin-top:8px;">'
        f'<span style="color:#64748b; font-weight:700;">{_enc(label)}</span><br/>'
        f'<span style="color:#94a3b8;">{before_html}</span>'
        '<span style="color:#94a3b8; padding:0 8px;">&rarr;</span>'
        f'<span style="color:#0f172a; font-weight:600;">{after_html}</span>'
        "</div>"
    )


def _deltas_html(deltas):
    rows = []
    if "approval" in deltas:
        d = deltas["approval"]
        rows.append(
            _delta_row("Approval", _enc(d["before"]), _enc(d["after"]))
        )
    if "scope" in deltas:
        d = deltas["scope"]
        rows.append(
            _delta_row(
                "Scope",
                _chips(d["before"], "#94a3b8"),
                _chips(d["after"], "#0066b3"),
            )
        )
    if "critical_scope" in deltas:
        d = deltas["critical_scope"]
        rows.append(
            _delta_row("Critical scope", _enc(d["before"]), _enc(d["after"]))
        )
    if "approval_matrix" in deltas:
        d = deltas["approval_matrix"]
        rows.append(
            _delta_row(
                "Approval basis",
                _chips(d["before"], "#94a3b8"),
                _chips(d["after"], "#0066b3"),
            )
        )
    return "".join(rows)


def _supplier_card(change, edmonton_company_code):
    s = change["supplier"]
    color = TYPE_COLORS.get(change["type"], ACCENT)
    name = _enc(s.get("name") or "(unnamed supplier)")
    url = _enc(s.get("web_url") or "#")
    org = _enc(s.get("org") or "")
    loc_bits = [b for b in [s.get("city"), s.get("region"), s.get("country")] if b]
    loc = _enc(", ".join(loc_bits))
    eyebrow = org or "Supplier"

    edm_badge = ""
    if is_edmonton(s, edmonton_company_code):
        edm_badge = (
            f'<span style="display:inline-block; background:{_tint(EDMONTON_BADGE,0.86)}; '
            f'color:{EDMONTON_BADGE}; font-size:10.5px; font-weight:800; letter-spacing:0.4px; '
            'padding:2px 8px; border-radius:999px; margin-left:8px; vertical-align:middle;">'
            "SFI EDMONTON</span>"
        )

    detail = ""
    if s.get("notes_quality"):
        detail = (
            '<div style="font-size:12px; color:#64748b; margin-top:8px;">'
            f'<span style="font-weight:600;">Quality notes</span> {_enc(s["notes_quality"])}</div>'
        )
    auditor = ""
    if s.get("auditor"):
        auditor = (
            '<div style="font-size:12px; color:#94a3b8; margin-top:6px;">'
            f'Auditor: {_enc(s["auditor"])}</div>'
        )

    deltas_html = _deltas_html(change.get("deltas") or {})

    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="margin:0 0 10px; background:#ffffff; border:1px solid #eceff4; '
        f'border-left:4px solid {color}; border-radius:10px;"><tr>'
        '<td style="padding:14px 16px;">'
        f'<div style="font-size:11px; font-weight:700; color:{color}; letter-spacing:0.5px; '
        f'margin:0 0 4px;">{eyebrow}</div>'
        f'<a href="{url}" style="font-size:15px; font-weight:600; color:#0f172a; '
        f'text-decoration:none;">{name}</a>{edm_badge}'
        + (f'<div style="font-size:12px; color:#94a3b8; margin-top:4px;">{loc}</div>' if loc else "")
        + deltas_html
        + detail
        + auditor
        + "</td></tr></table>"
    )


def _section(ctype, changes, edmonton_company_code):
    if not changes:
        return ""
    color = TYPE_COLORS.get(ctype, ACCENT)
    title = CHANGE_LABELS.get(ctype, ctype.title())
    cards = "".join(_supplier_card(c, edmonton_company_code) for c in changes)
    return (
        '<tr><td style="padding:20px 36px 4px;">'
        '<div style="font-size:11px; font-weight:700; letter-spacing:1.4px; '
        'text-transform:uppercase; border-top:1px solid #eceff4; padding-top:18px;">'
        f'<span style="color:{color};">{_enc(title)}</span> '
        f'<span style="color:#94a3b8;">({len(changes)})</span></div></td></tr>'
        f'<tr><td style="padding:8px 36px 8px;">{cards}</td></tr>'
    )


def build_subject(changes):
    counts = summarize(changes)
    parts = []
    for ctype in CHANGE_ORDER:
        if counts.get(ctype):
            parts.append(f"{counts[ctype]} {CHANGE_LABELS[ctype].lower()}")
    summary = "; ".join(parts) if parts else "no changes"
    return f"[AVL] QMS supplier changes - {summary}"


def build_body(changes, edmonton_company_code):
    accent = ACCENT
    accent_dark = _darken(accent, 0.72)
    grouped = group_by_type(changes, edmonton_company_code)
    counts = summarize(changes)
    company_names = "  &middot;  ".join(_enc(g[0]) for g in GROUP_BRANDS)
    today_str = date.today().strftime("%b %d, %Y")
    total = len(changes)
    edm_total = sum(
        1 for c in changes if is_edmonton(c["supplier"], edmonton_company_code)
    )

    sb = []
    sb.append('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/>')
    sb.append('<meta name="viewport" content="width=device-width, initial-scale=1"/>')
    sb.append('<meta name="color-scheme" content="light only"/>')
    sb.append("<title>QMS Supplier Change Digest</title></head>")
    sb.append(
        '<body style="margin:0; padding:0; width:100%; background:#eef2f7; '
        "font-family:'Segoe UI',Arial,sans-serif; font-size:15px; line-height:1.5; "
        'color:#1e293b; -webkit-font-smoothing:antialiased;">'
    )
    sb.append(
        '<div style="display:none; max-height:0; overflow:hidden; opacity:0; mso-hide:all;">'
        f"QMS supplier changes this week &mdash; {total} update(s), {edm_total} Edmonton</div>"
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

    # Tri-color ribbon
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
        'letter-spacing:1.6px; text-transform:uppercase;">QMS Supplier Change Digest</span>'
    )
    sb.append("</td></tr>")

    # Intro
    sb.append('<tr><td style="padding:30px 36px 8px;">')
    sb.append(
        '<div style="font-size:11px; font-weight:700; letter-spacing:1.4px; '
        'text-transform:uppercase; color:#94a3b8; margin:0 0 6px;">Approved Vendor List</div>'
    )
    sb.append(
        '<div style="font-size:21px; font-weight:700; color:#0f172a; margin:0 0 12px; '
        'line-height:1.25;">QMS Supplier Changes This Week</div>'
    )

    # Count pills
    sb.append("<div>")
    if total:
        for ctype in CHANGE_ORDER:
            if counts.get(ctype):
                sb.append(_pill(f"{counts[ctype]} {CHANGE_LABELS[ctype].lower()}", TYPE_COLORS[ctype]))
    else:
        sb.append(_pill("No changes this week", ACCENT))
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
    sb.append(
        '<tr><td style="padding:0 0 8px; width:180px; color:#64748b; font-weight:600;">'
        f'Total changes</td><td style="padding:0 0 8px; color:#1e293b;">{total}</td></tr>'
    )
    sb.append(
        '<tr><td style="padding:0 0 8px; color:#64748b; font-weight:600;">'
        f'SFI Edmonton changes</td><td style="padding:0 0 8px; color:#1e293b;">{edm_total}</td></tr>'
    )
    sb.append(
        '<tr><td style="padding:0; color:#64748b; font-weight:600;">'
        f'Generated</td><td style="padding:0; color:#1e293b;">{today_str}</td></tr>'
    )
    sb.append("</table></td></tr></table>")

    sb.append(
        '<p style="font-size:14px; color:#475569; margin:18px 0 0;">The following QMS suppliers '
        "changed <strong>approval status or scope</strong> since last week. SFI Edmonton "
        "suppliers are listed first in each section.</p>"
    )
    sb.append("</td></tr>")

    # Sections
    for ctype in CHANGE_ORDER:
        sb.append(_section(ctype, grouped.get(ctype, []), edmonton_company_code))

    # Footer
    sb.append(
        '<tr><td style="padding:22px 36px 26px; background:#fafbfc; border-top:1px solid #eceff4;">'
    )
    sb.append(
        '<div style="font-size:11px; color:#94a3b8; line-height:1.6;">Automated notice from the '
        "Stream-Flo Group QMS Supplier Change Digest, comparing the Corporate AVL week over week. "
        "Only QMS suppliers with an approval-status or scope change are listed. "
        "Please do not reply to this email.</div>"
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


def build_message(changes, recipients, edmonton_company_code, save_to_sent=False):
    return {
        "message": {
            "subject": build_subject(changes),
            "body": {"contentType": "HTML", "content": build_body(changes, edmonton_company_code)},
            "toRecipients": [
                {"emailAddress": {"address": addr}} for addr in recipients
            ],
        },
        "saveToSentItems": save_to_sent,
    }
