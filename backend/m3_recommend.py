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
    --model model.pkl `
    --people people.csv `
    --proposal_text "village drains blocked; handpump broken; need toilets and awareness" `
    --out teams_m3.csv `
    --tau 0.35 --soft_cap 6 `
    --auto_extract --threshold 0.20

Or if you already have a skills JSON:
  python m3_recommend.py --model model.pkl --people people.csv --proposal_text "..." --skills_json skills.json --out teams_m3.csv
"""

import argparse, csv, json, pickle, math, os, re, logging
from dataclasses import dataclass
from typing import List, Dict, Tuple, Any, Optional
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from embeddings import embed_with
from datetime import datetime, timedelta, timezone
from collections import defaultdict

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
    if not team_members:
        return 0.0
    _, per_req_best, _ = similarity_coverage(required, team_members, backend, model_or_vec, tau)
    if not all(v >= tau for v in per_req_best.values()):
        return 0.0
    n = len(team_members)
    if n == 0:
        return 0.0
    k = max(1, min(k, n - 1 if n > 1 else 1)) # Can't remove all members if n=1
    import itertools, random
    subsets = []
    for r in range(1, k + 1):
        combs = list(itertools.combinations(range(n), r))
        subsets.extend(combs)
        if len(subsets) > sample_limit:
            break
    if len(subsets) > sample_limit:
        random.seed(42)
        subsets = random.sample(subsets, sample_limit)
    ok = 0
    for rem in subsets:
        sub_members = [m for i, m in enumerate(team_members) if i not in rem]
        _, per_req_best2, _ = similarity_coverage(required, sub_members, backend, model_or_vec, tau)
        if all(v >= tau for v in per_req_best2.values()):
            ok += 1
    return ok / len(subsets) if subsets else 0.0

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
    s = (
        (+1) * metrics["coverage"]
        + (+1) * metrics["k_robustness"]
        + lambda_will * metrics["willingness_avg"]
        - lambda_red * metrics["redundancy"]
        - lambda_size * metrics["set_size"]
    )
    return (s + 2.0) / 4.0

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

def _auto_extract_skills(text: str, threshold: float) -> List[str]:
    try:
        import embed_skills_extractor as ex
        return ex.extract_skills_embed(text, topk_per_sentence=7, threshold=threshold)
    except Exception:
        t = (text or "").lower()
        keys = ["village","gram","panchayat","ward","toilet","drain","waste","river","water",
                "anganwadi","school","handpump","borewell","harvesting","mgnrega","shg",
                "pmay","health","nutrition","road","culvert","solar","gis","survey","iot"]
        if any(k in t for k in keys):
            base = [
                "drainage design and de-silting",
                "handpump repair and maintenance",
                "toilet construction and retrofitting",
                "solid waste segregation and composting",
                "water quality assessment",
                "rainwater harvesting",
                "watershed management",
                "soil testing and fertility management",
                "panchayat planning and budgeting",
                "self-help group formation and strengthening",
                "public health outreach",
                "education and digital literacy",
                "gis and remote sensing",
                "data analysis and reporting",
                "project management",
            ]
            return base
        return VILLAGE_FALLBACK_SKILLS[:12]

# ------------------------ main ---------------------

def run_recommender(config: RecommendationConfig) -> List[Dict[str, Any]]:
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

    # 2. Load model bundle
    if config.loaded_bundle:
        bundle = config.loaded_bundle
    elif not os.path.exists(config.model):
        raise FileNotFoundError(f"Model file not found: {config.model}")
    else:
        with open(config.model, "rb") as f:
            bundle = pickle.load(f)
    clf = bundle["model"]
    backend = bundle["backend"]
    prop_model = bundle["prop_model"]
    people_model = bundle["people_model"]
    distance_scale = bundle.get("distance_scale", config.distance_scale)
    distance_decay = bundle.get("distance_decay", config.distance_decay)

    # 3. Process Volunteers (People)
    all_people = read_people(config.people)
    if not all_people:
        raise ValueError("No valid volunteers found in people data.")
    
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
        p.update({
            "W": W_final,
            "distance_km": dist_km,
            "distance_penalty": dist_pen,
            "availability_level": avail_level,
            "severity_level": severity_level,
            "severity_penalty": sev_pen
        })
        features.append([
            sims[idx],
            sims[idx] * W_final,
            W_final,
            dist_norm,
            dist_pen,
            avail_level / 2.0,
            severity_level / 2.0
        ])
        
    probs = clf.predict_proba(np.asarray(features))[:, 1]
    ranked = sorted(zip(filtered_people, probs), key=lambda x: x[1], reverse=True)

    # 6. Team Building logic
    def evaluate(tlist):
        mets = team_metrics(required, tlist, backend, people_model, tau=config.tau, k=config.k_robust)
        score = goodness(mets, lambda_red=config.lambda_red, lambda_size=config.lambda_size, lambda_will=config.lambda_will)
        return score, mets

    team: List[Dict] = []
    team_ids = set()
    best_score, _ = evaluate(team)
    soft_cap = config.team_size or config.soft_cap

    while len(team) < soft_cap:
        best_cand, best_cand_score, best_cand_mets, best_cand_prob = None, -1.0, None, -1.0
        best_delta = 0.0
        for p, prob in ranked:
            if p["person_id"] in team_ids: continue
            cand_score, cand_mets = evaluate(team + [p])
            delta = cand_score - best_score
            if delta > best_delta + 1e-9 or (abs(delta - best_delta) <= 1e-9 and prob > best_cand_prob):
                best_cand, best_cand_score, best_cand_mets, best_cand_prob, best_delta = p, cand_score, cand_mets, prob, delta
        if not best_cand or best_delta <= 1e-9: break
        team.append(best_cand)
        team_ids.add(best_cand["person_id"])
        best_score = best_cand_score
        if best_cand_mets["coverage"] >= 0.999 and best_cand_mets["k_robustness"] >= 0.999: break

    # 7. Variants & Consolidation
    recs = []
    def add_rec(tlist):
        g, m = evaluate(tlist)
        recs.append({
            "team_ids": ";".join([mm["person_id"] for mm in tlist]),
            "team_names": "; ".join([mm["name"] for mm in tlist]),
            "team_size": len(tlist),
            "goodness": round(g, 4),
            "coverage": round(m["coverage"], 3),
            "k_robustness": round(m["k_robustness"], 3),
            "redundancy": round(m["redundancy"], 3),
            "set_size": round(m["set_size"], 3),
            "willingness_avg": round(m["willingness_avg"], 3),
            "willingness_min": round(m["willingness_min"], 3),
            "members": list(tlist)
        })

    add_rec(team)
    tids_set = {m["person_id"] for m in team}
    for p, _ in ranked[:max(1, config.topk_swap)]:
        if p["person_id"] in tids_set: continue
        for i in range(len(team)):
            variant = list(team)
            variant[i] = p
            add_rec(variant)

    dedup = {(r['team_ids'], r['team_names']): r for r in recs}.values()
    sorted_recs = sorted(dedup, key=lambda r: (r["goodness"], r["coverage"]), reverse=True)
    buckets = parse_size_buckets(config.size_buckets)
    final = select_top_teams_by_size(sorted_recs, buckets) or sorted_recs[:10]

    # Enforce unique volunteers across recommendations
    assigned_global = set()
    resolved = []
    for r in final:
        keep = [m for m in r["members"] if m["person_id"] not in assigned_global]
        if not keep: 
            continue
            
        # If we removed members, we MUST recalculate the goodness score
        if len(keep) < len(r["members"]):
            g, m = evaluate(keep)
            r = dict(r)
            r.update({
                "members": keep,
                "team_ids": ";".join([mm["person_id"] for mm in keep]),
                "team_names": "; ".join([mm.get("name", "Volunteer") for mm in keep]),
                "team_size": len(keep),
                "goodness": round(g, 4),
                "coverage": round(m["coverage"], 3),
                "k_robustness": round(m["k_robustness"], 3),
                "redundancy": round(m["redundancy"], 3),
                "set_size": round(m["set_size"], 3),
                "willingness_avg": round(m["willingness_avg"], 3),
                "willingness_min": round(m["willingness_min"], 3)
            })
        
        # Check if the team is still "good enough" after removals
        if len(resolved) > 0 and r["goodness"] < 0.2: # Example threshold
             continue

        for m in keep: 
            assigned_global.add(m["person_id"])
        resolved.append(r)
    
    # Add rank
    for i, r in enumerate(resolved, start=1):
        r["rank"] = i

    return {
        "severity_detected": SEVERITY_LABELS.get(severity_level, "NORMAL"),
        "severity_source": "override" if config.severity_override else "auto",
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
    
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    default_root = os.path.join(backend_dir, "..", "data")
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
        for i, r in enumerate(results, start=1):
            row = {k: v for k, v in r.items() if k != "members"}
            row["rank"] = i
            w.writerow(row)
            
    print(f"Wrote {len(results)} teams to {args.out}")

if __name__ == "__main__":
    main()
