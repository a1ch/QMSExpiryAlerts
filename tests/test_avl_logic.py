"""Offline unit tests for the AVL supplier change diff/classify logic.

Run: python tests/test_avl_logic.py   (no Azure / network needed)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from avl_logic import (  # noqa: E402
    diff_snapshots,
    group_by_type,
    has_changes,
    is_edmonton,
    summarize,
)


def _sup(key, name, approval, scope, company_code="2910", org="Stream-Flo Ind. Ltd.",
         critical="No", approval_matrix=None):
    return {
        "key": key,
        "name": name,
        "approval": approval,
        "scope": sorted(scope),
        "approval_matrix": sorted(approval_matrix or []),
        "critical_scope": critical,
        "company_code": company_code,
        "org": org,
        "web_url": f"https://example/{key}",
    }


def _types(changes):
    return {c["supplier"]["key"]: c["type"] for c in changes}


def test_classifies_each_change_type():
    prev = [
        _sup("A", "HERCULES", "Approved", ["Packing and Seals"]),          # scope will change
        _sup("B", "HASKEL", "Approved", ["Equipment Supply"], "1110", "Master Flo Valve UK"),  # suspend
        _sup("C", "ACME", "Approved", ["Machining"], "1710", "Stream-Flo USA LLC"),  # removed
        _sup("E", "REINST", "Suspended", ["Coating"], "1710", "Stream-Flo USA LLC"),  # reinstate
    ]
    curr = [
        _sup("A", "HERCULES", "Approved", ["Packing and Seals", "Gaskets"]),
        _sup("B", "HASKEL", "Suspended", ["Equipment Supply"], "1110", "Master Flo Valve UK"),
        _sup("D", "NEWCO", "Approved", ["Forgings"], "2910"),               # new
        _sup("E", "REINST", "Approved", ["Coating"], "1710", "Stream-Flo USA LLC"),
    ]
    changes = diff_snapshots(prev, curr)
    t = _types(changes)
    assert t["A"] == "scope", t
    assert t["B"] == "suspended", t
    assert t["C"] == "removed", t
    assert t["D"] == "new", t
    assert t["E"] == "reinstated", t
    assert len(changes) == 5, len(changes)


def test_unchanged_supplier_is_ignored():
    prev = [_sup("A", "HERCULES", "Approved", ["Packing and Seals"])]
    curr = [_sup("A", "HERCULES", "Approved", ["Packing and Seals"])]
    assert diff_snapshots(prev, curr) == []
    assert not has_changes([])


def test_scope_delta_recorded_on_card():
    prev = [_sup("A", "HERCULES", "Approved", ["Packing and Seals"])]
    curr = [_sup("A", "HERCULES", "Approved", ["Gaskets", "Packing and Seals"])]
    (change,) = diff_snapshots(prev, curr)
    assert change["type"] == "scope"
    assert change["deltas"]["scope"]["before"] == ["Packing and Seals"]
    assert change["deltas"]["scope"]["after"] == ["Gaskets", "Packing and Seals"]


def test_first_run_all_new():
    curr = [_sup("A", "HERCULES", "Approved", ["Packing and Seals"])]
    changes = diff_snapshots([], curr)
    assert [c["type"] for c in changes] == ["new"]


def test_edmonton_sorts_first():
    changes = diff_snapshots(
        [],
        [
            _sup("Z", "ZZZ USA", "Approved", ["X"], "1710", "Stream-Flo USA LLC"),
            _sup("A", "AAA EDM", "Approved", ["X"], "2910", "Stream-Flo Ind. Ltd."),
        ],
    )
    grouped = group_by_type(changes, "2910")
    first = grouped["new"][0]["supplier"]
    assert is_edmonton(first, "2910")
    assert first["key"] == "A"


def test_summarize_counts():
    prev = [_sup("B", "HASKEL", "Approved", ["Equipment Supply"], "1110")]
    curr = [_sup("B", "HASKEL", "Suspended", ["Equipment Supply"], "1110")]
    assert summarize(diff_snapshots(prev, curr)) == {"suspended": 1}


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  PASS  {name}")
            passed += 1
    print(f"\n{passed} test(s) passed.")
