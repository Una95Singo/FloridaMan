"""Material-change trigger detection.

Implements the "Triggers" section of the storm-watch agent contract
(``agents-storm-watch-agent.md``) and SPEC TRG-001..TRG-005. All detection
is pure functions over ``(previous_snapshot, current_advisory)`` — no
network, no wall clock (``now_utc`` is a parameter), no side effects.
Import-safe and deterministic: same inputs always give the same fired
trigger IDs.

Trigger IDs map to the spec:
- TRG-001 — storm named (newly discovered), or downgraded/upgraded across
  the TD/TS boundary (the non-numbered-category case).
- TRG-002 — material forecast change: >=1 Saffir-Simpson category move, or
  >=100 km shift in the forecast landfall point (haversine).
- TRG-003 — landfall occurred or the storm dissipated.
- TRG-004 — heartbeat: a check is due (<=12h cadence while watched). The
  heartbeat schedules the *check*; it never causes a draft on its own.
- TRG-005 — silence: no trigger fired. ``evaluate()`` returning ``[]``
  *is* TRG-005: the caller publishes nothing and logs "no trigger,
  no output".

State persistence (``load_state``/``save_state``) is plain JSON keyed by
storm_id (ATCF id, e.g. "AL092026"); a snapshot is the previous
``Advisory`` plus ``last_run_utc``. A missing snapshot means the storm is
newly seen, which is exactly TRG-001's "storm named" case.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

from floridaman.ingest import CATEGORY_ORDER, Advisory

HEARTBEAT_HOURS = 12
TRACK_SHIFT_KM = 100.0
EARTH_RADIUS_KM = 6371.0

#: Storm types NHC uses once a tropical cyclone is no longer tropical.
DISSIPATED_TYPES = {"Post-Tropical Cyclone", "Remnant Low", "Dissipated"}

#: Text patterns indicating the center has come ashore (case-insensitive).
LANDFALL_PATTERNS = (
    "made landfall",
    "landfall has occurred",
    "landfall occurred",
    "moved inland",
    "moving inland",
    "crossed the coast",
)

__all__ = [
    "HEARTBEAT_HOURS",
    "storm_named",
    "upgraded_or_downgraded",
    "intensification_ge_1_category",
    "track_shift_ge_100km",
    "landfall_occurred",
    "dissipated",
    "heartbeat_due",
    "evaluate",
    "load_state",
    "save_state",
    "haversine_km",
]


# ---------------------------------------------------------------------------
# Pure trigger functions
# ---------------------------------------------------------------------------

def storm_named(previous: dict | None, advisory: Advisory) -> bool:
    """TRG-001 (naming half): no previous snapshot — the storm is newly seen."""
    return previous is None


def upgraded_or_downgraded(previous: dict | None, advisory: Advisory) -> bool:
    """TRG-001 (category half): the advisory category label changed.

    Covers TD <-> TS transitions as well as moves in/out of the numbered
    Saffir-Simpson scale. Returns False when either side is unknown.
    """
    if previous is None:
        return False
    prev_cat = previous.get("category")
    cur_cat = advisory.category
    return bool(prev_cat and cur_cat and prev_cat != cur_cat)


def intensification_ge_1_category(previous: dict | None, advisory: Advisory) -> bool:
    """TRG-002 (intensity half): |category-order change| >= 1.

    Uses the TD=0, TS=1, C1..C5=2..6 order scale, so TS->C1 and C2->C3
    both count. Unknown categories on either side -> False (no trigger
    on missing data; silence is correct).
    """
    if previous is None:
        return False
    prev_cat = previous.get("category")
    cur_cat = advisory.category
    if prev_cat not in CATEGORY_ORDER or cur_cat not in CATEGORY_ORDER:
        return False
    return abs(CATEGORY_ORDER[cur_cat] - CATEGORY_ORDER[prev_cat]) >= 1


def track_shift_ge_100km(previous: dict | None, advisory: Advisory) -> bool:
    """TRG-002 (track half): forecast landfall point moved >= 100 km.

    Compares the first forecast position flagged INLAND in the NHC
    discussion (haversine). If either side's landfall point is unknown,
    returns False — a parse miss must not fire a trigger.
    """
    if previous is None:
        return False
    plat, plon = previous.get("forecast_landfall_lat"), previous.get("forecast_landfall_lon")
    clat, clon = advisory.forecast_landfall_lat, advisory.forecast_landfall_lon
    if None in (plat, plon, clat, clon):
        return False
    return haversine_km(plat, plon, clat, clon) >= TRACK_SHIFT_KM


def landfall_occurred(previous: dict | None, advisory: Advisory) -> bool:
    """TRG-003 (landfall half): advisory text says the center came ashore.

    Heuristic over the NHC headline and the lead of the discussion
    section. Fires only on the transition: requires a previous snapshot
    in which landfall had *not* already fired, so repeated post-landfall
    advisories do not re-fire. Callers track that by removing TRG-003
    from repeat evaluation once closed (see run.py).
    """
    text = f"{advisory.headline} {advisory.discussion_lead}".lower()
    return any(p in text for p in LANDFALL_PATTERNS)


def dissipated(previous: dict | None, advisory: Advisory) -> bool:
    """TRG-003 (dissipation half): NHC type is post-tropical/remnant.

    Uses the storm-type field from the RSS ``<nhc:Cyclone>`` summary.
    Fires only on transition (previous type was tropical).
    """
    cur = (advisory.storm_type or "").strip()
    if cur not in DISSIPATED_TYPES:
        return False
    if previous is None:
        return True  # discovered already dissipated: still a closing event
    prev_type = (previous.get("storm_type") or "").strip()
    return prev_type not in DISSIPATED_TYPES


def heartbeat_due(last_run_utc: str | None, now_utc: datetime | None = None) -> bool:
    """TRG-004: True if >= 12h since the last check (or never checked)."""
    if last_run_utc is None:
        return True
    now = now_utc or datetime.now(timezone.utc)
    try:
        last = datetime.fromisoformat(last_run_utc)
    except ValueError:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return (now - last) >= timedelta(hours=HEARTBEAT_HOURS)


def evaluate(previous: dict | None, advisory: Advisory,
             last_run_utc: str | None) -> list[str]:
    """Evaluate all event triggers. Returns fired trigger IDs, in order.

    ``[]`` means silence (TRG-005): the caller must publish nothing and
    record "no trigger, no output". TRG-003 (landfall/dissipation) is
    checked first so a closing event dominates the run's framing.
    """
    fired: list[str] = []
    if previous is not None and previous.get("closed"):
        return fired  # watch closed: nothing fires afterwards
    if landfall_occurred(previous, advisory) or dissipated(previous, advisory):
        fired.append("TRG-003")
    if storm_named(previous, advisory):
        fired.append("TRG-001")
    elif upgraded_or_downgraded(previous, advisory):
        fired.append("TRG-001")
    if intensification_ge_1_category(previous, advisory) or track_shift_ge_100km(previous, advisory):
        if "TRG-002" not in fired:
            fired.append("TRG-002")
    _ = last_run_utc  # heartbeat (TRG-004) gates the *check*, not the draft
    return fired


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two lat/lon points."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# State persistence (JSON)
# ---------------------------------------------------------------------------

def load_state(state_dir: str | Path) -> dict:
    """Load the state file; {} if missing or unreadable (never raises)."""
    path = Path(state_dir) / "state.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state_dir: str | Path, state: dict) -> None:
    """Persist state as JSON. Creates the state dir if needed."""
    path = Path(state_dir) / "state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
