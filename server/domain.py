"""Versioned packet contract. No weather fact implies a financial-loss estimate."""

import hashlib, json, re
from datetime import datetime, timezone, timedelta


def now():
    return datetime.now(timezone.utc)


def stamp():
    return now().isoformat()


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def fixture(version=2, correction=None):
    p = {
        "id": f"demo-gulf-v{version}",
        "version": version,
        "mode": "demo",
        "storm": "Demo storm",
        "storm_id": "demo-gulf",
        "as_of": "2026-10-10T06:00:00Z",
        "source_version": "demo-advisory-12",
        "title": "The track moved. Has the risk?",
        "summary": "The forecast shifted toward Florida’s west coast. Two watched contracts need a closer look.",
        "conclusion": "A closer review is warranted. Financial impact cannot yet be estimated.",
        "confidence": "Low",
        "confidence_reason": "Insured exposure and prior eligible losses are unavailable.",
        "change": "The latest forecast is east of the previous advisory.",
        "unknowns": ["Insured exposure", "Prior eligible losses"],
        "decision": "Verify exposure and eligible losses before changing the assessment.",
        "method": "Geographic screening only. A track change does not establish insured exposure or bond loss.",
        "bonds": [
            {
                "id": "gulf-wind-demo-a",
                "name": "Gulf Wind Demo A",
                "trigger": "Aggregate indemnity",
                "attachment": None,
                "erosion": None,
                "status": "Needs investigation",
            },
            {
                "id": "coastal-demo-b",
                "name": "Coastal Demo B",
                "trigger": "Occurrence indemnity",
                "attachment": None,
                "erosion": None,
                "status": "Needs investigation",
            },
        ],
        "claims": [
            {
                "id": "C01",
                "text": "The forecast track shifted east.",
                "kind": "fixture observation",
                "source_id": "S01",
                "previous": "Track west of the current forecast",
                "current": "Track closer to Florida’s west coast",
                "limitation": "This does not establish insured exposure.",
            },
            {
                "id": "C02",
                "text": "Financial impact cannot yet be estimated.",
                "kind": "interpretation",
                "source_id": "S02",
                "previous": "Eligible losses unavailable",
                "current": "Eligible losses remain unavailable",
                "limitation": "No estimate of attachment probability or payout is supported.",
            },
        ],
        "sources": [
            {
                "id": "S01",
                "title": "Demo advisory 12",
                "url": None,
                "issued_at": "2026-10-10T06:00:00Z",
                "retrieved_at": "2026-10-10T06:05:00Z",
                "version": "fixture-12",
                "excerpt": "Synthetic track comparison created for interface and workflow testing. It is not an NHC advisory.",
                "rights": "Original synthetic fixture; permitted for redistribution",
            },
            {
                "id": "S02",
                "title": "Demo contract universe",
                "url": None,
                "issued_at": "2026-10-10T06:00:00Z",
                "retrieved_at": "2026-10-10T06:05:00Z",
                "version": "fixture-1",
                "excerpt": "Fictional contracts. Attachment, insured exposure and prior eligible losses are deliberately unknown.",
                "rights": "Original synthetic fixture; permitted for redistribution",
            },
        ],
        "conditions": [
            {
                "id": "K01",
                "text": "Verified exposure outside the forecast corridor would change the screening view.",
                "deadline": "2026-10-11T09:00:00Z",
                "status": "pending",
                "evidence": None,
            }
        ],
        "geometry": {
            "observed": [[-88.8, 23.3], [-87.3, 24.0], [-85.9, 24.6], [-84.7, 25.3]],
            "forecast": [
                [-84.7, 25.3],
                [-83.9, 26.2],
                [-83.1, 27.2],
                [-82.4, 28.2],
                [-81.8, 29.3],
            ],
            "previous": [
                [-84.7, 25.3],
                [-84.4, 26.4],
                [-84.0, 27.5],
                [-83.5, 28.6],
                [-83.0, 29.5],
            ],
            "cone": [
                [-84.7, 25.3],
                [-84.4, 26.4],
                [-84.2, 27.7],
                [-84.0, 29.3],
                [-83.4, 30.0],
                [-81.3, 30.0],
                [-80.8, 29.4],
                [-81.7, 27.7],
                [-83.0, 26.2],
                [-84.7, 25.3],
            ],
        },
        "correction": correction,
    }
    return p


def qc(packet):
    sources = {x["id"] for x in packet.get("sources", [])}
    checks = [
        (
            "structure",
            all(
                packet.get(k)
                for k in [
                    "id",
                    "version",
                    "mode",
                    "conclusion",
                    "decision",
                    "unknowns",
                    "method",
                    "sources",
                    "claims",
                    "conditions",
                ]
            ),
        ),
        (
            "provenance",
            all(c.get("source_id") in sources for c in packet.get("claims", [])),
        ),
        (
            "source_versions",
            all(
                s.get("version")
                and s.get("issued_at")
                and s.get("retrieved_at")
                and s.get("rights")
                for s in packet.get("sources", [])
            ),
        ),
        ("uncertainty", bool(packet.get("confidence_reason"))),
        ("language", not re.search(r"\bmarks\b", json.dumps(packet), re.I)),
        (
            "conditions",
            all(
                c.get("deadline") and c.get("text")
                for c in packet.get("conditions", [])
            ),
        ),
        (
            "unknown_values",
            all(
                b.get("erosion") is None and b.get("attachment") is None
                for b in packet.get("bonds", [])
            ),
        ),
        ("mode", packet.get("mode") in ["demo", "live"]),
    ]
    return {
        "verdict": "PASS" if all(ok for _, ok in checks) else "BLOCKED",
        "input_digest": digest(packet),
        "checked_at": stamp(),
        "validator_version": "2.1.0",
        "checks": [{"name": name, "passed": bool(ok)} for name, ok in checks],
    }
