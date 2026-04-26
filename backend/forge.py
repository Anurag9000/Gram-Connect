"""
forge.py — Gram Connect Team Forge Engine
==========================================
Deterministic, interpretable volunteer-to-task matching.
No ML. No embeddings. No training data. Pure arithmetic.

Individual score:
    SCORE(v, T) = (DOMAIN^w_d) * (WILL^w_w) * (AVAIL^w_a) * (PROX^w_p) * (FRESH^w_f)

    Weights are severity-conditional (see SEVERITY_FACTOR_WEIGHTS):
        HIGH emergency : avail weight raised (need someone free NOW), prox lenient
        NORMAL         : balanced data-fitted weights
        LOW routine    : prox weight raised (stay local), avail weight raised (don't bother busy people)

Team building:
    Greedy marginal-coverage selection.
    At each step pick whoever maximises:
        forge_score × (1 + α × new_skill_fraction) × (1 - β × redundancy_fraction)
    α=1.5 (bonus for covering new skills), β=0.3 (penalty for duplicating coverage)

Team ranking:
    team_score = coverage_fraction × geometric_mean(member scores) - γ × avg_distance_km
    Teams sorted by (coverage, team_score) descending.
"""

import csv
import math
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("forge")

# ── Constants ─────────────────────────────────────────────────────────────────

AVAILABILITY_LEVELS: Dict[str, float] = {
    "immediately available": 1.0,
    "generally available":   0.70,
    "rarely available":      0.35,
}

# Distance decay constant λ (km). Exponential penalty e^(-d/λ).
# Larger λ = more tolerant of distance. Scales up under high severity.
DISTANCE_DECAY: Dict[int, float] = {
    0: 25.0,   # LOW severity   — stay close
    1: 40.0,   # NORMAL severity
    2: 65.0,   # HIGH severity  — willing to reach far
}

OVERWORK_PENALTY_PER_HOUR = 0.10   # deducted per excess hour
DEFAULT_WEEKLY_QUOTA      = 5.0    # hours/week before overwork kicks in

COVERAGE_BONUS_ALPHA   = 1.5   # bonus multiplier for bringing new skills
REDUNDANCY_PENALTY_BETA = 0.30  # penalty multiplier for duplicating covered skills
PARTIAL_MATCH_CREDIT    = 0.5   # credit for substring skill overlap (vs 1.0 for exact)
TEAM_DISTANCE_WEIGHT    = 0.003  # per-km penalty in team ranking score

# Per-severity exponent weights fitted from 150k synthetic samples (50k per severity).
# Fitting: Model Shootout (LogReg, RF, XGBoost, LightGBM).
# Extracted via SHAP values from the best performing non-linear tree model,
# then normalized mathematically strictly to the 0.0 - 1.0 range.
#
# Interpretation of fitted weight ordering:
#   HIGH  : domain > will > avail > prox≈0
#           In an emergency you need someone skilled, committed, AND free.
#           Distance is irrelevant — reach anyone anywhere.
#   NORMAL: domain > will > avail > prox
#           Balanced. All factors matter; proximity still a soft constraint.
#   LOW   : domain > will > prox > avail
#           Routine task: any competent local person who is free and willing.
#           No single secondary factor dominates — spread the weight evenly.
#   fresh : ~0 across all severities — overwork rarely tips the decision.
SEVERITY_FACTOR_WEIGHTS: dict = {
    2: {  # HIGH  (Best: XGBoost, ROC-AUC 0.9288)
        "domain": 1.0000,
        "will":   0.4787,
        "avail":  0.4303,
        "prox":   0.0500,  # emergencies reach far — distance irrelevant
        "fresh":  0.0500,
    },
    1: {  # NORMAL  (Best: LightGBM, ROC-AUC 0.9084)
        "domain": 1.0000,
        "will":   0.5768,
        "avail":  0.5146,
        "prox":   0.2115,
        "fresh":  0.0500,
    },
    0: {  # LOW  (Best: LightGBM, ROC-AUC 0.7352)
        "domain": 1.0000,
        "will":   0.6612,
        "avail":  0.5122,
        "prox":   0.5363,  # strongest distance constraint — stay local
        "fresh":  0.0653,
    },
}

SEVERITY_MAP    = {"LOW": 0, "NORMAL": 1, "HIGH": 2}
SEVERITY_LABELS = {0: "LOW", 1: "NORMAL", 2: "HIGH"}

FALLBACK_SKILLS = [
    "project management",
    "community mobilization",
    "data analysis and reporting",
    "public health outreach",
    "household survey and enumeration",
]

# ── Keyword → Required Skills Extraction ─────────────────────────────────────

_KEYWORD_SKILL_MAP: List[Tuple[List[str], List[str]]] = [
    (["handpump", "pump", "borewell", "water pump"], [
        "handpump repair and maintenance",
        "plumbing",
        "pump maintenance",
        "mechanical systems (pumps/filtration)",
        "pipe fitting",
        "borewell installation and rehabilitation",
    ]),
    (["drain", "drainage", "sewer", "sewage", "de-silt", "clogged"], [
        "drainage design and de-silting",
        "rural road maintenance and culvert repair",
        "fecal sludge management",
    ]),
    (["toilet", "latrine", "sanitation", "odf", "open defecation"], [
        "toilet construction and retrofitting",
        "hygiene behavior change communication",
        "fecal sludge management",
    ]),
    (["water", "contamination", "quality", "testing", "contaminated", "potable"], [
        "water quality assessment",
        "groundwater assessment and monitoring",
        "public health outreach",
    ]),
    (["solar", "electricity", "electrification", "power", "wiring", "electrical", "grid"], [
        "solar microgrid design and maintenance",
        "solar pumping systems",
        "rural electrification safety and earthing",
        "electrical work",
    ]),
    (["road", "culvert", "bridge", "path", "pavement", "pothole"], [
        "rural road maintenance and culvert repair",
        "culvert and causeway design",
        "construction",
    ]),
    (["digital", "literacy", "smartphone", "computer", "internet", "spreadsheet"], [
        "education and digital literacy",
        "mobile data collection and dashboards",
        "data analysis and reporting",
    ]),
    (["health", "disease", "outbreak", "nutrition", "anganwadi", "vaccination", "fever"], [
        "public health outreach",
        "anganwadi strengthening",
        "school wq testing and wash in schools",
    ]),
    (["agriculture", "irrigation", "drip", "crop", "farm", "soil", "harvest"], [
        "drip and sprinkler irrigation setup",
        "soil testing and fertility management",
        "integrated pest management",
        "dairy and livestock management",
    ]),
    (["housing", "pmay", "construction", "house", "wall", "building", "shelter"], [
        "low-cost housing construction and PMAY support",
        "construction",
    ]),
    (["forest", "tree", "erosion", "plantation", "biodiversity", "watershed"], [
        "tree plantation and survival monitoring",
        "erosion control and gully plugging",
        "biodiversity and habitat restoration",
    ]),
    (["panchayat", "mgnrega", "beneficiary", "gram sabha", "sarpanch"], [
        "panchayat planning and budgeting",
        "gram sabha facilitation",
        "mgnrega works planning and measurement",
        "beneficiary identification and targeting",
    ]),
    (["shg", "women", "group", "cooperative", "self help", "microfinance"], [
        "self-help group formation and strengthening",
        "panchayat planning and budgeting",
    ]),
    (["survey", "gis", "mapping", "data", "enumeration", "census"], [
        "household survey and enumeration",
        "gis and remote sensing",
        "data analysis and reporting",
        "mobile data collection and dashboards",
    ]),
]

_SEVERITY_HIGH_WORDS = [
    "urgent", "emergency", "critical", "broken", "no water", "flooding",
    "collapse", "immediate", "danger", "severe", "crisis",
]
_SEVERITY_LOW_WORDS  = ["minor", "low priority", "routine", "request", "small"]


def extract_required_skills(text: str) -> List[str]:
    """Keyword-based skill extraction from proposal text."""
    t = text.lower()
    matched: List[str] = []
    seen: Set[str] = set()
    for keywords, skills in _KEYWORD_SKILL_MAP:
        if any(kw in t for kw in keywords):
            for s in skills:
                if s not in seen:
                    matched.append(s)
                    seen.add(s)
    return matched if matched else FALLBACK_SKILLS[:5]


def estimate_severity(text: str) -> int:
    """Returns 0=LOW, 1=NORMAL, 2=HIGH."""
    t = text.lower()
    if any(w in t for w in _SEVERITY_HIGH_WORDS):
        return 2
    if any(w in t for w in _SEVERITY_LOW_WORDS):
        return 0
    return 1


# ── Config ────────────────────────────────────────────────────────────────────

@dataclass
class ForgeConfig:
    people_csv:                  str
    proposal_text:               str
    village_locations:           str
    distance_csv:                str
    required_skills:             Optional[List[str]] = None
    auto_extract:                bool = True
    proposal_location_override:  Optional[str] = None
    task_start:                  Optional[str] = None
    task_end:                    Optional[str] = None
    team_size:                   Optional[int] = None
    num_teams:                   int = 3
    soft_cap:                    int = 6
    severity_override:           Optional[str] = None
    weekly_quota:                float = DEFAULT_WEEKLY_QUOTA
    overwork_penalty:            float = OVERWORK_PENALTY_PER_HOUR
    transcription:               Optional[str] = None
    visual_tags:                 Optional[List[str]] = None
    # Pre-loaded data (avoids re-reading CSVs on every call)
    _people:           Optional[List[Dict]] = field(default=None, repr=False)
    _distance_lookup:  Optional[Dict]       = field(default=None, repr=False)
    _village_names:    Optional[List[str]]  = field(default=None, repr=False)


# ── CSV Readers ───────────────────────────────────────────────────────────────

def read_people(csv_path: str) -> List[Dict]:
    people = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pid = (row.get("person_id") or row.get("id") or "").strip()
            if not pid:
                continue
            raw = (row.get("skills") or row.get("text") or "").strip()
            skills = [s.strip() for s in raw.replace(";", ",").split(",") if s.strip()]
            people.append({
                "person_id":         pid,
                "name":              (row.get("name") or row.get("full_name") or pid).strip(),
                "skills":            skills,
                "willingness_eff":   float(row.get("willingness_eff") or 0.5),
                "willingness_bias":  float(row.get("willingness_bias") or 0.5),
                "availability":      (row.get("availability") or "").strip().lower(),
                "availability_status": (row.get("availability_status") or "available").strip(),
                "home_location":     (row.get("home_location") or row.get("village") or "").strip(),
                "overwork_hours":    float(row.get("overwork_hours") or 0),
                "user_id":           (row.get("user_id") or pid).strip(),
                "email":             (row.get("email") or "").strip(),
            })
    return people


def load_distance_lookup(csv_path: str) -> Dict:
    lookup: Dict = {}
    if not csv_path or not os.path.exists(csv_path):
        return lookup
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            a = (row.get("village_a") or "").strip().lower()
            b = (row.get("village_b") or "").strip().lower()
            if a and b:
                entry = {
                    "distance": float(row.get("distance_km") or 0),
                    "travel":   float(row.get("travel_time_min") or 0),
                }
                lookup[(a, b)] = entry
                lookup[(b, a)] = entry
    return lookup


def load_village_names(csv_path: str) -> List[str]:
    names: List[str] = []
    if not csv_path or not os.path.exists(csv_path):
        return names
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            n = (row.get("village_name") or row.get("name") or "").strip()
            if n:
                names.append(n)
    return names


def extract_location(text: str, village_names: List[str]) -> Optional[str]:
    t = text.lower()
    for v in village_names:
        if v.lower() in t:
            return v
    return None


# ── Scoring Components ────────────────────────────────────────────────────────

def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-88, min(88, x))))


def _skill_overlap(person_skills: List[str], required: List[str]) -> Tuple[float, Set[str]]:
    """
    Fraction of required skills this person covers.
    Returns (score 0–1, set of required skills covered).
    Exact match = 1.0 credit, substring overlap = PARTIAL_MATCH_CREDIT.
    """
    if not required or not person_skills:
        return 0.0, set()
    norm_req = [r.lower().strip() for r in required]
    norm_ps  = [s.lower().strip() for s in person_skills]
    total_credit = 0.0
    covered: Set[str] = set()
    for i, r in enumerate(norm_req):
        best = 0.0
        for ps in norm_ps:
            if r == ps:
                best = 1.0
                break
            elif r in ps or ps in r:
                best = max(best, PARTIAL_MATCH_CREDIT)
        if best > 0:
            total_credit += best
            covered.add(required[i])
    return min(1.0, total_credit / len(required)), covered


def _will_score(volunteer: Dict) -> float:
    """Sigmoid of (willingness_eff + willingness_bias − 1) so that eff=0.5, bias=0.5 → 0.5."""
    eff  = float(volunteer.get("willingness_eff",  0.5) or 0.5)
    bias = float(volunteer.get("willingness_bias", 0.5) or 0.5)
    return _sigmoid(eff + bias - 1.0)


def _avail_score(volunteer: Dict) -> float:
    label = volunteer.get("availability", "").lower().strip()
    return AVAILABILITY_LEVELS.get(label, 0.5)


def _prox_score(volunteer: Dict, proposal_location: str, distance_lookup: Dict, severity_int: int) -> Tuple[float, float]:
    """Returns (proximity_factor 0–1, distance_km)."""
    home = (volunteer.get("home_location") or "").strip()
    if not home or not proposal_location:
        return 1.0, 0.0
    if home.lower() == proposal_location.lower():
        return 1.0, 0.0
    rec = distance_lookup.get((home.lower(), proposal_location.lower()))
    if not rec:
        # Unknown pair: mild penalty (volunteer may still be reachable)
        return 0.75, 0.0
    d   = float(rec.get("distance", 0.0))
    lam = DISTANCE_DECAY.get(severity_int, 40.0)
    return math.exp(-d / lam), d


def _fresh_score(volunteer: Dict, weekly_quota: float, overwork_penalty: float) -> float:
    excess = max(0.0, float(volunteer.get("overwork_hours") or 0) - weekly_quota)
    return max(0.0, 1.0 - overwork_penalty * excess)


# ── Individual Score ──────────────────────────────────────────────────────────

def score_volunteer(
    v:                 Dict,
    required:          List[str],
    proposal_location: str,
    distance_lookup:   Dict,
    severity_int:      int,
    weekly_quota:      float = DEFAULT_WEEKLY_QUOTA,
    overwork_penalty:  float = OVERWORK_PENALTY_PER_HOUR,
) -> Dict[str, Any]:
    """
    Compute SCORE(v, T) = (DOMAIN^w_d) × (WILL^w_w) × (AVAIL^w_a) × (PROX^w_p) × (FRESH^w_f)
    Returns the full volunteer dict enriched with all component scores.
    """
    domain, covered  = _skill_overlap(v["skills"], required)
    will             = _will_score(v)
    avail            = _avail_score(v)
    prox, dist_km    = _prox_score(v, proposal_location, distance_lookup, severity_int)
    fresh            = _fresh_score(v, weekly_quota, overwork_penalty)

    # Pull severity-specific weights: avail/prox shift based on task urgency
    w = SEVERITY_FACTOR_WEIGHTS.get(severity_int, SEVERITY_FACTOR_WEIGHTS[1])

    forge_score = (
        (domain ** w["domain"]) *
        (will   ** w["will"])   *
        (avail  ** w["avail"])  *
        (prox   ** w["prox"])   *
        (fresh  ** w["fresh"])
    )

    avail_label = v.get("availability", "").lower().strip()
    avail_level_num = {
        "immediately available": 3,
        "generally available":   2,
        "rarely available":      1,
    }.get(avail_label, 2)

    # match_score = the actual Forge score the engine uses for ranking.
    return {
        **v,
        # Component scores (all 0–1)
        "domain_score":      round(domain, 4),
        "willingness_score": round(will, 4),
        "avail_factor":      round(avail, 4),
        "prox_factor":       round(prox, 4),
        "fresh_factor":      round(fresh, 4),
        # Derived fields
        "distance_km":       round(dist_km, 2),
        "availability_level": avail_level_num,
        "forge_score":       round(forge_score, 6),
        "match_score":       round(forge_score, 4),  # = forge_score, exposed as display field
        "covered_skills":    covered,
    }


# ── Team Building ─────────────────────────────────────────────────────────────

def _effective_score(candidate: Dict, covered_so_far: Set[str], required: List[str]) -> float:
    """
    Score used during greedy selection:
        forge_score × (1 + α × new_coverage_fraction) × (1 − β × redundancy_fraction)
    """
    n = max(len(required), 1)
    cand_covered = candidate.get("covered_skills", set())
    new_skills   = cand_covered - covered_so_far
    redundant    = cand_covered & covered_so_far
    coverage_bonus   = COVERAGE_BONUS_ALPHA   * len(new_skills) / n
    redundancy_pen   = REDUNDANCY_PENALTY_BETA * len(redundant) / n
    return candidate["forge_score"] * (1.0 + coverage_bonus) * max(0.0, 1.0 - redundancy_pen)


def _build_one_team(
    scored_pool:  List[Dict],
    required:     List[str],
    target_size:  int,
    excluded_ids: Set[str],
) -> List[Dict]:
    """
    Two-phase greedy team builder to guarantee multi-domain coverage.

    Phase 1 — Coverage sweep:
        For each required skill not yet covered by the forming team, pick the
        highest-scoring volunteer who covers it.  This is a hard guarantee:
        every domain represented in `required` gets at least one specialist,
        regardless of how much higher other volunteers score on the dominant
        domain.  Without this phase, a pool of excellent plumbers would crowd
        out the public-health specialist even though the task needs both.

    Phase 2 — Quality fill:
        Fill remaining slots using the effective_score bonus (current logic):
        volunteers who cover NEW skills are preferred, redundant coverage is
        penalised.  This is where the best generalists and backup specialists
        are added.
    """
    team:     List[Dict] = []
    team_ids: Set[str]   = set()
    covered:  Set[str]   = set()
    pool = [v for v in scored_pool
            if v["person_id"] not in excluded_ids and v["forge_score"] > 0]

    # ── Phase 1: coverage sweep ───────────────────────────────────────────────
    # Iterate over every required skill.  If it is not yet covered by anyone
    # on the team, find the best-scoring volunteer who covers it and add them.
    for skill in required:
        if len(team) >= target_size:
            break
        if skill in covered:
            continue
        # Candidates who cover this specific skill and are not already on team
        candidates = [
            v for v in pool
            if v["person_id"] not in team_ids
            and skill in v.get("covered_skills", set())
        ]
        if not candidates:
            continue  # no one in the pool covers this domain; skip
        best = max(candidates, key=lambda v: v["forge_score"])
        team.append(best)
        team_ids.add(best["person_id"])
        covered |= best.get("covered_skills", set())

    # ── Phase 2: quality fill ─────────────────────────────────────────────────
    # Fill remaining slots.  effective_score still applies a coverage bonus so
    # volunteers who add novel skills are preferred over redundant additions.
    while len(team) < target_size and pool:
        best, best_es = None, -1.0
        for candidate in pool:
            if candidate["person_id"] in team_ids:
                continue
            es = _effective_score(candidate, covered, required)
            if es > best_es:
                best, best_es = candidate, es
        if not best:
            break
        team.append(best)
        team_ids.add(best["person_id"])
        covered |= best.get("covered_skills", set())

    return team



def _team_coverage(team: List[Dict], required: List[str]) -> float:
    if not required:
        return 0.0
    covered: Set[str] = set()
    for v in team:
        covered |= v.get("covered_skills", set())
    return len(covered) / len(required)


def _geometric_mean(values: List[float]) -> float:
    if not values:
        return 0.0
    product = math.prod(max(v, 1e-9) for v in values)
    return product ** (1.0 / len(values))


def _format_team(team: List[Dict], required: List[str], rank: int) -> Dict[str, Any]:
    coverage   = _team_coverage(team, required)
    gm_score   = _geometric_mean([v["forge_score"] for v in team])
    avg_dist   = sum(v["distance_km"] for v in team) / max(len(team), 1)
    will_avg   = sum(v["willingness_score"] for v in team) / max(len(team), 1)
    will_min   = min(v["willingness_score"] for v in team)
    team_score = coverage * gm_score - TEAM_DISTANCE_WEIGHT * avg_dist

    members_out = [
        {
            "person_id":         v["person_id"],
            "name":              v["name"],
            "skills":            v["skills"],
            "domain_score":      v["domain_score"],
            "willingness_score": v["willingness_score"],
            "distance_km":       v["distance_km"],
            "availability_level": v["availability_level"],
            "home_location":     v.get("home_location", ""),
            "match_score":       v["match_score"],
            "forge_score":       v["forge_score"],
            "user_id":           v.get("user_id", v["person_id"]),
            "email":             v.get("email", ""),
        }
        for v in team
    ]

    return {
        "rank":            rank,
        "team_ids":        ";".join(v["person_id"] for v in team),
        "team_names":      "; ".join(v["name"] for v in team),
        "team_size":       len(team),
        # team_score = coverage_fraction * geometric_mean(member forge scores) - 0.003 * avg_distance_km
        # Primary ranking key: a team that covers more required skills and has higher-quality members ranks first.
        "team_score":      round(team_score, 4),
        "coverage":        round(coverage, 4),
        "k_robustness":    0.0,   # deprecated metric
        "redundancy":      0.0,
        "set_size":        0.0,
        "willingness_avg": round(will_avg, 4),
        "willingness_min": round(will_min, 4),
        "avg_distance_km": round(avg_dist, 2),
        "members":         members_out,
    }


# ── Main Entry Point ──────────────────────────────────────────────────────────

def run_forge(config: ForgeConfig) -> Dict[str, Any]:
    """
    Full Forge pipeline:
      1. Load volunteers, distance matrix, village names
      2. Extract required skills from proposal text
      3. Score every volunteer with DOMAIN × WILL × AVAIL × PROX × FRESH
      4. Build N alternative teams via greedy marginal-coverage selection
      5. Sort teams by (coverage, team_score) and return ranked results

    Returns a dict compatible with the existing /recommend API response schema.
    """
    # ── Load Data ──────────────────────────────────────────────────────────
    people          = config._people          or read_people(config.people_csv)
    distance_lookup = config._distance_lookup or load_distance_lookup(config.distance_csv)
    village_names   = config._village_names   or load_village_names(config.village_locations)

    # ── Multimodal text fusion ─────────────────────────────────────────────
    text = config.proposal_text or ""
    if config.transcription:
        text = f"{text}\n\n[Audio]: {config.transcription}"
    if config.visual_tags:
        text = f"{text}\n\n[Visual]: {', '.join(config.visual_tags)}"

    # ── Location & Severity ────────────────────────────────────────────────
    proposal_location = (
        config.proposal_location_override
        or extract_location(text, village_names)
        or ""
    )

    if config.severity_override:
        severity_int    = SEVERITY_MAP.get(config.severity_override.upper(), 1)
        severity_source = "Coordinator Override"
    else:
        severity_int    = estimate_severity(text)
        severity_source = "Keyword Match"

    # ── Required Skills ────────────────────────────────────────────────────
    if config.required_skills:
        required = [s.strip() for s in config.required_skills if s.strip()]
    elif config.auto_extract:
        required = extract_required_skills(text)
    else:
        required = FALLBACK_SKILLS[:]

    if not required:
        required = FALLBACK_SKILLS[:]

    logger.info(
        "Forge: location=%r  severity=%s  required_skills=%d  volunteers=%d",
        proposal_location, SEVERITY_LABELS[severity_int], len(required), len(people),
    )

    # ── Score All Volunteers ───────────────────────────────────────────────
    scored = [
        score_volunteer(
            v, required, proposal_location, distance_lookup, severity_int,
            config.weekly_quota, config.overwork_penalty,
        )
        for v in people
    ]
    scored.sort(key=lambda v: v["forge_score"], reverse=True)

    # ── Build Alternative Teams ────────────────────────────────────────────
    target_size = config.team_size or config.soft_cap
    num_teams   = max(1, config.num_teams or 3)
    teams_out:  List[Dict] = []
    excluded:   Set[str]   = set()   # each team gets unique members

    for idx in range(num_teams):
        team = _build_one_team(scored, required, target_size, excluded)
        if not team:
            break
        teams_out.append(_format_team(team, required, rank=idx + 1))
        for m in team:
            excluded.add(m["person_id"])

    # ── Rank: coverage first, then team_score ──────────────────────────────
    teams_out.sort(key=lambda t: (t["coverage"], t["team_score"]), reverse=True)
    for i, t in enumerate(teams_out):
        t["rank"] = i + 1

    return {
        "severity_detected":  SEVERITY_LABELS.get(severity_int, "NORMAL"),
        "severity_source":    severity_source,
        "proposal_location":  proposal_location or None,
        "required_skills":    required,
        "teams":              teams_out,
    }
