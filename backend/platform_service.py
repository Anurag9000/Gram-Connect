from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from insights_service import find_duplicate_problem_candidates, infer_problem_triage


def _now() -> datetime:
    return datetime.now()


def _now_iso() -> str:
    return _now().isoformat()


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
    except Exception:
        return None


def _problem_text(problem: Dict[str, Any]) -> str:
    tags = " ".join(problem.get("visual_tags") or [])
    return " ".join(
        str(part or "")
        for part in [
            problem.get("title"),
            problem.get("description"),
            problem.get("category"),
            problem.get("village_name"),
            tags,
        ]
        if part
    ).strip()


def _category_to_asset_type(problem: Dict[str, Any]) -> str:
    text = _problem_text(problem).lower()
    category = str(problem.get("category") or "").lower()
    mapping = [
        ("water", ["pump", "handpump", "pipe", "water", "drain", "tap"]),
        ("solar", ["solar", "inverter", "battery", "panel"]),
        ("road", ["road", "pothole", "street", "drainage", "culvert"]),
        ("health", ["fever", "mosquito", "health", "clinic", "medicine"]),
        ("school", ["school", "classroom", "teacher", "education"]),
        ("sanitation", ["toilet", "sanitation", "sewage", "waste"]),
    ]
    for asset_type, keywords in mapping:
        if any(keyword in text for keyword in keywords):
            return asset_type
    if "infrastructure" in category:
        return "infrastructure"
    if "health" in category:
        return "health"
    if "water" in category:
        return "water"
    return "general"


def build_asset_registry(problems: Sequence[Dict[str, Any]], days_back: int = 365) -> Dict[str, Any]:
    cutoff = _now() - timedelta(days=max(1, days_back))
    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for problem in problems:
        created = _parse_dt(problem.get("created_at") or problem.get("updated_at"))
        if created and created < cutoff:
            continue
        groups[(str(problem.get("village_name") or "Unknown"), _category_to_asset_type(problem))].append(problem)

    assets: List[Dict[str, Any]] = []
    for (village_name, asset_type), items in sorted(groups.items()):
        open_items = [item for item in items if item.get("status") != "completed"]
        latest_update = max((_parse_dt(item.get("updated_at") or item.get("created_at")) or _now()) for item in items)
        assets.append({
            "asset_id": f"asset-{village_name.lower()}-{asset_type}",
            "village_name": village_name,
            "asset_type": asset_type,
            "status": "needs_attention" if open_items else "healthy",
            "problem_count": len(items),
            "open_problem_count": len(open_items),
            "last_seen_at": latest_update.isoformat(),
            "next_inspection_days": 14 if asset_type in {"water", "health"} else 30,
            "recommended_action": f"Inspect {asset_type} assets in {village_name}" if open_items else f"Keep {asset_type} asset records current in {village_name}",
            "example_problem_ids": [item.get("id") for item in items[:3]],
        })
    return {
        "generated_at": _now_iso(),
        "window_days": days_back,
        "summary": f"Tracked {len(assets)} asset groups across the selected window.",
        "assets": assets,
    }


def build_procurement_tracker(problems: Sequence[Dict[str, Any]], days_back: int = 180) -> Dict[str, Any]:
    asset_registry = build_asset_registry(problems, days_back=days_back)["assets"]
    rows: List[Dict[str, Any]] = []
    for asset in asset_registry:
        if asset["open_problem_count"] == 0:
            continue
        item_name = {
            "water": "seal tape and pump washers",
            "solar": "fuses and inverter spares",
            "road": "patch material and gravel",
            "health": "diagnostic strips and mosquito control supplies",
            "sanitation": "cleaning supplies and pipe couplers",
        }.get(asset["asset_type"], "basic repair consumables")
        rows.append({
            "procurement_id": f"proc-{asset['asset_id']}",
            "village_name": asset["village_name"],
            "asset_type": asset["asset_type"],
            "item_name": item_name,
            "priority": "high" if asset["open_problem_count"] > 1 else "normal",
            "quantity_estimate": max(1, asset["open_problem_count"]),
            "vendor_hint": "local hardware shop or approved supplier",
            "cost_estimate": round(250.0 + 150.0 * asset["open_problem_count"], 2),
            "delivery_eta_days": 7 if asset["asset_type"] in {"water", "health"} else 14,
            "status": "pending_approval",
            "reason": f"{asset['open_problem_count']} open cases linked to {asset['asset_type']} assets.",
        })
    return {
        "generated_at": _now_iso(),
        "window_days": days_back,
        "summary": f"{len(rows)} procurement items inferred from unresolved asset groups.",
        "items": rows,
    }


def build_district_hierarchy(problems: Sequence[Dict[str, Any]], villages: Sequence[Dict[str, Any]], days_back: int = 365) -> Dict[str, Any]:
    village_map = {str(row.get("village_name") or row.get("name") or ""): row for row in villages}
    buckets: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for problem in problems:
        village_name = str(problem.get("village_name") or "Unknown")
        village_row = village_map.get(village_name, {})
        district = str(village_row.get("district") or "Unknown district")
        state = str(village_row.get("state") or "Unknown state")
        buckets[(state, district)].append(problem)
    districts = []
    for (state, district), items in sorted(buckets.items()):
        districts.append({
            "state": state,
            "district": district,
            "problem_count": len(items),
            "open_count": sum(1 for item in items if item.get("status") != "completed"),
            "top_villages": Counter(str(item.get("village_name") or "Unknown") for item in items).most_common(3),
            "top_topics": Counter(_category_to_asset_type(item) for item in items).most_common(3),
        })
    return {"generated_at": _now_iso(), "window_days": days_back, "districts": districts, "summary": f"Rolled up {len(districts)} district buckets."}


def build_work_order_templates() -> List[Dict[str, Any]]:
    templates = {
        "water": ("Handpump / pipe work order", ["Isolate water line", "Inspect washers", "Tighten joint", "Verify flow"]),
        "solar": ("Solar inverter work order", ["Disconnect load", "Check fuse", "Inspect battery", "Test output"]),
        "road": ("Road repair work order", ["Mark hazard", "Clear debris", "Patch damage", "Re-check drainage"]),
        "health": ("Health response work order", ["Notify health worker", "Inspect standing water", "Escalate if cluster grows"]),
        "sanitation": ("Sanitation work order", ["Check pipe routing", "Clear blockage", "Disinfect area"]),
        "general": ("General issue work order", ["Assess issue", "Collect evidence", "Assign follow-up"]),
    }
    return [
        {
            "template_id": f"template-{topic}",
            "topic": topic,
            "title": title,
            "steps": steps,
            "approval_steps": ["Coordinator review", "Field confirmation"],
        }
        for topic, (title, steps) in templates.items()
    ]


def assess_proof_spoofing(problem: Dict[str, Any]) -> Dict[str, Any]:
    proof = problem.get("proof") or {}
    before_id = proof.get("before_media_id")
    after_id = proof.get("after_media_id")
    suspicious = []
    if before_id and after_id and before_id == after_id:
        suspicious.append("before_and_after_use_same_media")
    if not before_id or not after_id:
        suspicious.append("missing_before_or_after_media")
    confidence = 0.95 if suspicious else 0.15
    return {
        "problem_id": problem.get("id"),
        "accepted": not suspicious,
        "confidence": round(confidence, 3),
        "signals": suspicious,
        "summary": "Potential spoofing or low-trust proof." if suspicious else "No obvious spoofing signals detected.",
        "recommendation": "Request fresh geo-tagged photos" if suspicious else "Accept proof and notify resident.",
    }


def build_resident_confirmation(problem: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "problem_id": problem.get("id"),
        "prompt": f"Please confirm whether {problem.get('title')} is fixed.",
        "options": ["resolved", "still_broken", "needs_more_help"],
        "default_source": "public-board",
        "follow_up_window_days": 3,
    }


def build_audit_pack(problem: Dict[str, Any], timeline: Sequence[Dict[str, Any]], learning_events: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "problem": problem,
        "timeline": list(timeline),
        "learning_events": list(learning_events),
        "media_ids": list(problem.get("media_ids") or []),
        "duplicate_reports": list(problem.get("duplicate_reports") or []),
        "generated_at": _now_iso(),
    }


def build_skill_certifications(volunteers: Sequence[Dict[str, Any]], problems: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    skills = Counter()
    for volunteer in volunteers:
        for skill in volunteer.get("skills") or []:
            skills[str(skill).strip().lower()] += 1
    certs: List[Dict[str, Any]] = []
    for volunteer in volunteers:
        skill_list = [str(skill).strip() for skill in volunteer.get("skills") or [] if str(skill).strip()]
        badges = []
        for skill in skill_list:
            topic = skill.lower()
            completed = sum(1 for problem in problems if topic in _problem_text(problem).lower() and problem.get("status") == "completed")
            badges.append({
                "skill": skill,
                "level": "verified" if completed >= 1 else "in_progress",
                "completed_cases": completed,
            })
        certs.append({
            "volunteer_id": volunteer.get("id") or volunteer.get("user_id"),
            "name": (volunteer.get("profiles") or volunteer.get("profile") or {}).get("full_name") or volunteer.get("full_name") or volunteer.get("id"),
            "badges": badges,
        })
    return certs


def build_shift_plan(volunteers: Sequence[Dict[str, Any]], problems: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    open_problems = [problem for problem in problems if problem.get("status") != "completed"]
    plan: List[Dict[str, Any]] = []
    for index, volunteer in enumerate(volunteers):
        plan.append({
            "shift_id": f"shift-{index + 1}",
            "volunteer_id": volunteer.get("id") or volunteer.get("user_id"),
            "name": (volunteer.get("profiles") or volunteer.get("profile") or {}).get("full_name") or volunteer.get("full_name"),
            "window": "09:00-13:00" if index % 2 == 0 else "14:00-18:00",
            "assigned_problem_ids": [problem.get("id") for problem in open_problems[index::max(1, len(volunteers))][:3]],
        })
    return plan


def build_training_mode() -> List[Dict[str, Any]]:
    return [
        {"module_id": "training-intake", "title": "Reporting quality", "quiz": ["Capture location", "Add photos", "Explain urgency"]},
        {"module_id": "training-proof", "title": "Proof and confirmation", "quiz": ["Before and after", "Resident confirmation", "Safety checks"]},
        {"module_id": "training-safety", "title": "Field safety", "quiz": ["Stop conditions", "Electrical hazards", "Water contamination"]},
    ]


def assess_burnout_signals(volunteers: Sequence[Dict[str, Any]], problems: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for volunteer in volunteers:
        vid = volunteer.get("id") or volunteer.get("user_id")
        assigned = [problem for problem in problems if any((match.get("volunteer_id") == vid or match.get("volunteers", {}).get("id") == vid) for match in (problem.get("matches") or []))]
        reopen_count = sum(1 for problem in assigned if len(problem.get("duplicate_reports") or []) > 0)
        score = min(1.0, 0.2 * len(assigned) + 0.15 * reopen_count)
        rows.append({
            "volunteer_id": vid,
            "name": (volunteer.get("profiles") or volunteer.get("profile") or {}).get("full_name") or volunteer.get("full_name") or vid,
            "assignment_count": len(assigned),
            "reopen_count": reopen_count,
            "burnout_score": round(score, 3),
            "signal": "high" if score >= 0.7 else "medium" if score >= 0.35 else "low",
        })
    return rows


def build_suggestion_box(records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return list(records)


def build_community_polls(records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return list(records)


def build_announcement_feed(records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return list(records)


def build_village_champions(records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return list(records)


def build_impact_measurement(problems: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(problems)
    completed = sum(1 for problem in problems if problem.get("status") == "completed")
    reopened = sum(1 for problem in problems if len(problem.get("duplicate_reports") or []) > 0)
    avg_resolution = []
    for problem in problems:
        proof = problem.get("proof") or {}
        submitted = _parse_dt(proof.get("submitted_at"))
        created = _parse_dt(problem.get("created_at"))
        if submitted and created:
            avg_resolution.append((submitted - created).total_seconds() / 3600.0)
    return {
        "generated_at": _now_iso(),
        "summary": f"{completed} of {total} issues are resolved in the current view.",
        "closure_rate": round(completed / total, 3) if total else 0.0,
        "reopen_rate": round(reopened / total, 3) if total else 0.0,
        "avg_resolution_hours": round(sum(avg_resolution) / len(avg_resolution), 2) if avg_resolution else None,
    }


def build_ab_test_plan(problems: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    counts = Counter(_category_to_asset_type(problem) for problem in problems)
    return [
        {
            "test_id": f"ab-{topic}",
            "topic": topic,
            "variant_a": "standard dispatch",
            "variant_b": "duplicate-aware dispatch",
            "observed_cases": count,
            "recommendation": "Prefer the variant with fewer reopenings and faster closure in this topic.",
        }
        for topic, count in counts.most_common()
    ]


def build_anomaly_dashboard(problems: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    counts = Counter((str(problem.get("village_name") or "Unknown"), _category_to_asset_type(problem)) for problem in problems if problem.get("status") != "completed")
    rows = []
    for (village_name, topic), count in counts.items():
        if count < 2:
            continue
        rows.append({
            "anomaly_id": f"anom-{village_name.lower()}-{topic}",
            "village_name": village_name,
            "topic": topic,
            "count": count,
            "signal": "spike" if count >= 4 else "cluster",
            "note": f"Repeated open {topic} issues detected in {village_name}.",
        })
    return sorted(rows, key=lambda row: row["count"], reverse=True)


def build_budget_forecast(problems: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    counts = Counter(_category_to_asset_type(problem) for problem in problems if problem.get("status") != "completed")
    rows = []
    total = 0.0
    for topic, count in counts.items():
        cost = 500.0 + count * 250.0
        total += cost
        rows.append({
            "topic": topic,
            "expected_items": count,
            "estimated_budget": round(cost, 2),
        })
    return {
        "generated_at": _now_iso(),
        "summary": "Forecast links open work to likely spend.",
        "total_estimated_budget": round(total, 2),
        "topics": rows,
    }


def autofill_problem_form(text: str, village_name: Optional[str] = None) -> Dict[str, Any]:
    lowered = (text or "").lower()
    category = "water-sanitation" if any(word in lowered for word in ["pump", "water", "tap", "pipe"]) else "infrastructure"
    severity = "HIGH" if any(word in lowered for word in ["outbreak", "leak", "broken", "collapsed", "danger"]) else "NORMAL"
    title = text.split(".")[0][:80].strip() if text else "Reported issue"
    return {
        "title": title or "Reported issue",
        "description": text,
        "category": category,
        "severity": severity,
        "village_name": village_name,
        "suggested_tags": [tag for tag in ["water", "handpump", "health", "road"] if tag in lowered],
    }


def find_case_similarity_explorer(problem: Dict[str, Any], problems: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    duplicates = find_duplicate_problem_candidates(
        problems,
        title=problem.get("title") or "",
        description=problem.get("description") or "",
        village_name=problem.get("village_name"),
        category=problem.get("category"),
        visual_tags=list(problem.get("visual_tags") or []),
        transcript=problem.get("transcript"),
        limit=5,
    )
    return {
        "problem_id": problem.get("id"),
        "summary": f"Found {len(duplicates)} earlier cases that look similar.",
        "matches": duplicates,
    }


def build_conversation_memory(memory_rows: Sequence[Dict[str, Any]], user_id: Optional[str] = None) -> Dict[str, Any]:
    rows = [row for row in memory_rows if not user_id or row.get("owner_id") == user_id]
    rows.sort(key=lambda row: row.get("updated_at") or "", reverse=True)
    return {
        "owner_id": user_id,
        "summary": f"Remembering {len(rows)} prior prompts and context items.",
        "items": rows[:20],
    }


def answer_policy_question(question: str) -> Dict[str, Any]:
    lowered = question.lower()
    if "privacy" in lowered or "public" in lowered:
        answer = "Keep public views limited to non-sensitive status, counts, and general progress."
    elif "escalation" in lowered or "sla" in lowered:
        answer = "Escalate unresolved HIGH-severity items first, then aging NORMAL items, and document every step."
    elif "procurement" in lowered or "budget" in lowered:
        answer = "Require a clear asset link, estimated cost, and approval path before procurement."
    else:
        answer = "Follow the standard operating playbook, then record the outcome and any resident feedback."
    return {"question": question, "answer": answer, "generated_at": _now_iso()}


def build_custom_forms_bundle(records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return list(records)


def build_webhook_events(records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return list(records)


def build_bulk_export_bundle(problems: Sequence[Dict[str, Any]], volunteers: Sequence[Dict[str, Any]], platform_records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "generated_at": _now_iso(),
        "problems": list(problems),
        "volunteers": list(volunteers),
        "platform_records": list(platform_records),
    }


def _string_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
        except Exception:
            parsed = None
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
        return [part.strip() for part in stripped.split(",") if part.strip()]
    item = str(value).strip()
    return [item] if item else []


def _normalize_broadcast_record(record: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(record.get("data") or {})
    return {
        "id": record.get("id"),
        "record_type": record.get("record_type") or "broadcast",
        "subtype": record.get("subtype") or data.get("event_type") or data.get("audience_type"),
        "owner_id": record.get("owner_id"),
        "status": record.get("status") or data.get("delivery_state") or "sent",
        "title": data.get("title") or data.get("name") or "Broadcast",
        "message": data.get("message") or data.get("body") or "",
        "event_type": data.get("event_type") or record.get("subtype") or "general",
        "audience_type": data.get("audience_type") or "all",
        "tags": _string_list(data.get("tags")),
        "target_villages": _string_list(data.get("target_villages")),
        "target_volunteers": _string_list(data.get("target_volunteers")),
        "target_skills": _string_list(data.get("target_skills")),
        "media_ids": _string_list(data.get("media_ids")),
        "scheduled_for": data.get("scheduled_for"),
        "created_at": data.get("created_at") or record.get("updated_at"),
        "updated_at": record.get("updated_at"),
    }


def build_broadcast_feed(
    records: Sequence[Dict[str, Any]],
    *,
    scope: str = "all",
    village_name: Optional[str] = None,
    volunteer_id: Optional[str] = None,
    volunteer_skills: Optional[Sequence[str]] = None,
    tags: Optional[Sequence[str]] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    normalized = [_normalize_broadcast_record(record) for record in records]
    skill_set = {str(skill).strip().lower() for skill in (volunteer_skills or []) if str(skill).strip()}
    tag_set = {str(tag).strip().lower() for tag in (tags or []) if str(tag).strip()}
    filtered: List[Dict[str, Any]] = []
    for row in sorted(normalized, key=lambda item: str(item.get("created_at") or item.get("updated_at") or ""), reverse=True):
        audience_type = str(row.get("audience_type") or "all").lower()
        target_villages = {str(item).strip() for item in row.get("target_villages") or [] if str(item).strip()}
        target_volunteers = {str(item).strip() for item in row.get("target_volunteers") or [] if str(item).strip()}
        target_skills = {str(item).strip().lower() for item in row.get("target_skills") or [] if str(item).strip()}
        row_tags = {str(item).strip().lower() for item in row.get("tags") or [] if str(item).strip()}

        if tag_set and not tag_set.intersection(row_tags):
            continue

        if scope == "villages":
            if audience_type not in {"all", "villages"}:
                continue
            if village_name and target_villages and village_name not in target_villages:
                continue
        elif scope == "volunteers":
            if audience_type not in {"all", "volunteers"}:
                continue
            volunteer_match = bool(volunteer_id and volunteer_id in target_volunteers)
            skill_match = bool(skill_set and target_skills and skill_set.intersection(target_skills))
            generic_volunteer = not target_volunteers and not target_skills
            if not (volunteer_match or skill_match or generic_volunteer):
                continue
        filtered.append(row)

    filtered = filtered[: max(1, int(limit))]
    return {
        "generated_at": _now_iso(),
        "window_days": None,
        "scope": scope,
        "summary": f"{len(filtered)} broadcasts ready for the selected view.",
        "items": filtered,
    }


def build_resident_feedback_summary(
    problems: Sequence[Dict[str, Any]],
    feedback_rows: Sequence[Dict[str, Any]],
    volunteers: Sequence[Dict[str, Any]],
    *,
    days_back: int = 90,
) -> Dict[str, Any]:
    cutoff = _now() - timedelta(days=max(1, days_back))
    def _volunteer_name(record: Optional[Dict[str, Any]], fallback: str) -> str:
        if not record:
            return fallback
        profile = record.get("profiles") or record.get("profile") or {}
        if isinstance(profile, dict):
            return str(profile.get("full_name") or "").strip() or str(record.get("full_name") or "").strip() or fallback
        return str(record.get("full_name") or "").strip() or fallback

    volunteer_lookup = {}
    for volunteer in volunteers:
        vid = str(volunteer.get("id") or volunteer.get("user_id") or "").strip()
        if not vid:
            continue
        volunteer_lookup[vid] = volunteer

    problem_lookup = {str(problem.get("id") or ""): problem for problem in problems if problem.get("id")}
    rows: List[Dict[str, Any]] = []
    for feedback in feedback_rows:
        created_at = _parse_dt(feedback.get("created_at"))
        if created_at and created_at < cutoff:
            continue
        data = dict(feedback.get("data") or {})
        problem_id = str(feedback.get("problem_id") or data.get("problem_id") or "").strip()
        problem = problem_lookup.get(problem_id, {})
        volunteer_id = str(data.get("volunteer_id") or feedback.get("volunteer_id") or "").strip()
        if not volunteer_id:
            proof = problem.get("proof") or {}
            volunteer_id = str(proof.get("volunteer_id") or "").strip()
        if not volunteer_id:
            matches = problem.get("matches") or []
            for match in reversed(matches):
                candidate = str(match.get("volunteer_id") or match.get("volunteer", {}).get("id") or match.get("volunteers", {}).get("id") or "").strip()
                if candidate:
                    volunteer_id = candidate
                    break

        rating = data.get("rating")
        try:
            rating_value = float(rating) if rating is not None else None
        except Exception:
            rating_value = None

        rows.append({
            "id": feedback.get("id"),
            "problem_id": problem_id,
            "problem_title": problem.get("title") or problem_id,
            "village_name": problem.get("village_name") or "Unknown",
            "volunteer_id": volunteer_id or None,
            "volunteer_name": _volunteer_name(volunteer_lookup.get(volunteer_id), volunteer_id or "Unknown"),
            "response": feedback.get("response"),
            "rating": rating_value,
            "note": data.get("note"),
            "source": feedback.get("source"),
            "created_at": feedback.get("created_at"),
        })

    response_counts = Counter(row["response"] for row in rows)
    ratings = [row["rating"] for row in rows if isinstance(row.get("rating"), (int, float))]
    volunteer_buckets: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "volunteer_id": None,
        "volunteer_name": None,
        "feedback_count": 0,
        "resolved_count": 0,
        "still_broken_count": 0,
        "needs_more_help_count": 0,
        "rating_total": 0.0,
        "rated_count": 0,
        "latest_feedback_at": None,
    })
    village_buckets: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "village_name": None,
        "feedback_count": 0,
        "resolved_count": 0,
        "still_broken_count": 0,
        "needs_more_help_count": 0,
        "rating_total": 0.0,
        "rated_count": 0,
    })

    for row in rows:
        volunteer_id = row.get("volunteer_id") or "unknown"
        volunteer_bucket = volunteer_buckets[volunteer_id]
        volunteer_bucket["volunteer_id"] = row.get("volunteer_id")
        volunteer_bucket["volunteer_name"] = row.get("volunteer_name")
        volunteer_bucket["feedback_count"] += 1
        volunteer_bucket[f"{row['response']}_count"] += 1
        if isinstance(row.get("rating"), (int, float)):
            volunteer_bucket["rating_total"] += float(row["rating"])
            volunteer_bucket["rated_count"] += 1
        if row.get("created_at") and (
            volunteer_bucket["latest_feedback_at"] is None or str(row["created_at"]) > str(volunteer_bucket["latest_feedback_at"])
        ):
            volunteer_bucket["latest_feedback_at"] = row["created_at"]

        village_name = row.get("village_name") or "Unknown"
        village_bucket = village_buckets[village_name]
        village_bucket["village_name"] = village_name
        village_bucket["feedback_count"] += 1
        village_bucket[f"{row['response']}_count"] += 1
        if isinstance(row.get("rating"), (int, float)):
            village_bucket["rating_total"] += float(row["rating"])
            village_bucket["rated_count"] += 1

    volunteer_rows = []
    for item in volunteer_buckets.values():
        rated_count = int(item["rated_count"] or 0)
        volunteer_rows.append({
            "volunteer_id": item["volunteer_id"],
            "volunteer_name": item["volunteer_name"],
            "feedback_count": item["feedback_count"],
            "resolved_count": item["resolved_count"],
            "still_broken_count": item["still_broken_count"],
            "needs_more_help_count": item["needs_more_help_count"],
            "average_rating": round(item["rating_total"] / rated_count, 2) if rated_count else None,
            "latest_feedback_at": item["latest_feedback_at"],
        })
    volunteer_rows.sort(key=lambda row: (row["average_rating"] is None, -(row["average_rating"] or 0), -row["feedback_count"]))

    village_rows = []
    for item in village_buckets.values():
        rated_count = int(item["rated_count"] or 0)
        village_rows.append({
            "village_name": item["village_name"],
            "feedback_count": item["feedback_count"],
            "resolved_count": item["resolved_count"],
            "still_broken_count": item["still_broken_count"],
            "needs_more_help_count": item["needs_more_help_count"],
            "average_rating": round(item["rating_total"] / rated_count, 2) if rated_count else None,
        })
    village_rows.sort(key=lambda row: (row["average_rating"] is None, -(row["average_rating"] or 0), -row["feedback_count"]))

    return {
        "generated_at": _now_iso(),
        "window_days": days_back,
        "summary": f"Captured {len(rows)} resident feedback entries across {len(volunteer_rows)} volunteers.",
        "total_feedback": len(rows),
        "response_counts": {
            "resolved": response_counts.get("resolved", 0),
            "still_broken": response_counts.get("still_broken", 0),
            "needs_more_help": response_counts.get("needs_more_help", 0),
        },
        "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
        "volunteers": volunteer_rows,
        "villages": village_rows,
        "recent_feedback": rows[:20],
    }


def build_repeat_breakdown_metrics(problems: Sequence[Dict[str, Any]], *, days_back: int = 90) -> Dict[str, Any]:
    cutoff = _now() - timedelta(days=max(1, days_back))
    by_village: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    by_topic: Counter[str] = Counter()
    repeat_counts: Counter[str] = Counter()
    gap_days: List[float] = []

    for problem in problems:
        created_at = _parse_dt(problem.get("created_at") or problem.get("updated_at"))
        if created_at and created_at < cutoff:
            continue
        village_name = str(problem.get("village_name") or "Unknown")
        topic = _category_to_asset_type(problem)
        by_village[village_name].append(problem)
        by_topic[topic] += 1

    village_rows: List[Dict[str, Any]] = []
    for village_name, items in by_village.items():
        ordered = sorted(items, key=lambda item: _parse_dt(item.get("created_at") or item.get("updated_at")) or _now())
        topic_counts = Counter(_category_to_asset_type(item) for item in ordered)
        repeat_count = sum(max(0, count - 1) for count in topic_counts.values())
        repeat_counts[village_name] = repeat_count
        intervals = []
        previous_created = None
        for item in ordered:
            current_created = _parse_dt(item.get("created_at") or item.get("updated_at"))
            if previous_created and current_created:
                interval = max(0.0, (current_created - previous_created).total_seconds() / 86400.0)
                intervals.append(interval)
                gap_days.append(interval)
            if current_created:
                previous_created = current_created
        avg_gap = round(sum(intervals) / len(intervals), 2) if intervals else None
        avg_resolution = []
        for item in ordered:
            proof = item.get("proof") or {}
            created = _parse_dt(item.get("created_at") or item.get("updated_at"))
            finished = _parse_dt(proof.get("submitted_at") or item.get("updated_at"))
            if created and finished and finished >= created:
                avg_resolution.append((finished - created).total_seconds() / 3600.0)
        open_count = sum(1 for item in ordered if item.get("status") != "completed")
        village_rows.append({
            "village_name": village_name,
            "problem_count": len(ordered),
            "open_problem_count": open_count,
            "completed_problem_count": len(ordered) - open_count,
            "repeat_problem_count": repeat_count,
            "repeat_rate": round(repeat_count / len(ordered), 3) if ordered else 0.0,
            "average_gap_days": avg_gap,
            "average_resolution_hours": round(sum(avg_resolution) / len(avg_resolution), 2) if avg_resolution else None,
            "top_topic": topic_counts.most_common(1)[0][0] if topic_counts else "general",
            "topic_breakdown": topic_counts.most_common(3),
            "latest_problem_at": ordered[-1].get("created_at") if ordered else None,
        })

    village_rows.sort(key=lambda row: (row["repeat_rate"], row["problem_count"]), reverse=True)
    overall_gap = round(sum(gap_days) / len(gap_days), 2) if gap_days else None
    top_topics = by_topic.most_common(5)
    return {
        "generated_at": _now_iso(),
        "window_days": days_back,
        "summary": f"{len(village_rows)} villages show repeated problems in the selected window.",
        "villages": village_rows,
        "top_topics": top_topics,
        "average_repeat_gap_days": overall_gap,
    }
