"""Render a sample AVL supplier-change digest to HTML (no Azure / no send).

Uses realistic mock data modeled on the real CorpAVLV2 rows so Christine and
Shawn can see the email layout before anything is deployed.

Run: python scripts/preview_avl_digest.py
Writes: preview_avl_digest.html in the project root.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from avl_emailer import build_body, build_subject  # noqa: E402
from avl_logic import diff_snapshots  # noqa: E402

EDMONTON = "2910"


def sup(key, name, approval, scope, company_code, org, city="", region="",
        critical="No", approval_matrix=None, notes="", auditor="Abbey Raikles"):
    return {
        "key": key, "name": name, "approval": approval, "scope": sorted(scope),
        "approval_matrix": sorted(approval_matrix or []), "critical_scope": critical,
        "company_code": company_code, "org": org, "city": city, "region": region,
        "country": "CA", "auditor": auditor, "notes_quality": notes,
        "web_url": "https://streamflogroup.sharepoint.com/sites/OFForms/CorpAVL",
    }


# Last week's snapshot
previous = [
    sup("17101011788", "HERCULES SEALING PRODUCTS CANA", "Approved", ["Packing and Seals"],
        "2910", "Stream-Flo Ind. Ltd.", "EDMONTON", "AB",
        approval_matrix=["PO Compliance"], notes="ISO 9001 - 0122322"),
    sup("11101003380", "HASKEL EUROPE LTD", "Approved", ["Equipment Supply"],
        "1110", "Master Flo Valve UK", "SUNDERLAND", "", ),
    sup("29101099001", "PRECISION HEAT TREAT LTD", "Approved", ["Heat Treatment"],
        "2910", "Stream-Flo Ind. Ltd.", "NISKU", "AB"),
    sup("17101044555", "GULF COAST MACHINING", "Suspended", ["Machining"],
        "1710", "Stream-Flo USA LLC", "HOUSTON", "TX"),
]

# This week's snapshot
current = [
    # scope expanded (Edmonton)
    sup("17101011788", "HERCULES SEALING PRODUCTS CANA", "Approved",
        ["Packing and Seals", "Gaskets"], "2910", "Stream-Flo Ind. Ltd.",
        "EDMONTON", "AB", approval_matrix=["PO Compliance"], notes="ISO 9001 - 0122322"),
    # suspended (UK)
    sup("11101003380", "HASKEL EUROPE LTD", "Suspended", ["Equipment Supply"],
        "1110", "Master Flo Valve UK", "SUNDERLAND", ""),
    # unchanged (Edmonton) - should NOT appear
    sup("29101099001", "PRECISION HEAT TREAT LTD", "Approved", ["Heat Treatment"],
        "2910", "Stream-Flo Ind. Ltd.", "NISKU", "AB"),
    # reinstated (USA)
    sup("17101044555", "GULF COAST MACHINING", "Approved", ["Machining"],
        "1710", "Stream-Flo USA LLC", "HOUSTON", "TX"),
    # brand new QMS supplier (Edmonton)
    sup("29101099777", "APEX FORGINGS INC", "Approved", ["Forgings", "NDE"],
        "2910", "Stream-Flo Ind. Ltd.", "EDMONTON", "AB",
        approval_matrix=["Audit"], notes="API 6A licensed"),
]

changes = diff_snapshots(previous, current)
html = build_body(changes, EDMONTON)
out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "preview_avl_digest.html")
with open(out, "w", encoding="utf-8") as fh:
    fh.write(html)

print("Subject:", build_subject(changes))
print(f"{len(changes)} change(s) rendered.")
print("Wrote", out)
