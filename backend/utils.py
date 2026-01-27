import csv
import json
import math
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

# Constants
AVAILABILITY_LEVELS = {
    "rarely available": 0,
    "generally available": 1,
    "immediately available": 2,
}

SEVERITY_LABELS = {0: "LOW", 1: "NORMAL", 2: "HIGH"}

SEVERITY_KEYWORDS = {
    2: ["urgent", "immediate", "critical", "outbreak", "epidemic", "collapse", "broken", "flood", "drought", "disease", "contamination", "crisis", "emergency"],
    1: ["audit", "survey", "assessment", "monitoring", "planning", "inspection", "review", "repair", "maintenance"],
}

SEVERITY_AVAILABILITY_PENALTIES = {
    2: {"generally available": 0.2, "rarely available": 0.4},
    1: {"rarely available": 0.2},
    0: {},
}

VILLAGE_FALLBACK_SKILLS = [
    "water quality assessment",
    "drainage design and de-silting",
    "handpump repair and maintenance",
    "borewell installation and rehabilitation",
    "rainwater harvesting",
    "fecal sludge management",
    "toilet construction and retrofitting",
    "solid waste segregation and composting",
    "hygiene behavior change communication",
    "river restoration",
    "watershed management",
    "groundwater assessment and monitoring",
    "check dam and nala bund construction",
    "farm pond design and maintenance",
    "soil testing and fertility management",
    "integrated pest management",
    "drip and sprinkler irrigation setup",
    "dairy and livestock management",
    "fisheries pond management",
    "solar microgrid design and maintenance",
    "solar pumping systems",
    "rural road maintenance and culvert repair",
    "culvert and causeway design",
    "low-cost housing construction and PMAY support",
    "panchayat planning and budgeting",
    "gram sabha facilitation",
    "self-help group formation and strengthening",
    "mgnrega works planning and measurement",
    "beneficiary identification and targeting",
    "public health outreach",
    "school wq testing and wash in schools",
    "anganwadi strengthening",
    "education and digital literacy",
    "tree plantation and survival monitoring",
    "erosion control and gully plugging",
    "biodiversity and habitat restoration",
    "disaster preparedness and response",
    "gis and remote sensing",
    "household survey and enumeration",
    "data analysis and reporting",
    "mobile data collection and dashboards",
    "sensor deployment and iot",
    "project management",
    "safety and risk management",
]

# Robust replacement for math.exp to avoid overflow in sigmoid if needed,
# though Python's math.exp is usually fine for most ranges.
def robust_sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1 / (1 + z)
    else:
        z = math.exp(x)
        return z / (1 + z)

def normalize_phrase(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()

def read_csv_norm(fp: str) -> List[Dict[str, Any]]:
    rows = []
    if not os.path.exists(fp):
        raise FileNotFoundError(f"CSV file not found: {fp}")
    with open(fp, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"{fp}: missing header row")
        reader.fieldnames = [h.strip().lower() for h in reader.fieldnames]
        for r in reader:
            rows.append({(k.strip().lower() if k else k): (v.strip() if isinstance(v, str) else v)
                         for k, v in r.items()})
    return rows

def get_any(d: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    if d is None:
        return default
    for k in keys:
        if k in d and d[k] not in ("", None):
            return d[k]
    return default

def load_village_names(path: str) -> List[str]:
    if not path or not os.path.exists(path):
        return []
    try:
        rows = read_csv_norm(path)
        names = [get_any(r, ["village_name", "village", "name"], "") for r in rows]
        names = [n for n in names if n]
        return sorted(names, key=lambda n: len(n), reverse=True)
    except Exception:
        return []

def load_distance_lookup(path: str) -> Dict[Tuple[str, str], Dict[str, float]]:
    lookup: Dict[Tuple[str, str], Dict[str, float]] = {}
    if not path or not os.path.exists(path):
        return lookup
    try:
        rows = read_csv_norm(path)
        for r in rows:
            a = get_any(r, ["village_a", "from", "source"])
            b = get_any(r, ["village_b", "to", "destination"])
            if not a or not b:
                continue
            dist = float(get_any(r, ["distance_km", "distance"], 0.0) or 0.0)
            travel = float(get_any(r, ["travel_time_min", "travel_min"], 0.0) or 0.0)
            lookup[(a.lower(), b.lower())] = {"distance": dist, "travel": travel}
            lookup[(b.lower(), a.lower())] = {"distance": dist, "travel": travel}
    except Exception:
        pass
    return lookup

def extract_location(text: str, village_names: List[str]) -> str:
    norm_text = normalize_phrase(text or "")
    for name in village_names:
        if normalize_phrase(name) in norm_text:
            return name
    return ""

def estimate_severity(text: str) -> int:
    if not text:
        return 1 # Default to NORMAL if no text
    text_norm = str(text).lower()
    for kw in SEVERITY_KEYWORDS.get(2, []):
        if kw in text_norm:
            return 2
    for kw in SEVERITY_KEYWORDS.get(1, []):
        if kw in text_norm:
            return 1
    return 0

def severity_penalty(availability_label: str, severity_level: int) -> float:
    label = (availability_label or "").lower()
    penalties = SEVERITY_AVAILABILITY_PENALTIES.get(severity_level, {})
    return penalties.get(label, 0.0)

def lookup_distance_km(origin: str, target: str, distance_lookup: Dict[Tuple[str, str], Dict[str, float]]) -> float:
    if not origin or not target:
        return 0.0
    rec = distance_lookup.get((origin.lower(), target.lower()))
    if rec:
        return float(rec.get("distance", 0.0))
    return 0.0

def parse_datetime(value: str, label: str) -> datetime:
    if not value:
        raise ValueError(f"{label} is required.")
    value = value.strip()
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"{label} '{value}' is not a valid ISO-8601 timestamp.")
    if dt.tzinfo:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt

def split_hours_by_week(start: datetime, end: datetime) -> Dict[Tuple[int, int], float]:
    if end <= start:
        return {}
    hours_by_week: Dict[Tuple[int, int], float] = defaultdict(float)
    cursor = start
    while cursor < end:
        iso_year, iso_week, _ = cursor.isocalendar()
        week_key = (iso_year, iso_week)
        week_start = cursor - timedelta(days=cursor.weekday())
        week_end = week_start + timedelta(days=7)
        segment_end = min(end, week_end)
        hours = (segment_end - cursor).total_seconds() / 3600.0
        hours_by_week[week_key] += hours
        cursor = segment_end
    return dict(hours_by_week)

def intervals_overlap(intervals: List[Tuple[datetime, datetime]], new_interval: Tuple[datetime, datetime]) -> bool:
    ns, ne = new_interval
    for s, e in intervals:
        if s < ne and ns < e:
            return True
    return False

def parse_schedule_csv(path: str) -> Dict[str, Dict[str, Any]]:
    if not path or not os.path.exists(path):
        return {}
    try:
        rows = read_csv_norm(path)
        schedule: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            pid = get_any(row, ["person_id", "student_id", "volunteer_id", "id"])
            if not pid:
                continue
            start_raw = get_any(row, ["start", "start_time", "begin", "start_datetime"])
            end_raw = get_any(row, ["end", "end_time", "finish", "finish_time", "end_datetime"])
            if not start_raw or not end_raw:
                continue
            try:
                start_dt = parse_datetime(start_raw, f"schedule start for {pid}")
                end_dt = parse_datetime(end_raw, f"schedule end for {pid}")
            except ValueError:
                continue
            if end_dt <= start_dt:
                continue
            info = schedule.setdefault(pid, {"intervals": [], "week_hours": defaultdict(float)})
            info["intervals"].append((start_dt, end_dt))
            week_hours = split_hours_by_week(start_dt, end_dt)
            for wk, hrs in week_hours.items():
                info["week_hours"][wk] += hrs
        for info in schedule.values():
            if isinstance(info.get("week_hours"), defaultdict):
                info["week_hours"] = dict(info["week_hours"])
        return schedule
    except Exception:
        return {}
