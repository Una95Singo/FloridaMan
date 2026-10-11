"""Operated import seam for source-pinned packets produced by an external analyst.

This does not run a language model. Imported packets require a declared QC report
and are blocked until the importer records independent review evidence.
"""

import argparse, json
from pathlib import Path
from .app import Factory, Record, put, save_packet, audit
from .domain import now, stamp, qc, digest, review_deadline


def main():
    p = argparse.ArgumentParser(
        description="Import a private, source-pinned review packet. No publication."
    )
    p.add_argument("--packet", required=True)
    p.add_argument("--qc-record", required=True)
    p.add_argument("--expert-subject", required=True)
    p.add_argument("--operator", required=True)
    a = p.parse_args()
    packet = json.loads(Path(a.packet).read_text())
    report = json.loads(Path(a.qc_record).read_text())
    checks = qc(packet)
    if packet.get("mode") != "live":
        raise SystemExit(
            "The operated import requires mode=live. Use the isolated demo for fixtures."
        )
    if checks["verdict"] != "PASS":
        raise SystemExit("Packet failed structural checks: " + json.dumps(checks))
    if (
        report.get("input_digest") != digest(packet)
        or report.get("verdict") != "PASS"
        or not report.get("reviewer")
        or not report.get("evidence_refs")
    ):
        raise SystemExit(
            "Provide an independent PASS report bound to the exact input digest, with reviewer and evidence_refs."
        )
    if not all(
        s.get("url") and s.get("rights") and s.get("excerpt") for s in packet["sources"]
    ):
        raise SystemExit(
            "Live source records require URL, rights basis and captured excerpt."
        )
    with Factory() as db:
        ident = packet["storm_id"]
        existing = db.get(Record, "case:" + ident)
        if existing and existing.data["state"] not in [
            "revision_requested",
            "queued",
            "blocked",
        ]:
            raise SystemExit(
                "The existing case is not open for a replacement. Finish or explicitly reopen it first."
            )
        dg = save_packet(db, packet)
        # A replacement keeps the open cycle's deadline. A new case gets the
        # contract rule: earliest of the next 09:00/21:00 UTC window, first
        # request plus twelve hours, or the packet's decision horizon.
        first = existing.data["first_requested"] if existing else stamp()
        deadline = (
            existing.data["deadline"]
            if existing
            else review_deadline(first, packet.get("decision_horizon")).isoformat()
        )
        put(
            db,
            "case:" + ident,
            "case",
            {
                "id": ident,
                "digest": dg,
                "state": "review_pending",
                "deadline": deadline,
                "first_requested": first,
                "cycle": existing.data["cycle"] if existing else 1,
                "qc": checks,
                "independent_qc": report,
                "assigned_expert": a.expert_subject,
                "approval": None,
                "release_id": None,
            },
        )
        put(
            db,
            "source:" + ident,
            "source",
            {"version": packet["source_version"], "verified_at": stamp()},
        )
        audit(
            db,
            a.operator,
            "operator_import",
            ident,
            {"digest": dg, "reviewer": report["reviewer"]},
        )
        db.commit()
        print(
            json.dumps(
                {"case_id": ident, "packet_digest": dg, "state": "review_pending"}
            )
        )


if __name__ == "__main__":
    main()
