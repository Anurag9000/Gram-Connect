import os
import math
import csv
import pickle
import logging
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from embeddings import embed_with
from m3_recommend import (
    VILLAGE_FALLBACK_SKILLS,
    RecommendationConfig,
    DEFAULT_SIZE_BUCKETS,
    AVAILABILITY_LEVELS,
    SEVERITY_LABELS,
    SEVERITY_KEYWORDS,
    load_village_names,
    load_distance_lookup,
    extract_location,
    estimate_severity,
    severity_penalty,
    lookup_distance_km,
    parse_datetime,
    split_hours_by_week,
    read_people,
    parse_size_buckets,
    select_top_teams_by_size,
    _load_skills_json,
    _auto_extract_skills,
    team_metrics,
    goodness,
    parse_schedule_csv,
    intervals_overlap,
)

logger = logging.getLogger("recommender_service")


def _evaluate_team(
    required: List[str],
    team_list: List[Dict[str, Any]],
    backend: str,
    people_model,
    tau: float,
    k: int,
    lambda_red: float,
    lambda_size: float,
    lambda_will: float,
) -> Dict[str, float]:
    metrics = team_metrics(required, team_list, backend, people_model, tau=tau, k=k)
    score = goodness(metrics, lambda_red=lambda_red, lambda_size=lambda_size, lambda_will=lambda_will)
    return {"score": score, "metrics": metrics}


def _enforce_unique_members(
    teams: List[Dict[str, Any]],
    required: List[str],
    backend: str,
    people_model,
    tau: float,
    k_robust: int,
    lambda_red: float,
    lambda_size: float,
    lambda_will: float,
) -> List[Dict[str, Any]]:
    assigned: Dict[str, bool] = {}
    resolved: List[Dict[str, Any]] = []
    for team in teams:
        members = list(team.get("members", []))
        keep_members = []
        removed = False
        for member in members:
            pid = member["person_id"]
            if assigned.get(pid):
                removed = True
                continue
            keep_members.append(member)
        if not keep_members:
            continue
        updated_team = dict(team)
        updated_team["members"] = keep_members
        if removed:
            eval_res = _evaluate_team(
                required,
                keep_members,
                backend,
                people_model,
                tau,
                k_robust,
                lambda_red,
                lambda_size,
                lambda_will,
            )
            metrics = eval_res["metrics"]
            updated_team.update({
                "team_ids": ";".join([m["person_id"] for m in keep_members]),
                "team_names": "; ".join([m["name"] for m in keep_members]),
                "team_size": len(keep_members),
                "goodness": round(eval_res["score"], 4),
                "coverage": round(metrics["coverage"], 3),
                "k_robustness": round(metrics["k_robustness"], 3),
                "redundancy": round(metrics["redundancy"], 3),
                "set_size": round(metrics["set_size"], 3),
                "willingness_avg": round(metrics["willingness_avg"], 3) if "willingness_avg" in metrics else updated_team.get("willingness_avg", 0.0),
                "willingness_min": round(metrics["willingness_min"], 3) if "willingness_min" in metrics else updated_team.get("willingness_min", 0.0),
            })
        for member in keep_members:
            assigned[member["person_id"]] = True
        resolved.append(updated_team)
    return resolved


def generate_recommendations(config: RecommendationConfig, write_output: bool = False) -> Dict[str, Any]:
    logger.info("Preparing recommendation request")
    for name, path in (
        ("model", config.model),
        ("people", config.people),
        ("schedule_csv", config.schedule_csv),
        ("village_locations", config.village_locations),
        ("distance_csv", config.distance_csv),
        ("proposal_file", config.proposal_file),
    ):
        if path and not os.path.exists(path):
            raise SystemExit(f"Not found: {path} ({name})")

    text = config.proposal_text
    if config.proposal_file:
        with open(config.proposal_file, "r", encoding="utf-8") as f:
            text = f.read()
    if not text:
        raise SystemExit("proposal_text or proposal_file is required")

    village_names = load_village_names(config.village_locations)
    distance_lookup = load_distance_lookup(config.distance_csv)
    proposal_location = extract_location(text, village_names)
    if not proposal_location and config.proposal_location_override:
        proposal_location = config.proposal_location_override
    if proposal_location:
        logger.info("Detected proposal location: %s", proposal_location)
    elif village_names:
        logger.warning("Proposal text did not match known village names; distance penalty will be zero.")

    severity_override = config.severity_override.upper() if config.severity_override else None
    if severity_override:
        severity_level = {"LOW": 0, "NORMAL": 1, "HIGH": 2}[severity_override]
    else:
        severity_level = estimate_severity(text)
    severity_label = SEVERITY_LABELS.get(severity_level, "NORMAL")
    logger.info("Severity: %s (source=%s)", severity_label, "override" if severity_override else "auto")

    if not config.task_start or not config.task_end:
        raise SystemExit("task_start and task_end are required")
    task_start = parse_datetime(config.task_start, "task_start")
    task_end = parse_datetime(config.task_end, "task_end")
    if task_end <= task_start:
        raise SystemExit("task_end must be after task_start")
    task_interval = (task_start, task_end)
    task_week_hours = split_hours_by_week(task_start, task_end)
    if not task_week_hours:
        raise SystemExit("Task duration must be positive.")
    schedule_map = parse_schedule_csv(config.schedule_csv) if config.schedule_csv else {}

    with open(config.model, "rb") as f:
        bundle = pickle.load(f)
    clf = bundle["model"]
    backend = bundle["backend"]
    prop_model = bundle["prop_model"]
    people_model = bundle["people_model"]
    distance_scale = bundle.get("distance_scale", config.distance_scale)
    distance_decay = bundle.get("distance_decay", config.distance_decay)

    people = read_people(config.people)
    if not people:
        raise SystemExit("No valid rows found in people CSV.")
    filtered_people: List[Dict[str, Any]] = []
    conflicts = 0
    for person in people:
        sched_info = schedule_map.get(person["person_id"])
        intervals = sched_info.get("intervals", []) if sched_info else []
        if intervals and intervals_overlap(intervals, task_interval):
            conflicts += 1
            continue
        week_hours_map = sched_info.get("week_hours", {}) if sched_info else {}
        overwork_total = 0.0
        for week_key, hrs in task_week_hours.items():
            existing = float(week_hours_map.get(week_key, 0.0))
            total_hours = existing + hrs
            overwork_total += max(0.0, total_hours - config.weekly_quota)
        adjusted = dict(person)
        base_W = person["W"]
        penalty_overwork = config.overwork_penalty * overwork_total
        adjusted_W = max(0.0, min(1.0, base_W - penalty_overwork))
        adjusted["W_original"] = base_W
        adjusted["W_base"] = adjusted_W
        adjusted["W"] = adjusted_W
        adjusted["overwork_hours"] = overwork_total
        adjusted["availability"] = (adjusted.get("availability") or "").lower()
        filtered_people.append(adjusted)
    if conflicts:
        logger.info("Excluded %d volunteers due to overlapping assignments", conflicts)
    people = filtered_people
    if not people:
        raise SystemExit("No available volunteers after applying schedule and workload constraints.")

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

    P = embed_with(prop_model, [text], backend)
    S = embed_with(people_model, [p["text"] for p in people], backend)
    sims = cosine_similarity(P, S).ravel()
    features = []
    for idx, person in enumerate(people):
        avail_label = (person.get("availability") or "").lower()
        availability_level = AVAILABILITY_LEVELS.get(avail_label, 1)
        base_W = person.get("W_base", person["W"])
        sev_pen = severity_penalty(avail_label, severity_level)
        W_after_severity = max(0.0, min(1.0, base_W - sev_pen))
        distance_km = lookup_distance_km(person.get("home_location"), proposal_location, distance_lookup)
        distance_norm = min(distance_km / distance_scale, 1.0) if distance_scale > 0 else 0.0
        distance_penalty = math.exp(-distance_km / distance_decay) if distance_decay > 0 else 1.0
        W_adjusted = max(0.0, min(1.0, W_after_severity * distance_penalty))
        person["W"] = W_adjusted
        person["distance_km"] = distance_km
        person["distance_penalty"] = distance_penalty
        person["availability_level"] = availability_level
        person["severity_level"] = severity_level
        person["severity_penalty"] = sev_pen
        features.append([
            sims[idx],
            sims[idx] * W_adjusted,
            W_adjusted,
            distance_norm,
            distance_penalty,
            availability_level / 2.0,
            severity_level / 2.0,
        ])
    X = np.asarray(features)
    probs = clf.predict_proba(X)[:, 1]
    ranked = sorted(zip(people, probs), key=lambda x: x[1], reverse=True)

    def evaluate_team(team_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        return _evaluate_team(
            required,
            team_list,
            backend,
            people_model,
            tau=config.tau,
            k=config.k_robust,
            lambda_red=config.lambda_red,
            lambda_size=config.lambda_size,
            lambda_will=config.lambda_will,
        )

    team: List[Dict[str, Any]] = []
    team_ids = set()
    eval_current = evaluate_team(team)
    team_score = eval_current["score"]
    best_metrics = eval_current["metrics"]

    soft_cap = max(config.soft_cap, config.team_size or config.soft_cap)

    while len(team) < soft_cap:
        best_candidate = None
        best_candidate_score = None
        best_candidate_metrics = None
        best_candidate_prob = -1.0
        best_delta = 0.0
        for person, prob in ranked:
            if person["person_id"] in team_ids:
                continue
            candidate_team = team + [person]
            eval_candidate = evaluate_team(candidate_team)
            cand_score = eval_candidate["score"]
            cand_metrics = eval_candidate["metrics"]
            delta = cand_score - team_score
            if delta > best_delta + 1e-9 or (
                abs(delta - best_delta) <= 1e-9 and (
                    cand_metrics["coverage"] > (best_candidate_metrics["coverage"] if best_candidate_metrics else -1.0) or
                    (
                        abs(cand_metrics["coverage"] - (best_candidate_metrics["coverage"] if best_candidate_metrics else -1.0)) <= 1e-9
                        and prob > best_candidate_prob
                    )
                )
            ):
                best_candidate = person
                best_candidate_score = cand_score
                best_candidate_metrics = cand_metrics
                best_candidate_prob = prob
                best_delta = delta
        if best_candidate is None or best_delta <= 1e-9:
            break
        team.append(best_candidate)
        team_ids.add(best_candidate["person_id"])
        team_score = best_candidate_score
        best_metrics = best_candidate_metrics
        if best_metrics["coverage"] >= 0.999 and best_metrics["k_robustness"] >= 0.999:
            break

    def score_team(tlist: List[Dict[str, Any]]) -> Dict[str, Any]:
        eval_res = evaluate_team(tlist)
        metrics = eval_res["metrics"]
        return {
            "goodness": round(eval_res["score"], 4),
            "metrics": {
                "coverage": round(metrics["coverage"], 3),
                "k_robustness": round(metrics["k_robustness"], 3),
                "redundancy": round(metrics["redundancy"], 3),
                "set_size": round(metrics["set_size"], 3),
                "willingness_avg": round(metrics.get("willingness_avg", 0.0), 3),
                "willingness_min": round(metrics.get("willingness_min", 0.0), 3),
            },
        }

    recs: List[Dict[str, Any]] = []
    base_eval = score_team(team)
    recs.append({
        "team_ids": ";".join([m["person_id"] for m in team]),
        "team_names": "; ".join([m["name"] for m in team]),
        "team_size": len(team),
        "goodness": base_eval["goodness"],
        "coverage": base_eval["metrics"]["coverage"],
        "k_robustness": base_eval["metrics"]["k_robustness"],
        "redundancy": base_eval["metrics"]["redundancy"],
        "set_size": base_eval["metrics"]["set_size"],
        "willingness_avg": base_eval["metrics"]["willingness_avg"],
        "willingness_min": base_eval["metrics"]["willingness_min"],
        "members": list(team),
    })

    team_ids_set = {m["person_id"] for m in team}
    for person, _prob in ranked[:max(1, config.topk_swap)]:
        if person["person_id"] in team_ids_set:
            continue
        for i in range(len(team)):
            variant = team.copy()
            variant[i] = person
            eval_variant = score_team(variant)
            recs.append({
                "team_ids": ";".join([mm["person_id"] for mm in variant]),
                "team_names": "; ".join([mm["name"] for mm in variant]),
                "team_size": len(variant),
                "goodness": eval_variant["goodness"],
                "coverage": eval_variant["metrics"]["coverage"],
                "k_robustness": eval_variant["metrics"]["k_robustness"],
                "redundancy": eval_variant["metrics"]["redundancy"],
                "set_size": eval_variant["metrics"]["set_size"],
                "willingness_avg": eval_variant["metrics"]["willingness_avg"],
                "willingness_min": eval_variant["metrics"]["willingness_min"],
                "members": list(variant),
            })

    dedup = {(r["team_ids"], r["team_names"]): r for r in recs}.values()
    sorted_recs = sorted(dedup, key=lambda r: (r["goodness"], r["coverage"]), reverse=True)

    if config.size_buckets:
        size_spec = config.size_buckets
    elif config.team_size:
        limit = config.num_teams or 10
        size_spec = f"custom:{config.team_size}-{config.team_size}:{limit}"
    else:
        size_spec = DEFAULT_SIZE_BUCKETS
        if config.num_teams:
            # adjust default by overriding limits uniformly
            default_buckets = []
            for entry in DEFAULT_SIZE_BUCKETS.split(","):
                label, rng, _limit = entry.split(":")
                default_buckets.append(f"{label}:{rng}:{config.num_teams}")
            size_spec = ",".join(default_buckets)

    buckets = parse_size_buckets(size_spec)
    final = select_top_teams_by_size(sorted_recs, buckets) or sorted_recs[:config.num_teams or 10]
    final = _enforce_unique_members(
        final,
        required,
        backend,
        people_model,
        config.tau,
        config.k_robust,
        config.lambda_red,
        config.lambda_size,
        config.lambda_will,
    )

    result_payload = {
        "severity_detected": severity_label,
        "severity_source": "override" if severity_override else "auto",
        "proposal_location": proposal_location,
        "teams": [],
    }

    for team_entry in final:
        members_payload = []
        for member in team_entry.get("members", []):
            members_payload.append({
                "person_id": member.get("person_id"),
                "name": member.get("name"),
                "skills": member.get("skills", []),
                "availability": member.get("availability"),
                "willingness": round(member.get("W", 0.0), 3),
                "distance_km": member.get("distance_km"),
                "overwork_hours": round(member.get("overwork_hours", 0.0), 2),
                "severity_penalty": member.get("severity_penalty"),
                "distance_penalty": round(member.get("distance_penalty", 1.0), 3) if member.get("distance_penalty") is not None else None,
            })
        payload_team = {
            "team_ids": team_entry["team_ids"],
            "team_names": team_entry["team_names"],
            "team_size": team_entry["team_size"],
            "goodness": team_entry["goodness"],
            "coverage": team_entry["coverage"],
            "k_robustness": team_entry["k_robustness"],
            "redundancy": team_entry["redundancy"],
            "set_size": team_entry["set_size"],
            "willingness_avg": team_entry["willingness_avg"],
            "willingness_min": team_entry["willingness_min"],
            "members": members_payload,
        }
        result_payload["teams"].append(payload_team)

    if write_output and config.out:
        logger.info("Writing results to %s", config.out)
        csv_rows = []
        for team in result_payload["teams"]:
            row = dict(team)
            row.pop("members", None)
            csv_rows.append(row)
        fieldnames = ["team_ids","team_names","team_size","goodness","coverage","k_robustness","redundancy","set_size","willingness_avg","willingness_min"]
        with open(config.out, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["rank"] + fieldnames)
            writer.writeheader()
            for idx, row in enumerate(csv_rows, start=1):
                writer.writerow({"rank": idx, **row})
    return result_payload

