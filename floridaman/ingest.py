"""NHC public advisory ingest.

Implements the "Inputs" section of the storm-watch agent contract
(``agents-storm-watch-agent.md``) and feeds SPEC TRC-003 (every published
hypothesis cites the NHC advisory number and timestamp): this module
discovers active Atlantic storms from the NHC public RSS feed and parses
the public advisory text products into a normalized :class:`Advisory`.

NHC id scheme (documented, verified live 2026-10-09):
- ATCF id: basin code + two-digit storm number + year, e.g. ``AL092026``
  (Atlantic, storm 09, 2026). This is the canonical storm key.
- Wallet: NHC's internal short code, e.g. ``AT4``. The public advisory
  text products are addressed by wallet: ``MIATCP<wallet>.shtml`` is the
  public advisory, ``MIATCD<wallet>.shtml`` the forecast discussion
  (``https://www.nhc.noaa.gov/text/MIATCPAT4.shtml``).
- All of this is discovered from the RSS feed at
  ``https://www.nhc.noaa.gov/index-at.xml`` — never hardcoded.

Defensive parsing rule: NHC product formats drift. Every regex may miss;
a miss never raises — it appends a note to ``Advisory.parse_notes`` and
leaves the field ``None`` (or falls back to the RSS ``<nhc:Cyclone>``
structured summary). The ``fetch_text`` seam exists so tests can inject
fixture text instead of hitting the network.
"""

from __future__ import annotations

import re
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

RSS_URL = "https://www.nhc.noaa.gov/index-at.xml"
TEXT_BASE = "https://www.nhc.noaa.gov/text"

# ---------------------------------------------------------------------------
# Advisory dataclass
# ---------------------------------------------------------------------------

#: Saffir-Simpson category from sustained winds in mph. "TS"/"TD" are not
#: numbered categories; the numeric scale below is for trigger comparisons.
def category_from_mph(mph: float | None) -> str | None:
    """Saffir-Simpson category label from sustained wind speed (mph)."""
    if mph is None:
        return None
    if mph < 39:
        return "TD"
    if mph < 74:
        return "TS"
    if mph <= 95:
        return "C1"
    if mph <= 110:
        return "C2"
    if mph <= 129:
        return "C3"
    if mph <= 156:
        return "C4"
    return "C5"


#: Ordered scale used by triggers.py: TD=0, TS=1, C1..C5=2..6.
CATEGORY_ORDER = {"TD": 0, "TS": 1, "C1": 2, "C2": 3, "C3": 4, "C4": 5, "C5": 6}


@dataclass
class Advisory:
    """Normalized NHC advisory.

    Fields exactly per the pipeline contract, plus documented extras
    (``storm_type``, ``forecast_landfall_lat/lon``, ``parse_notes``) needed
    by triggers.py and draft.py.
    """

    storm_id: str | None = None            # ATCF id, e.g. "AL092026"
    name: str | None = None                # e.g. "Isaias"
    advisory_number: str | None = None     # e.g. "13A"
    issued_utc: str | None = None          # ISO-8601 UTC, e.g. "2026-10-09T23:49:43+00:00"
    lat: float | None = None
    lon: float | None = None               # degrees east, negative = west
    max_winds_mph: float | None = None
    min_pressure_mb: float | None = None
    category: str | None = None            # Saffir-Simpson label from mph
    movement_dir_deg: int | None = None
    movement_mph: float | None = None
    watches_warnings: str = ""             # raw text block
    forecast_peak_mph: float | None = None # max forecast wind from discussion
    landfall_window_text: str = ""         # raw sentence(s) re landfall
    source_url: str = ""
    # Extras:
    storm_type: str | None = None          # e.g. "Hurricane", "Tropical Storm"
    forecast_landfall_lat: float | None = None  # first forecast pos flagged INLAND
    forecast_landfall_lon: float | None = None
    headline: str = ""                     # raw headline lines (landfall detection)
    discussion_lead: str = ""              # raw lead of DISCUSSION AND OUTLOOK
    parse_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Advisory":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})


# ---------------------------------------------------------------------------
# fetch_text seam (tests inject fixtures here)
# ---------------------------------------------------------------------------

def fetch_text(url: str, timeout: int = 30) -> str | None:
    """Fetch a URL as text. Returns None on any network/HTTP failure.

    This is the single network seam in the package: tests monkeypatch or
    rebind this function to inject fixture text instead of live HTTP.
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "FloridaMan/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# RSS discovery
# ---------------------------------------------------------------------------

def discover_storms(rss_url: str = RSS_URL) -> list[dict]:
    """Discover active Atlantic storms from the NHC RSS feed.

    Returns a list of dicts with keys: name, atcf (storm_id), wallet,
    storm_type, lat, lon, max_winds_mph, min_pressure_mb, movement_text,
    headline, link (advisory URL). Never raises on malformed XML: returns
    whatever parsed cleanly, [] if the fetch failed.
    """
    storms: list[dict] = []
    text = fetch_text(rss_url)
    if not text:
        return storms
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return storms
    ns = {"nhc": "https://www.nhc.noaa.gov"}
    for item in root.iter("item"):
        cyc = item.find("nhc:Cyclone", ns)
        if cyc is None:
            continue

        def _get(tag: str) -> str:
            el = cyc.find(f"nhc:{tag}", ns)
            return (el.text or "").strip() if el is not None else ""

        wallet = _get("wallet")
        center = _get("center")
        lat, lon = _parse_latlon(center)
        movement = _get("movement")
        wind = _parse_number(_get("wind"))
        pressure = _parse_number(_get("pressure"))
        link_el = item.find("link")
        storms.append(
            {
                "name": _get("name"),
                "atcf": _get("atcf"),
                "wallet": wallet,
                "storm_type": _get("type"),
                "lat": lat,
                "lon": lon,
                "max_winds_mph": wind,
                "min_pressure_mb": pressure,
                "movement_text": movement,
                "headline": _get("headline"),
                "link": (link_el.text or "").strip() if link_el is not None else "",
            }
        )
    return storms


def find_storm(storms: list[dict], storm: str) -> dict | None:
    """Match a user-supplied storm key against discovered storms.

    Accepts, case-insensitively: storm name ("isaias"), ATCF id
    ("AL092026"), or wallet ("AT4"). Returns the storm dict or None.
    """
    key = storm.strip().lower()
    for s in storms:
        if key in {str(s.get("name", "")).lower(), str(s.get("atcf", "")).lower(),
                   str(s.get("wallet", "")).lower()}:
            return s
    # prefix fallback on name ("isai" -> "isaias") only if unambiguous
    matches = [s for s in storms if str(s.get("name", "")).lower().startswith(key)]
    return matches[0] if len(matches) == 1 else None


# ---------------------------------------------------------------------------
# Public advisory parsing
# ---------------------------------------------------------------------------

def fetch_advisory(storm: dict) -> Advisory:
    """Fetch and parse the public advisory for a discovered storm.

    ``storm`` is one dict from :func:`discover_storms`. Uses the wallet to
    address ``MIATCP<wallet>.shtml`` (public advisory) and
    ``MIATCD<wallet>.shtml`` (discussion, for forecast peak + landfall
    point). RSS values seed the advisory; text-product values override
    them when parseable. Parse misses are recorded in ``parse_notes``.
    """
    adv = Advisory()
    adv.storm_id = storm.get("atcf") or None
    adv.name = storm.get("name") or None
    adv.storm_type = storm.get("storm_type") or None
    adv.lat = storm.get("lat")
    adv.lon = storm.get("lon")
    adv.max_winds_mph = storm.get("max_winds_mph")
    adv.min_pressure_mb = storm.get("min_pressure_mb")
    adv.headline = storm.get("headline", "")
    adv.source_url = storm.get("link", "")

    mov = _parse_movement_text(storm.get("movement_text", ""))
    if mov:
        adv.movement_dir_deg, adv.movement_mph = mov

    wallet = (storm.get("wallet") or "").strip()
    if not wallet:
        adv.parse_notes.append("no wallet in RSS; skipping text-product fetch")
    else:
        pub_url = f"{TEXT_BASE}/MIATCP{wallet}.shtml"
        pub_text = fetch_text(pub_url)
        if pub_text:
            _parse_public_advisory(pub_text, adv)
            adv.source_url = pub_url
        else:
            adv.parse_notes.append(f"public advisory fetch failed: {pub_url}")

        disc_url = f"{TEXT_BASE}/MIATCD{wallet}.shtml"
        disc_text = fetch_text(disc_url)
        if disc_text:
            _parse_discussion(disc_text, adv)
        else:
            adv.parse_notes.append(f"discussion fetch failed: {disc_url}")

    if adv.max_winds_mph is not None:
        adv.category = category_from_mph(adv.max_winds_mph)
    else:
        adv.parse_notes.append("max winds unknown; category unset")
    return adv


def _parse_public_advisory(text: str, adv: Advisory) -> None:
    """Fill Advisory fields from the MIATCP public advisory text."""
    flat = _strip_html(text)

    m = re.search(r"Advisory Number\s+([0-9]+[A-Z]?)", flat, re.I)
    if m:
        adv.advisory_number = m.group(1).upper()
    else:
        adv.parse_notes.append("advisory number not found")

    m = re.search(
        r"(\d{1,2})(?::(\d{2}))?\s*(AM|PM)\s+([A-Z]{2,4})\s+"
        r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
        r"(\d{1,2})\s+(\d{4})",
        flat,
    )
    if m:
        adv.issued_utc = _to_utc_iso(m)
    else:
        adv.parse_notes.append("issued timestamp not parsed")

    m = re.search(r"LOCATION\.*\s*(\d+\.\d+)\s*N\s+(\d+\.\d+)\s*W", flat, re.I)
    if m:
        adv.lat, adv.lon = float(m.group(1)), -float(m.group(2))
    else:
        adv.parse_notes.append("position not parsed from public advisory")

    m = re.search(r"MAXIMUM SUSTAINED WINDS\.*\s*(\d+)\s*MPH", flat, re.I)
    if m:
        adv.max_winds_mph = float(m.group(1))
    else:
        adv.parse_notes.append("max winds not parsed from public advisory")

    m = re.search(r"MINIMUM CENTRAL PRESSURE\.*\s*(\d+)\s*MB", flat, re.I)
    if m:
        adv.min_pressure_mb = float(m.group(1))
    else:
        adv.parse_notes.append("min pressure not parsed from public advisory")

    m = re.search(r"PRESENT MOVEMENT\.*\s*[A-Z ]*?(\d+)\s*DEGREES?\s*AT\s*(\d+)\s*MPH", flat, re.I)
    if m:
        adv.movement_dir_deg, adv.movement_mph = int(m.group(1)), float(m.group(2))
    else:
        adv.parse_notes.append("movement not parsed from public advisory")

    m = re.search(r"WATCHES AND WARNINGS\s*-+\s*(.*?)\s*DISCUSSION AND OUTLOOK", flat, re.I | re.S)
    if m:
        adv.watches_warnings = _clean_block(m.group(1))
    else:
        adv.parse_notes.append("watches/warnings block not parsed")

    m = re.search(r"DISCUSSION AND OUTLOOK\s*-+\s*(.*?)\s*HAZARDS AFFECTING LAND", flat, re.I | re.S)
    if m:
        lead = _clean_block(m.group(1))
        adv.discussion_lead = lead[:1200]
        adv.landfall_window_text = _landfall_sentence(lead)
    else:
        adv.parse_notes.append("discussion section not parsed")

    m = re.search(r"\.\.\.(.*?)\.\.\.", flat, re.S)
    if m and not adv.headline:
        adv.headline = _clean_block(m.group(1))


def _parse_discussion(text: str, adv: Advisory) -> None:
    """Fill forecast peak + first INLAND forecast position from MIATCD."""
    flat = _strip_html(text)
    m = re.search(r"FORECAST POSITIONS AND MAX WINDS\s*(.*?)\$\$", flat, re.I | re.S)
    if not m:
        adv.parse_notes.append("forecast table not found in discussion")
        return
    table = m.group(1)
    peaks: list[float] = []
    for line in table.splitlines():
        # e.g. " 12H  10/0600Z 31.2N  86.8W   75 KT  85 MPH...INLAND"
        mm = re.search(r"(\d+\.\d+)N\s+(\d+\.\d+)W\s+(\d+)\s*KT\s+(\d+)\s*MPH", line, re.I)
        if not mm:
            continue
        lat, lon = float(mm.group(1)), -float(mm.group(2))
        mph = float(mm.group(4))
        peaks.append(mph)
        if "INLAND" in line.upper() and adv.forecast_landfall_lat is None:
            adv.forecast_landfall_lat, adv.forecast_landfall_lon = lat, lon
    if peaks:
        adv.forecast_peak_mph = max(peaks)
    else:
        adv.parse_notes.append("no forecast wind rows parsed from discussion")


# ---------------------------------------------------------------------------
# Small parsing helpers (all defensive: return None/""/[] on miss)
# ---------------------------------------------------------------------------

_TZ_OFFSETS = {
    "AST": -4, "ADT": -3, "EDT": -4, "EST": -5, "CDT": -5, "CST": -6,
    "MDT": -6, "MST": -7, "PDT": -7, "PST": -8, "HST": -10, "AKDT": -8,
    "AKST": -9, "UTC": 0, "GMT": 0,
}
_MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}


def _to_utc_iso(m: re.Match) -> str:
    hour, minute, ampm, tz, _dow, mon, day, year = m.groups()
    hour = int(hour)
    if ampm == "PM" and hour != 12:
        hour += 12
    if ampm == "AM" and hour == 12:
        hour = 0
    offset = _TZ_OFFSETS.get(tz.upper())
    dt = datetime(int(year), _MONTHS[mon], int(day), hour, int(minute or 0))
    if offset is None:
        return dt.isoformat()  # local time, no zone — recorded as-is
    return (dt - timedelta(hours=offset)).replace(tzinfo=timezone.utc).isoformat()


def _strip_html(text: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"[ \t]+", " ", text)


def _clean_block(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text.strip())


def _parse_number(text: str) -> float | None:
    m = re.search(r"(\d+(?:\.\d+)?)", text)
    return float(m.group(1)) if m else None


def _parse_latlon(center: str) -> tuple[float | None, float | None]:
    # RSS form: "30.1, -86.6"
    m = re.search(r"(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)", center)
    return (float(m.group(1)), float(m.group(2))) if m else (None, None)


def _parse_movement_text(text: str) -> tuple[int, float] | None:
    # RSS form: "N at 18 mph" — direction from compass point
    m = re.search(r"\b([NSEW]{1,3})\b.*?(\d+(?:\.\d+)?)\s*mph", text, re.I)
    if not m:
        return None
    compass = {"N": 0, "NNE": 22, "NE": 45, "ENE": 67, "E": 90, "ESE": 112,
               "SE": 135, "SSE": 157, "S": 180, "SSW": 202, "SW": 225,
               "WSW": 247, "W": 270, "WNW": 292, "NW": 315, "NNW": 337}
    return compass.get(m.group(1).upper(), 0), float(m.group(2))


def _landfall_sentence(lead: str) -> str:
    for sent in re.split(r"(?<=[.!?])\s+", lead):
        if "landfall" in sent.lower():
            return sent.strip()
    return ""
