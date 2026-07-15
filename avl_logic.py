"""Pure functions that diff two AVL snapshots and classify supplier changes.

No Azure or network calls here so the logic is unit-testable offline.

A change is bucketed by a single *primary* type for section placement, but the
card still carries every field delta (approval and scope) so nothing is hidden:

    suspended   - ApprovalRating moved to "Suspended"
    reinstated  - ApprovalRating moved to "Approved" (from a non-approved state)
    status      - ApprovalRating changed between other states
    scope       - ScopeMatrix / CriticalScopeText changed (approval unchanged)
    new         - a QMS supplier that was not in the previous snapshot
    removed     - a supplier that was in the previous snapshot but is gone
                  (deleted, or QMSSupplier flag turned off)
"""

# Section order in the digest.
CHANGE_ORDER = ["suspended", "reinstated", "status", "scope", "new", "removed"]

CHANGE_LABELS = {
    "suspended": "Suspended",
    "reinstated": "Approved / Reinstated",
    "status": "Approval status changed",
    "scope": "Scope changed",
    "new": "New QMS supplier",
    "removed": "Removed from QMS list",
}


def _by_key(records):
    return {r["key"]: r for r in records if r.get("key")}


def _approval_bucket(before, after):
    """Classify an ApprovalRating transition; None if it did not change."""
    if (before or "") == (after or ""):
        return None
    if (after or "").lower() == "suspended":
        return "suspended"
    if (after or "").lower() == "approved":
        return "reinstated"
    return "status"


def _scope_changed(prev, curr):
    return (
        prev.get("scope") != curr.get("scope")
        or prev.get("critical_scope") != curr.get("critical_scope")
        or prev.get("approval_matrix") != curr.get("approval_matrix")
    )


def _field_deltas(prev, curr):
    """Return the human-facing before/after deltas present on a change card."""
    deltas = {}
    if (prev.get("approval") or "") != (curr.get("approval") or ""):
        deltas["approval"] = {
            "before": prev.get("approval") or "(none)",
            "after": curr.get("approval") or "(none)",
        }
    if prev.get("scope") != curr.get("scope"):
        deltas["scope"] = {
            "before": prev.get("scope") or [],
            "after": curr.get("scope") or [],
        }
    if prev.get("critical_scope") != curr.get("critical_scope"):
        deltas["critical_scope"] = {
            "before": prev.get("critical_scope") or "(none)",
            "after": curr.get("critical_scope") or "(none)",
        }
    if prev.get("approval_matrix") != curr.get("approval_matrix"):
        deltas["approval_matrix"] = {
            "before": prev.get("approval_matrix") or [],
            "after": curr.get("approval_matrix") or [],
        }
    return deltas


def diff_snapshots(previous, current):
    """Compare two lists of supplier records; return a list of change dicts.

    Each change: {type, supplier, deltas}. ``supplier`` is the current record
    (or the previous one for removals).
    """
    prev = _by_key(previous or [])
    curr = _by_key(current or [])
    changes = []

    for key, curr_rec in curr.items():
        prev_rec = prev.get(key)
        if prev_rec is None:
            changes.append({"type": "new", "supplier": curr_rec, "deltas": {}})
            continue

        approval_bucket = _approval_bucket(
            prev_rec.get("approval"), curr_rec.get("approval")
        )
        scope_change = _scope_changed(prev_rec, curr_rec)
        if not approval_bucket and not scope_change:
            continue  # unchanged

        change_type = approval_bucket or "scope"
        changes.append(
            {
                "type": change_type,
                "supplier": curr_rec,
                "deltas": _field_deltas(prev_rec, curr_rec),
            }
        )

    for key, prev_rec in prev.items():
        if key not in curr:
            changes.append({"type": "removed", "supplier": prev_rec, "deltas": {}})

    return changes


def is_edmonton(supplier, edmonton_company_code):
    return str(supplier.get("company_code") or "").strip() == str(edmonton_company_code)


def group_by_type(changes, edmonton_company_code):
    """Return an ordered {type: [changes]} map, Edmonton suppliers first.

    Within each section, SFI Edmonton (matching company code) sorts to the top,
    then by organization and name.
    """

    def sort_key(chg):
        s = chg["supplier"]
        return (
            not is_edmonton(s, edmonton_company_code),  # Edmonton (False) first
            s.get("org") or "",
            s.get("name") or "",
        )

    grouped = {}
    for ctype in CHANGE_ORDER:
        rows = sorted(
            (c for c in changes if c["type"] == ctype), key=sort_key
        )
        if rows:
            grouped[ctype] = rows
    return grouped


def summarize(changes):
    """Return {type: count} for the changes present (used in subject/pills)."""
    counts = {}
    for c in changes:
        counts[c["type"]] = counts.get(c["type"], 0) + 1
    return counts


def has_changes(changes):
    return bool(changes)
