"""
m3_recommend.py  — M3 + ULTRA with willingness, expanded village skills, auto extraction

What’s new:
- Flexible CSV headers: person_id|student_id, text|skills
- Auto skill extraction from proposal_text using embed_skills_extractor.extract_skills_embed if available
- Or pass --skills_json (path to JSON: either ["skill", ...]  OR  {"skills":[...]} )
- Strong village fallback skills if nothing supplied
- W-weighted coverage, k-robustness, redundancy, set-size → goodness

Usage (PowerShell):
  python m3_recommend.py `
    --model backend/runtime_data/canonical_model.pkl `
    --people people.csv `
    --proposal_text "village drains blocked; handpump broken; need toilets and awareness" `
    --out teams_m3.csv `
    --tau 0.35 --soft_cap 6 `
    --auto_extract --threshold 0.20

Or if you already have a skills JSON:
  python m3_recommend.py --model backend/runtime_data/canonical_model.pkl --people people.csv --proposal_text "..." --skills_json skills.json --out teams_m3.csv
"""

import argparse
import csv
import json
import pickle
import math
import os
import re
import logging
from dataclasses import dataclass
from typing import List, Dict, Tuple, Any, Optional
from datetime import datetime, timedelta, timezone
from collections import defaultdict

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from embeddings import embed_texts
from embeddings import embed_with
from path_utils import get_repo_paths

from utils import (
    AVAILABILITY_LEVELS,
    SEVERITY_LABELS,
    SEVERITY_KEYWORDS,
    SEVERITY_AVAILABILITY_PENALTIES,
    VILLAGE_FALLBACK_SKILLS,
    robust_sigmoid,
    normalize_phrase,
    read_csv_norm,
    get_any,
    load_village_names,
    load_distance_lookup,
    extract_location,
    estimate_severity,
    severity_penalty,
    lookup_distance_km,
    parse_datetime,
    split_hours_by_week,
    intervals_overlap,
    parse_schedule_csv,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("m3_recommend")

# Backward-compatible alias used by older utilities and tests.
sigmoid = robust_sigmoid


@dataclass
class RecommendationConfig:
    model: str
    people: str
    proposal_text: Optional[str] = None
    proposal_file: Optional[str] = None
    proposal_location_override: Optional[str] = None
    required_skills: Optional[List[str]] = None
    skills_json: Optional[str] = None
    auto_extract: bool = False
    threshold: float = 0.25
    out: Optional[str] = "teams_m3.csv"
    tau: float = 0.35
    task_start: Optional[str] = None
    task_end: Optional[str] = None
    schedule_csv: Optional[str] = None
    weekly_quota: float = 5.0
    overwork_penalty: float = 0.1
    soft_cap: int = 6
    topk_swap: int = 10
    k_robust: int = 1
    lambda_red: float = 1.0
    lambda_size: float = 1.0
    lambda_will: float = 0.5
    size_buckets: Optional[str] = None
    team_size: Optional[int] = None
    num_teams: Optional[int] = None
    severity_override: Optional[str] = None
    village_locations: Optional[str] = None
    distance_csv: Optional[str] = None
    distance_scale: float = 50.0
    distance_decay: float = 30.0
    # Hybrid Multimodal extensions
    transcription: Optional[str] = None
    visual_tags: Optional[List[str]] = None
    
    # Performance optimization
    loaded_bundle: Optional[Any] = None

# -------- reading people / roster (robust) --------

def read_people(people_csv: str) -> List[Dict]:
    rows = read_csv_norm(people_csv)
    out = []
    for r in rows:
        pid = get_any(r, ["person_id","student_id","id"])
        if not pid:
            # skip rows without id
            continue
        name = get_any(r, ["name","person_name","full_name"], pid)
        text = get_any(r, ["text","skills"], "")
        # turn either "text" or "skills" into a list of phrases; accept both sentencey or ; separated
        raw = get_any(r, ["skills", "text"], "")
        
        # split on semicolons if present; otherwise keep sentences/phrases by splitting on commas as a fallback
        if ";" in raw:
            skills = [s.strip() for s in raw.split(";") if s.strip()]
        else:
            skills = [s.strip() for s in raw.replace("  ", " ").split(",") if s.strip()]
        # willingness
        try:
            eff = float(get_any(r, ["willingness_eff","eff","w_eff"], 0.5))
        except Exception:
            eff = 0.5
        try:
            bias = float(get_any(r, ["willingness_bias","bias","w_bias"], 0.5))
        except Exception:
            bias = 0.5
        W = robust_sigmoid(eff + bias)
        out.append({
            "person_id": pid,
            "name": name,
            "text": text,
            "skills": skills,
            "W": W,
            "availability": (get_any(r, ["availability"], "") or "").lower(),
            "home_location": get_any(r, ["home_location", "location", "village"], ""),
        })
    return out

# --------- ULTRA metrics with willingness ----------

def similarity_coverage(required: List[str], team_members: List[Dict], backend: str, model_or_vec, tau: float = 0.35):
    """
    W-weighted similarity coverage with member-level aggregation.
    """
    member_phrases = []
    ownersW = []
    member_index = []
    for idx, m in enumerate(team_members):
        for sk in m["skills"]:
            member_phrases.append(sk)
            ownersW.append(m["W"])
            member_index.append(idx)
    if not required:
        return 0.0, {}, {}
    if not member_phrases:
        return 0.0, {r: 0.0 for r in required}, {r: 0 for r in required}

    R = embed_with(model_or_vec, required, backend)
    M = embed_with(model_or_vec, member_phrases, backend)
    S = cosine_similarity(R, M)
    Wcol = np.array(ownersW).reshape(1, -1)
    S_w = S * Wcol

    per_member_best = [np.zeros(len(required), dtype=float) for _ in range(len(team_members))]
    for col in range(S_w.shape[1]):
        owner = member_index[col]
        col_vals = np.array(S_w[:, col]).ravel()
        per_member_best[owner] = np.maximum(per_member_best[owner], col_vals)

    per_req_best = np.max(np.stack(per_member_best, axis=0), axis=0) if len(team_members) else np.zeros(len(required))

    covered_counts = {}
    for i, req in enumerate(required):
        count = sum(1 for u in range(len(team_members)) if per_member_best[u][i] >= tau)
        covered_counts[req] = int(count)

    adj = []
    for s in per_req_best:
        s = float(s)
        if s < tau:
            adj.append(0.0)
        else:
            # Handle tau=1.0 edge case or very high tau
            denom = (1.0 - tau)
            if denom <= 1e-6: # Case where tau is close to 1.0
                adj.append(1.0 if s >= tau else 0.0)
            else:
                adj.append(min(1.0, (s - tau) / denom))
    coverage = float(np.mean(adj)) if len(adj) else 0.0
    return coverage, {required[i]: float(per_req_best[i]) for i in range(len(required))}, covered_counts

def redundancy_metric(required: List[str], covered_counts: Dict[str, int]) -> float:
    if not required: return 0.0
    redundant = sum(1 for r in required if covered_counts.get(r, 0) >= 2)
    return redundant / len(required)

def k_robustness(required: List[str], team_members: List[Dict], backend: str, model_or_vec, tau: float = 0.35, k: int = 1, sample_limit: int = 2000) -> float:
    """Robustness measured over the subset of required skills the full team actually covers.
    This avoids always returning 0 when the skill list is longer than the team can cover."""
    if not team_members:
        return 0.0
    _, per_req_best, _ = similarity_coverage(required, team_members, backend, model_or_vec, tau)
    # Only measure over skills the full team covers – fairer for small teams
    covered = [r for r, v in per_req_best.items() if v >= tau]
    if not covered:
        return 0.0
    n = len(team_members)
    if n == 1:
        return 0.0  # nothing to remove
    import itertools, random
    k = max(1, min(k, n - 1))
    subsets: list = []
    for r in range(1, k + 1):
        subsets.extend(itertools.combinations(range(n), r))
        if len(subsets) > sample_limit:
            break
    if len(subsets) > sample_limit:
        subsets = random.sample(subsets, sample_limit)
    if not subsets:
        return 0.0
    ok = 0
    for rem in subsets:
        sub_members = [m for i, m in enumerate(team_members) if i not in rem]
        _, per_req_best2, _ = similarity_coverage(covered, sub_members, backend, model_or_vec, tau)
        if all(v >= tau for v in per_req_best2.values()):
            ok += 1
    return ok / len(subsets)

def team_metrics(required: List[str], team_members: List[Dict], backend: str, model_or_vec, tau: float = 0.35, k: int = 1) -> Dict[str, float]:
    coverage, per_req_best, covered_counts = similarity_coverage(required, team_members, backend, model_or_vec, tau)
    redundancy = redundancy_metric(required, covered_counts)
    soft_cap = max(len(required), 4)
    set_size = min(len(team_members) / soft_cap, 1.0)
    krob = k_robustness(required, team_members, backend, model_or_vec, tau, k=k)
    w_vals = [float(m.get("W", 0.0)) for m in team_members]
    willingness_avg = float(np.mean(w_vals)) if w_vals else 0.0
    willingness_min = float(np.min(w_vals)) if w_vals else 0.0
    return {
        "coverage": coverage,
        "redundancy": redundancy,
        "set_size": set_size,
        "k_robustness": krob,
        "willingness_avg": willingness_avg,
        "willingness_min": willingness_min,
    }

def goodness(metrics: Dict[str, float], lambda_red: float = 1.0, lambda_size: float = 1.0, lambda_will: float = 0.5) -> float:
    # k_robustness removed: tasks are single-classification and small teams can't achieve redundancy.
    # Score = multiplicative combination of coverage × willingness, penalised by size and redundancy.
    # This ensures a plumber on a plumbing task scores high, not just a willing but irrelevant person.
    coverage = metrics["coverage"]
    willingness = metrics["willingness_avg"]
    # Combined skill×will: geometric mean so both matter
    core = math.sqrt(max(coverage, 0.0) * max(willingness, 0.0))
    s = (
        2.0 * core                            # main signal
        + lambda_will * willingness            # bonus for high-willingness teams
        - lambda_red * metrics["redundancy"]   # penalty for skill duplication
        - lambda_size * metrics["set_size"]    # gentle penalty for large teams
    )
    return max(0.0, min(1.0, (s + 0.5) / 3.5))

# ------------- size-bucket selection -------------

DEFAULT_SIZE_BUCKETS = "small:2-10:10,medium:11-50:10,large:51-200:10"

def parse_size_buckets(spec: str):
    buckets = []
    if not spec:
        return buckets
    parts = [p.strip() for p in spec.split(",") if p.strip()]
    for part in parts:
        try:
            label, size_range, limit = [x.strip() for x in part.split(":")]
        except ValueError:
            raise ValueError(f"Invalid --size_buckets entry '{part}'. Expected label:min-max:limit.")
        if "-" in size_range:
            min_s, max_s = [x.strip() for x in size_range.split("-", 1)]
        else:
            min_s = max_s = size_range.strip()
        try:
            min_size = int(min_s)
        except ValueError:
            raise ValueError(f"Invalid min size '{min_s}' in size bucket '{part}'.")
        if max_s.lower() in ("inf", "infinity", "*", "max"):
            max_size = math.inf
        else:
            try:
                max_size = int(max_s)
            except ValueError:
                raise ValueError(f"Invalid max size '{max_s}' in size bucket '{part}'.")
        try:
            limit_int = int(limit)
        except ValueError:
            raise ValueError(f"Invalid limit '{limit}' in size bucket '{part}'.")
        if limit_int < 0:
            raise ValueError(f"Limit must be >= 0 in size bucket '{part}'.")
        buckets.append({
            "label": label,
            "min": min_size,
            "max": max_size,
            "limit": limit_int,
        })
    return buckets

def select_top_teams_by_size(teams: List[Dict], buckets):
    if not buckets:
        return teams
    grouped = {b["label"]: [] for b in buckets}
    for team in teams:
        size = team.get("team_size")
        if size is None:
            size = team.get("team_ids", "").count(";") + 1 if team.get("team_ids") else 0
        assigned = False
        for bucket in buckets:
            min_size = bucket["min"]
            max_size = bucket["max"]
            if size < min_size or (max_size is not math.inf and size > max_size):
                continue
            label = bucket["label"]
            if len(grouped[label]) < bucket["limit"]:
                grouped[label].append(team)
            assigned = True
            break
    ordered = []
    for bucket in buckets:
        ordered.extend(grouped[bucket["label"]])
    return ordered

# ------------- skill acquisition logic -------------

def _load_skills_json(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        blob = json.load(f)
    if isinstance(blob, list):
        return [str(x) for x in blob]
    if isinstance(blob, dict) and "skills" in blob and isinstance(blob["skills"], list):
        return [str(x) for x in blob["skills"]]
    raise ValueError(f"--skills_json must be a JSON array or an object with a 'skills' array.")

# Keyword→skill mapping: words in proposal text → concrete required skills
_KEYWORD_SKILL_MAP: List[tuple] = [
    (["handpump", "pump", "borewell", "water pump"], [
        "handpump repair and maintenance",
        "plumbing",
        "pump maintenance",
        "mechanical systems (pumps/filtration)",
        "pipe fitting",
        "borewell installation and rehabilitation",
    ]),
    (["drain", "drainage", "sewer", "sewage", "de-silt"], [
        "drainage design and de-silting",
        "rural road maintenance and culvert repair",
        "fecal sludge management",
    ]),
    (["toilet", "latrine", "sanitation", "odf"], [
        "toilet construction and retrofitting",
        "hygiene behavior change communication",
        "fecal sludge management",
    ]),
    (["water", "contamination", "quality", "testing", "contaminated"], [
        "water quality assessment",
        "groundwater assessment and monitoring",
        "public health outreach",
    ]),
    (["solar", "electricity", "electrification", "power", "wiring", "electrical"], [
        "solar microgrid design and maintenance",
        "solar pumping systems",
        "rural electrification safety and earthing",
        "electrical work",
    ]),
    (["road", "culvert", "bridge", "path", "pavement"], [
        "rural road maintenance and culvert repair",
        "culvert and causeway design",
        "construction",
    ]),
    (["digital", "literacy", "smartphone", "computer", "spreadsheet", "internet"], [
        "education and digital literacy",
        "mobile data collection and dashboards",
        "data analysis and reporting",
    ]),
    (["health", "disease", "outbreak", "nutrition", "anganwadi", "vaccination"], [
        "public health outreach",
        "anganwadi strengthening",
        "school wq testing and wash in schools",
    ]),
    (["agriculture", "irrigation", "drip", "crop", "farm", "soil"], [
        "drip and sprinkler irrigation setup",
        "soil testing and fertility management",
        "integrated pest management",
        "dairy and livestock management",
    ]),
    (["housing", "pmay", "construction", "house", "wall", "building"], [
        "low-cost housing construction and PMAY support",
        "construction",
    ]),
    (["forest", "tree", "erosion", "plantation", "biodiversity"], [
        "tree plantation and survival monitoring",
        "erosion control and gully plugging",
        "biodiversity and habitat restoration",
    ]),
    (["gram sabha", "panchayat", "mgnrega", "beneficiary"], [
        "panchayat planning and budgeting",
        "gram sabha facilitation",
        "mgnrega works planning and measurement",
        "beneficiary identification and targeting",
    ]),
    (["shg", "self.help", "women", "group", "cooperative"], [
        "self-help group formation and strengthening",
        "panchayat planning and budgeting",
    ]),
    (["survey", "gis", "mapping", "data", "enumeration"], [
        "household survey and enumeration",
        "gis and remote sensing",
        "data analysis and reporting",
        "mobile data collection and dashboards",
    ]),
    (["solar", "pump", "irrigation"], [
        "solar pumping systems",
        "pump maintenance",
    ]),
]

def _auto_extract_skills(text: str, threshold: float) -> List[str]:
    """Extract required skills from proposal text using keyword matching against a comprehensive map.
    This avoids returning a generic 15-skill list that produces meaningless coverage scores."""
    try:
        import embed_skills_extractor as ex
        return ex.extract_skills_embed(text, topk_per_sentence=7, threshold=threshold)
    except Exception:
        pass

    t = (text or "").lower()
    matched: List[str] = []
    seen: set = set()
    for keywords, skills in _KEYWORD_SKILL_MAP:
        if any(kw in t for kw in keywords):
            for s in skills:
                if s not in seen:
                    matched.append(s)
                    seen.add(s)

    # Always include the top few fallback skills as a backstop so the list is never empty
    if not matched:
        return VILLAGE_FALLBACK_SKILLS[:6]
    return matched

# ------------------------ main ---------------------

def run_recommender(config: RecommendationConfig) -> Dict[str, Any]:
    # 1. Validation & Setup
    if not config.proposal_text and not (config.proposal_file and os.path.exists(config.proposal_file)):
        raise ValueError("Provide proposal_text or a valid proposal_file")

    text = config.proposal_text
    if config.proposal_file and os.path.exists(config.proposal_file):
        with open(config.proposal_file, "r", encoding="utf-8") as f:
            file_text = f.read()
            text = (text + "\n" + file_text) if text else file_text

    # Multimodal Fusion
    if config.transcription:
        text = f"{text}\n\n[Transcribed Audio Context]: {config.transcription}"
    if config.visual_tags:
        text = f"{text}\n\n[Visual Content Tags]: {', '.join(config.visual_tags)}"

    village_names = load_village_names(config.village_locations)
    distance_lookup = load_distance_lookup(config.distance_csv)
    proposal_location = config.proposal_location_override or extract_location(text, village_names)

    if config.severity_override:
        severity_level = {"LOW": 0, "NORMAL": 1, "HIGH": 2}.get(config.severity_override, 1)
    else:
        severity_level = estimate_severity(text)

    task_start = parse_datetime(config.task_start, "task_start")
    task_end = parse_datetime(config.task_end, "task_end")
    if task_end <= task_start:
        raise ValueError("task_end must be after task_start")

    task_interval = (task_start, task_end)
    task_week_hours = split_hours_by_week(task_start, task_end)
    schedule_map = parse_schedule_csv(config.schedule_csv) if config.schedule_csv else {}

    # 2. Process Volunteers (People)
    all_people = read_people(config.people)
    if not all_people:
        raise ValueError("No valid volunteers found in people data.")

    # 3. Load the trained model bundle.
    if config.loaded_bundle:
        bundle = config.loaded_bundle
    elif not os.path.exists(config.model):
        raise FileNotFoundError(
            f"Trained model bundle not found at {config.model}. "
            "Train and persist the canonical model before calling the recommender."
        )
    else:
        with open(config.model, "rb") as f:
            bundle = pickle.load(f)
    clf = bundle["model"]
    backend = bundle["backend"]
    prop_model = bundle["prop_model"]
    people_model = bundle["people_model"]
    distance_scale = bundle.get("distance_scale", config.distance_scale)
    distance_decay = bundle.get("distance_decay", config.distance_decay)

    filtered_people: List[Dict[str, Any]] = []
    for person in all_people:
        sched_info = schedule_map.get(person["person_id"], {})
        intervals = sched_info.get("intervals", [])
        if intervals and intervals_overlap(intervals, task_interval):
            continue
            
        week_hours_map = sched_info.get("week_hours", {})
        overwork_total = 0.0
        for week_key, hrs in task_week_hours.items():
            existing = float(week_hours_map.get(week_key, 0.0))
            overwork_total += max(0.0, (existing + hrs) - config.weekly_quota)
            
        adjusted = dict(person)
        base_W = person["W"]
        penalty_overwork = config.overwork_penalty * overwork_total
        adjusted_W = max(0.0, min(1.0, base_W - penalty_overwork))
        
        adjusted.update({
            "W_original": base_W,
            "W_base": adjusted_W,
            "W": adjusted_W,
            "overwork_hours": overwork_total
        })
        filtered_people.append(adjusted)
        
    if not filtered_people:
        raise ValueError("No available volunteers after applying constraints.")

    # 4. Acquire required skills
    if config.required_skills:
        required = [s for s in config.required_skills if s.strip()]
    elif config.skills_json:
        required = _load_skills_json(config.skills_json)
    elif config.auto_extract:
        required = _auto_extract_skills(text, config.threshold)
    else:
        required = VILLAGE_FALLBACK_SKILLS
    if not required:
        required = VILLAGE_FALLBACK_SKILLS

    # 5. Ranking & Feature Matrix
    # Compute domain_score via direct skill-set overlap with required skills.
    # The cross-model embedding cosine (prop_model vs people_model) is unreliable because
    # the two models project to different embedding spaces.
    norm_required = {normalize_phrase(r) for r in required}

    def _skill_overlap_score(person_skills: List[str]) -> float:
        """Fraction of required skills covered by this person's skills (with partial credit)."""
        if not norm_required or not person_skills:
            return 0.0
        norm_ps = {normalize_phrase(s) for s in person_skills}
        exact = len(norm_required & norm_ps)
        # Partial: a required token appears as substring in a skill or vice versa
        partial = sum(
            0.5 for r in norm_required for ps in norm_ps
            if r != ps and (r in ps or ps in r)
        )
        return min(1.0, (exact + partial) / len(norm_required))

    # Still compute embedding sims for the ML model feature (even if imperfect)
    P = embed_with(prop_model, [text], backend)
    S = embed_with(people_model, [p["text"] for p in filtered_people], backend)
    sims = cosine_similarity(P, S).ravel()

    features = []
    for idx, p in enumerate(filtered_people):
        avail_label = (p.get("availability") or "").lower()
        avail_level = AVAILABILITY_LEVELS.get(avail_label, 1)
        base_W = p["W_base"]
        sev_pen = severity_penalty(avail_label, severity_level)
        W_sev = max(0.0, min(1.0, base_W - sev_pen))

        dist_km = lookup_distance_km(p.get("home_location"), proposal_location, distance_lookup)
        dist_norm = min(dist_km / distance_scale, 1.0) if distance_scale > 0 else 0.0
        dist_pen = math.exp(-dist_km / distance_decay) if distance_decay > 0 else 1.0

        W_final = max(0.0, min(1.0, W_sev * dist_pen))
        # Interpretable domain score: what fraction of the task's required skills does this person cover?
        domain_score = _skill_overlap_score(p.get("skills", []))
        p.update({
            "W": W_final,
            "distance_km": dist_km,
            "distance_penalty": dist_pen,
            "availability_level": avail_level,
            "severity_level": severity_level,
            "severity_penalty": sev_pen,
            "domain_score": round(domain_score, 4),
            "willingness_score": round(W_final, 4),
            "overwork_hours": round(p.get("overwork_hours", 0.0), 2),
        })
        # ML features: use domain_score (now skill-overlap) as primary signal
        features.append([
            domain_score,
            domain_score * W_final,
            W_final,
            dist_norm,
            dist_pen,
            avail_level / 2.0,
            severity_level / 2.0,
        ])


    probs = clf.predict_proba(np.asarray(features))[:, 1]
    # Blend model prob with domain_score so pure skill-match people rank higher
    for p, prob in zip(filtered_people, probs):
        blended = 0.5 * float(prob) + 0.5 * p["domain_score"]
        p["model_prob"] = round(blended, 4)
    ranked = sorted(zip(filtered_people, probs), key=lambda x: x[0]["model_prob"], reverse=True)

    # 6. Team Building logic
    # Use direct skill-overlap for coverage (not embedding similarity) for interpretability.
    # tau=0.6 means a volunteer skill must be at least 60% semantically similar to a required skill.
    COVERAGE_TAU = 0.60
    def evaluate(tlist):
        mets = team_metrics(required, tlist, backend, people_model, tau=COVERAGE_TAU, k=config.k_robust)
        score = goodness(mets, lambda_red=config.lambda_red, lambda_size=config.lambda_size, lambda_will=config.lambda_will)
        return score, mets

    team: List[Dict] = []
    team_ids = set()
    best_score, _ = evaluate(team)
    soft_cap = config.team_size or config.soft_cap

    while len(team) < soft_cap:
        best_cand, best_cand_score, best_cand_mets, best_cand_prob = None, -float('inf'), None, -1.0
        # If user explicitly wants a team size, allow negative score deltas to fill the roster.
        # Otherwise, only accept additions that improve the score.
        best_delta = -float('inf') if config.team_size else 0.0
        for p, prob in ranked:
            if p["person_id"] in team_ids: continue
            cand_score, cand_mets = evaluate(team + [p])
            delta = cand_score - best_score
            if delta > best_delta + 1e-9 or (abs(delta - best_delta) <= 1e-9 and prob > best_cand_prob):
                best_cand, best_cand_score, best_cand_mets, best_cand_prob, best_delta = p, cand_score, cand_mets, prob, delta
        if not best_cand or (best_delta <= 1e-9 and not config.team_size): break
        team.append(best_cand)
        team_ids.add(best_cand["person_id"])
        best_score = best_cand_score
        # Early exit only when skills are fully covered (no robustness dependency)
        if not config.team_size and best_cand_mets["coverage"] >= 0.999: break


    # 7. Variants & Consolidation
    # Build N alternative full-size teams by re-running the greedy algorithm
    # from different starting seeds (top-ranked non-team-1 candidates).
    recs = []
    def add_rec(tlist):
        g, m = evaluate(tlist)
        dist_vals = [float(mm.get("distance_km", 0.0)) for mm in tlist]
        avg_dist = round(sum(dist_vals) / len(dist_vals), 2) if dist_vals else 0.0
        enriched = [{**mm, "home_location": mm.get("home_location", "")} for mm in tlist]
        recs.append({
            "team_ids": ";".join([mm["person_id"] for mm in enriched]),
            "team_names": "; ".join([mm["name"] for mm in enriched]),
            "team_size": len(enriched),
            "goodness": round(g, 4),
            "coverage": round(m["coverage"], 3),
            "k_robustness": round(m["k_robustness"], 3),
            "redundancy": round(m["redundancy"], 3),
            "set_size": round(m["set_size"], 3),
            "willingness_avg": round(m["willingness_avg"], 3),
            "willingness_min": round(m["willingness_min"], 3),
            "avg_distance_km": avg_dist,
            "members": enriched
        })


    add_rec(team)

    # Generate alternative full-size teams: exclude team-1 members, re-run greedy from scratch
    requested_limit = max(1, int(config.num_teams)) if config.num_teams else 3
    team1_ids = {m["person_id"] for m in team}
    alt_pool = [(p, prob) for p, prob in ranked if p["person_id"] not in team1_ids]

    for alt_seed_idx in range(requested_limit - 1):
        alt_team: List[Dict] = []
        alt_team_ids: set = set()
        alt_excluded = set(team1_ids)
        # Each alternative excludes the seed candidates already used in previous alternatives
        for prev_rec in recs[1:]:
            for prev_member in prev_rec["members"]:
                alt_excluded.add(prev_member["person_id"])

        alt_ranked = [(p, prob) for p, prob in alt_pool if p["person_id"] not in alt_excluded]
        if not alt_ranked:
            break

        alt_best_score, _ = evaluate([])
        while len(alt_team) < soft_cap:
            best_cand_alt, best_alt_prob = None, -1.0
            best_alt_delta = -float('inf') if config.team_size else 0.0
            for p_alt, prob_alt in alt_ranked:
                if p_alt["person_id"] in alt_team_ids: continue
                cand_score_alt, _ = evaluate(alt_team + [p_alt])
                delta_alt = cand_score_alt - alt_best_score
                if delta_alt > best_alt_delta + 1e-9 or (abs(delta_alt - best_alt_delta) <= 1e-9 and prob_alt > best_alt_prob):
                    best_cand_alt, best_alt_prob, best_alt_delta = p_alt, prob_alt, delta_alt
                    alt_best_score = cand_score_alt
            if not best_cand_alt or (best_alt_delta <= 1e-9 and not config.team_size):
                break
            alt_team.append(best_cand_alt)
            alt_team_ids.add(best_cand_alt["person_id"])
        if alt_team:
            add_rec(alt_team)

    # Deduplicate and sort; do NOT strip members across teams (these are alternatives, not serial assignments)
    dedup = {r['team_ids']: r for r in recs}.values()
    sorted_recs = sorted(dedup, key=lambda r: (r["coverage"], r["goodness"]), reverse=True)
    buckets = parse_size_buckets(config.size_buckets)
    final = list(sorted_recs[:requested_limit])
    resolved = final
    
    # Add rank
    for i, r in enumerate(resolved, start=1):
        r["rank"] = i

    return {
        "severity_detected": SEVERITY_LABELS.get(severity_level, "NORMAL"),
        "severity_source": "Coordinator Override" if config.severity_override else "Keyword Match",
        "proposal_location": proposal_location,
        "teams": resolved
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--proposal_text", help="Raw project/proposal text")
    ap.add_argument("--proposal_file", help="Path to proposal text file")
    ap.add_argument("--people", required=True)
    ap.add_argument("--required_skills", nargs="+", help="Explicit required skills")
    ap.add_argument("--skills_json", help="Path to JSON skills")
    ap.add_argument("--auto_extract", action="store_true")
    ap.add_argument("--threshold", type=float, default=0.25)
    ap.add_argument("--out", default="teams_m3.csv")
    ap.add_argument("--tau", type=float, default=0.35)
    ap.add_argument("--task_start", required=True)
    ap.add_argument("--task_end", required=True)
    
    default_root = str(get_repo_paths().data_dir.resolve())
    ap.add_argument("--village_locations", default=os.path.join(default_root, "village_locations.csv"))
    ap.add_argument("--distance_csv", default=os.path.join(default_root, "village_distances.csv"))
    ap.add_argument("--distance_scale", type=float, default=50.0)
    ap.add_argument("--distance_decay", type=float, default=30.0)
    ap.add_argument("--severity", choices=["LOW", "NORMAL", "HIGH"])
    ap.add_argument("--schedule_csv")
    ap.add_argument("--weekly_quota", type=float, default=5.0)
    ap.add_argument("--overwork_penalty", type=float, default=0.1)
    ap.add_argument("--soft_cap", type=int, default=6)
    ap.add_argument("--topk_swap", type=int, default=10)
    ap.add_argument("--k_robust", type=int, default=1)
    ap.add_argument("--lambda_red", type=float, default=1.0)
    ap.add_argument("--lambda_size", type=float, default=1.0)
    ap.add_argument("--lambda_will", type=float, default=0.5)
    ap.add_argument("--size_buckets", default=DEFAULT_SIZE_BUCKETS)
    
    args = ap.parse_args()
    
    cfg = RecommendationConfig(
        model=args.model,
        people=args.people,
        proposal_text=args.proposal_text,
        proposal_file=args.proposal_file,
        required_skills=args.required_skills,
        skills_json=args.skills_json,
        auto_extract=args.auto_extract,
        threshold=args.threshold,
        out=args.out,
        tau=args.tau,
        task_start=args.task_start,
        task_end=args.task_end,
        schedule_csv=args.schedule_csv,
        weekly_quota=args.weekly_quota,
        overwork_penalty=args.overwork_penalty,
        soft_cap=args.soft_cap,
        topk_swap=args.topk_swap,
        k_robust=args.k_robust,
        lambda_red=args.lambda_red,
        lambda_size=args.lambda_size,
        lambda_will=args.lambda_will,
        size_buckets=args.size_buckets,
        severity_override=args.severity,
        village_locations=args.village_locations,
        distance_csv=args.distance_csv,
        distance_scale=args.distance_scale,
        distance_decay=args.distance_decay
    )
    
    results = run_recommender(cfg)
    
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "rank", "team_ids", "team_names", "team_size", "goodness", 
            "coverage", "k_robustness", "redundancy", "set_size", 
            "willingness_avg", "willingness_min"
        ])
        w.writeheader()
        
        # FIX: 'results' is a dict, we must iterate over results['teams']
        teams_list = results.get("teams", [])
        for i, r in enumerate(teams_list, start=1):
            row = {k: v for k, v in r.items() if k != "members"}
            row["rank"] = i
            w.writerow(row)
            
    print(f"Wrote {len(results.get('teams', []))} teams to {args.out}")

if __name__ == "__main__":
    main()
