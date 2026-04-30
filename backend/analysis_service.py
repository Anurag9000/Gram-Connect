import json
import logging
import math
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from env_loader import load_local_env
from embeddings import embed_texts

load_local_env()

logger = logging.getLogger("analysis_service")

DEFAULT_CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-1.5-pro")
DEFAULT_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "text-embedding-004")

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "can", "could",
    "for", "from", "has", "have", "how", "i", "in", "into", "is", "it", "me", "of",
    "on", "or", "please", "show", "summarize", "the", "their", "this", "to", "was",
    "we", "were", "which", "with", "within", "who", "why", "would", "you", "your",
}

_HEALTH_TERMS = {
    "fever", "sickness", "illness", "mosquito", "stagnant", "waterlogging", "dengue",
    "malaria", "diarrhea", "cough", "vomiting", "outbreak", "infection", "contamination",
}

_INFRA_TERMS = {
    "pump", "handpump", "borewell", "motor", "pipe", "road", "bridge", "culvert", "wire",
    "electricity", "power", "drain", "sewer", "sanitation", "toilet", "roadway", "leak",
}

_SKILL_ALIASES = {
    "masonry": {"masonry", "brickwork", "bricklayer", "construction"},
    "plumbing": {"plumbing", "pipe fitting", "pipe", "handpump"},
    "water": {"water", "sanitation", "drain", "drainage", "toilet"},
    "digital": {"digital", "computer", "smartphone", "internet", "literacy"},
    "agriculture": {"agriculture", "farm", "crop", "irrigation", "soil"},
}


def _has_gemini_key() -> bool:
    return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))


def _get_gemini_client():
    from google import genai

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    return genai.Client(api_key=api_key) if api_key else genai.Client()


def _safe_json_loads(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _parse_records(payload: Any) -> List[Dict[str, Any]]:
    parsed = _safe_json_loads(payload)
    if isinstance(parsed, list):
        return [dict(item) for item in parsed if isinstance(item, dict)]
    if isinstance(parsed, dict):
        for key in ("records", "items", "data", "problems", "volunteers"):
            nested = parsed.get(key)
            if isinstance(nested, list):
                return [dict(item) for item in nested if isinstance(item, dict)]
        return [dict(parsed)]
    return []


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _clean_tokens(text: str) -> List[str]:
    return [token for token in re.split(r"[^a-z0-9]+", text.lower()) if token and token not in _STOPWORDS]


def _problem_text(problem: Dict[str, Any]) -> str:
    parts = [
        problem.get("title"),
        problem.get("description"),
        problem.get("category"),
        problem.get("village_name"),
        problem.get("village"),
        " ".join(problem.get("visual_tags") or []),
        problem.get("severity"),
        problem.get("status"),
    ]
    return " ".join(str(part or "") for part in parts).strip()


def _volunteer_text(volunteer: Dict[str, Any]) -> str:
    profile = volunteer.get("profiles") or volunteer.get("profile") or {}
    parts = [
        volunteer.get("id"),
        volunteer.get("user_id"),
        profile.get("full_name"),
        volunteer.get("home_location"),
        volunteer.get("availability"),
        volunteer.get("availability_status"),
        " ".join(volunteer.get("skills") or []),
    ]
    return " ".join(str(part or "") for part in parts).strip()


def _normalize_problem(problem: Dict[str, Any]) -> Dict[str, Any]:
    village = problem.get("village_name") or problem.get("village") or ""
    return {
        "id": str(problem.get("id") or ""),
        "title": str(problem.get("title") or "").strip(),
        "description": str(problem.get("description") or "").strip(),
        "category": str(problem.get("category") or "").strip(),
        "village_name": str(village).strip(),
        "status": str(problem.get("status") or "").strip(),
        "severity": str(problem.get("severity") or "NORMAL").upper(),
        "created_at": problem.get("created_at"),
        "updated_at": problem.get("updated_at"),
        "lat": problem.get("lat"),
        "lng": problem.get("lng"),
        "visual_tags": list(problem.get("visual_tags") or []),
        "matches": list(problem.get("matches") or []),
        "matches_count": len(problem.get("matches") or []),
    }


def _normalize_volunteer(volunteer: Dict[str, Any]) -> Dict[str, Any]:
    profile = volunteer.get("profiles") or volunteer.get("profile") or {}
    skills = [str(skill).strip() for skill in volunteer.get("skills") or [] if str(skill).strip()]
    return {
        "id": str(volunteer.get("id") or volunteer.get("user_id") or ""),
        "user_id": str(volunteer.get("user_id") or volunteer.get("id") or ""),
        "full_name": str(profile.get("full_name") or profile.get("name") or volunteer.get("name") or "Volunteer").strip(),
        "home_location": str(volunteer.get("home_location") or volunteer.get("village_name") or "").strip(),
        "availability": str(volunteer.get("availability") or volunteer.get("availability_status") or "").strip(),
        "availability_status": str(volunteer.get("availability_status") or volunteer.get("availability") or "").strip(),
        "skills": skills,
        "profiles": profile,
        "created_at": volunteer.get("created_at"),
        "updated_at": volunteer.get("updated_at"),
    }


def _dense_embeddings(texts: Sequence[str]) -> Tuple[np.ndarray, str]:
    backend = "local"
    if _has_gemini_key():
        try:
            client = _get_gemini_client()
            response = client.models.embed_content(model=DEFAULT_EMBEDDING_MODEL, contents=list(texts))
            vectors: List[Sequence[float]] = []
            for item in getattr(response, "embeddings", []) or []:
                values = getattr(item, "values", None)
                if values is None and isinstance(item, dict):
                    values = item.get("values") or item.get("embedding") or item.get("vector")
                if values is not None:
                    vectors.append(list(values))
            if vectors and len(vectors) == len(texts):
                return np.asarray(vectors, dtype=float), "gemini"
        except Exception as exc:
            logger.info("Gemini embeddings unavailable, using local fallback: %s", exc)

    _, embeddings, local_backend = embed_texts(list(texts), model_name="tfidf")
    if hasattr(embeddings, "toarray"):
        embeddings = embeddings.toarray()
    backend = local_backend
    return np.asarray(embeddings, dtype=float), backend


def _geo_distance_km(a: Dict[str, Any], b: Dict[str, Any]) -> Optional[float]:
    try:
        lat1 = float(a.get("lat"))
        lng1 = float(a.get("lng"))
        lat2 = float(b.get("lat"))
        lng2 = float(b.get("lng"))
    except (TypeError, ValueError):
        return None

    radius = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lng2 - lng1)
    sin_dphi = math.sin(d_phi / 2.0)
    sin_dlam = math.sin(d_lam / 2.0)
    h = sin_dphi ** 2 + math.cos(phi1) * math.cos(phi2) * sin_dlam ** 2
    return 2.0 * radius * math.asin(min(1.0, math.sqrt(h)))


def _geo_similarity(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    distance = _geo_distance_km(a, b)
    if distance is None:
        if a.get("village_name") and a.get("village_name") == b.get("village_name"):
            return 1.0
        return 0.0
    return float(math.exp(-distance / 18.0))


def _time_similarity(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    dt_a = _parse_iso_datetime(a.get("created_at") or a.get("updated_at"))
    dt_b = _parse_iso_datetime(b.get("created_at") or b.get("updated_at"))
    if not dt_a or not dt_b:
        return 0.0
    days = abs((dt_a - dt_b).days)
    if days <= 3:
        return 1.0
    if days <= 7:
        return 0.8
    if days <= 14:
        return 0.5
    if days <= 30:
        return 0.25
    return 0.0


def _shared_signal_bonus(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    text_a = _problem_text(a).lower()
    text_b = _problem_text(b).lower()
    shared = 0.0
    if any(term in text_a and term in text_b for term in _HEALTH_TERMS):
        shared += 0.20
    if any(term in text_a and term in text_b for term in _INFRA_TERMS):
        shared += 0.18
    if any(tag in (a.get("visual_tags") or []) and tag in (b.get("visual_tags") or []) for tag in (a.get("visual_tags") or [])):
        shared += 0.10
    return min(shared, 0.25)


def _dominant_terms(records: Sequence[Dict[str, Any]], limit: int = 5) -> List[str]:
    counter: Counter[str] = Counter()
    for record in records:
        counter.update(token for token in _clean_tokens(_problem_text(record)) if len(token) > 2)
        counter.update(token for token in _clean_tokens(" ".join(record.get("visual_tags") or [])) if len(token) > 2)
    return [term for term, _ in counter.most_common(limit)]


def _cluster_name(records: Sequence[Dict[str, Any]], dominant_terms: Sequence[str]) -> str:
    blob = " ".join(_problem_text(record).lower() for record in records)
    if any(term in blob for term in ("fever", "sickness", "outbreak", "mosquito", "stagnant")):
        return "Possible public health risk"
    if any(term in blob for term in ("pump", "handpump", "borewell", "motor")):
        return "Recurring water infrastructure failures"
    if any(term in blob for term in ("road", "bridge", "culvert", "drain")):
        return "Local infrastructure bottleneck"
    if dominant_terms:
        readable = " ".join(term.capitalize() for term in dominant_terms[:3])
        return f"{readable} cluster"
    return "Related issue cluster"


def _cluster_recommendation(name: str, records: Sequence[Dict[str, Any]]) -> str:
    blob = " ".join(_problem_text(record).lower() for record in records)
    villages = sorted({str(record.get("village_name") or "Unknown") for record in records})
    village_text = ", ".join(villages[:4]) + (" and more" if len(villages) > 4 else "")
    if "health" in name.lower() or any(term in blob for term in _HEALTH_TERMS):
        return f"Alert the block health team, inspect {village_text}, and check for water or mosquito breeding sources."
    if any(term in blob for term in ("pump", "handpump", "borewell", "motor", "pipe")):
        return f"Treat this as a shared infrastructure fault. Verify the failing hardware pattern across {village_text} before dispatching separate repairs."
    return f"Group field inspection across {village_text} and fix the repeated root cause before assigning isolated tickets."


def _find_recent_assignments(problem: Dict[str, Any]) -> List[datetime]:
    timestamps: List[datetime] = []
    for match in problem.get("matches") or []:
        for field in ("assigned_at", "completed_at"):
            dt = _parse_iso_datetime(match.get(field))
            if dt:
                timestamps.append(dt)
    return timestamps


def _assignment_age_days(volunteer: Dict[str, Any], problems: Sequence[Dict[str, Any]]) -> Optional[float]:
    volunteer_id = str(volunteer.get("id") or volunteer.get("user_id") or "")
    if not volunteer_id:
        return None

    timestamps: List[datetime] = []
    for problem in problems:
        for match in problem.get("matches") or []:
            target = str(match.get("volunteer_id") or match.get("volunteers", {}).get("id") or match.get("volunteers", {}).get("user_id") or "")
            if target == volunteer_id:
                dt = _parse_iso_datetime(match.get("assigned_at") or match.get("completed_at"))
                if dt:
                    timestamps.append(dt)

    if not timestamps:
        return None
    latest = max(timestamps)
    return (datetime.now() - latest).total_seconds() / 86400.0


def _build_chat_bundle(query: str, problems: Sequence[Dict[str, Any]], volunteers: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    query_lc = query.lower().strip()
    query_tokens = set(_clean_tokens(query_lc))
    problems_norm = [_normalize_problem(problem) for problem in problems]
    volunteers_norm = [_normalize_volunteer(volunteer) for volunteer in volunteers]

    village_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    severity_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    for problem in problems_norm:
        village_counts[problem["village_name"] or "Unknown"] += 1
        category_counts[problem["category"] or "uncategorized"] += 1
        severity_counts[problem["severity"] or "NORMAL"] += 1
        status_counts[problem["status"] or "unknown"] += 1

    focus = "overview"
    if any(word in query_lc for word in ("volunteer", "assigned", "masonry", "skill", "who knows", "haven't been assigned")):
        focus = "volunteer_lookup"
    elif any(word in query_lc for word in ("which villages", "summarize", "complaint", "trends", "most")):
        focus = "trend_analysis"

    relevant_problems = sorted(
        problems_norm,
        key=lambda problem: (_problem_relevance(problem, query_tokens), problem.get("created_at") or ""),
        reverse=True,
    )
    relevant_problems = [problem for problem in relevant_problems if _problem_relevance(problem, query_tokens) > 0] or problems_norm[:25]

    village_focus = _query_village_names(query_lc, problems_norm)
    skill_focus = _query_skill_terms(query_lc)
    time_window_days, time_note = _query_time_window(query_lc)
    time_filtered = _apply_time_window(relevant_problems, time_window_days)

    if village_focus:
        time_filtered = [problem for problem in time_filtered if problem["village_name"] in village_focus] or time_filtered
    if focus == "volunteer_lookup" and skill_focus:
        volunteer_candidates = [
            volunteer for volunteer in volunteers_norm
            if _volunteer_has_skill(volunteer, skill_focus)
        ]
    else:
        volunteer_candidates = []

    volunteer_matches = []
    if focus == "volunteer_lookup":
        for volunteer in volunteer_candidates or volunteers_norm:
            assignment_age = _assignment_age_days(volunteer, problems_norm)
            if assignment_age is None or assignment_age >= 14:
                volunteer_matches.append(
                    {
                        "id": volunteer["id"],
                        "name": volunteer["full_name"],
                        "home_location": volunteer["home_location"],
                        "skills": volunteer["skills"][:8],
                        "assignment_age_days": round(assignment_age, 1) if assignment_age is not None else None,
                    }
                )
        volunteer_matches.sort(key=lambda item: (item["assignment_age_days"] is None, -(item["assignment_age_days"] or 0)))

    top_villages = [
        {"village": village, "count": count}
        for village, count in village_counts.most_common(5)
    ]
    top_categories = [
        {"category": category, "count": count}
        for category, count in category_counts.most_common(5)
    ]

    return {
        "query": query,
        "focus": focus,
        "time_window_days": time_window_days,
        "time_window_note": time_note,
        "query_villages": village_focus,
        "query_skills": skill_focus,
        "problem_counts": {
            "total": len(problems_norm),
            "open": sum(1 for problem in problems_norm if problem["status"] != "completed"),
            "completed": sum(1 for problem in problems_norm if problem["status"] == "completed"),
        },
        "problem_breakdown": {
            "villages": top_villages,
            "categories": top_categories,
            "severities": [{"severity": sev, "count": count} for sev, count in severity_counts.most_common(5)],
            "statuses": [{"status": status, "count": count} for status, count in status_counts.most_common(5)],
        },
        "relevant_problems": [
            {
                "id": problem["id"],
                "title": problem["title"],
                "village_name": problem["village_name"],
                "category": problem["category"],
                "severity": problem["severity"],
                "status": problem["status"],
                "created_at": problem["created_at"],
                "matches_count": problem["matches_count"],
                "visual_tags": problem["visual_tags"][:5],
            }
            for problem in time_filtered[:12]
        ],
        "volunteer_matches": volunteer_matches[:12],
    }


def _problem_relevance(problem: Dict[str, Any], query_tokens: Sequence[str]) -> int:
    blob = _problem_text(problem).lower()
    score = 0
    for token in query_tokens:
        if not token or len(token) < 2:
            continue
        if token in blob:
            score += 2
    for alias, synonyms in _SKILL_ALIASES.items():
        if any(term in blob for term in synonyms) and alias in query_tokens:
            score += 4
    return score


def _query_village_names(query_lc: str, problems: Sequence[Dict[str, Any]]) -> List[str]:
    villages = sorted({problem["village_name"] for problem in problems if problem.get("village_name")})
    hits = [village for village in villages if village and village.lower() in query_lc]
    if hits:
        return hits
    for pattern in (r"\bin\s+([a-zA-Z][a-zA-Z\s-]+)", r"\bfrom\s+([a-zA-Z][a-zA-Z\s-]+)"):
        for match in re.findall(pattern, query_lc):
            candidate = match.strip().title()
            if candidate in villages:
                hits.append(candidate)
    return list(dict.fromkeys(hits))


def _query_skill_terms(query_lc: str) -> List[str]:
    hits = []
    for alias, synonyms in _SKILL_ALIASES.items():
        if alias in query_lc or any(term in query_lc for term in synonyms):
            hits.append(alias)
    if "masonry" in query_lc and "construction" not in hits:
        hits.append("masonry")
    return list(dict.fromkeys(hits))


def _query_time_window(query_lc: str) -> Tuple[int, str]:
    if "this month" in query_lc:
        return 31, "Using the current month window."
    if "last month" in query_lc:
        return 62, "Using the last month window."
    if "2 weeks" in query_lc or "two weeks" in query_lc:
        return 14, "Using a two-week window."
    if "week" in query_lc:
        return 7, "Using a one-week window."
    if "today" in query_lc or "now" in query_lc:
        return 1, "Using today as the window."
    return 90, "Using the last 90 days as a fallback window."


def _apply_time_window(records: Sequence[Dict[str, Any]], days: int) -> List[Dict[str, Any]]:
    if days <= 0:
        return list(records)
    cutoff = datetime.now() - timedelta(days=days)
    filtered = []
    for record in records:
        dt = _parse_iso_datetime(record.get("created_at") or record.get("updated_at"))
        if dt is None or dt >= cutoff:
            filtered.append(record)
    if filtered:
        return filtered
    return list(records)


def _volunteer_has_skill(volunteer: Dict[str, Any], skill_focus: Sequence[str]) -> bool:
    blob = " ".join([volunteer.get("full_name", ""), volunteer.get("home_location", ""), " ".join(volunteer.get("skills") or [])]).lower()
    if not skill_focus:
        return True
    return any(
        alias in blob or any(term in blob for term in _SKILL_ALIASES.get(alias, set()))
        for alias in skill_focus
    )


def _render_chat_answer(bundle: Dict[str, Any]) -> str:
    focus = bundle.get("focus", "overview")
    counts = bundle.get("problem_counts") or {}
    breakdown = bundle.get("problem_breakdown") or {}
    villages = breakdown.get("villages") or []
    categories = breakdown.get("categories") or []
    problems = bundle.get("relevant_problems") or []
    volunteers = bundle.get("volunteer_matches") or []

    lines: List[str] = []
    if bundle.get("time_window_note"):
        lines.append(bundle["time_window_note"])

    if focus == "volunteer_lookup":
        if volunteers:
            lines.append(f"I found {len(volunteers)} volunteer(s) that match the request.")
            for volunteer in volunteers[:6]:
                skill_text = ", ".join(volunteer.get("skills") or []) or "no listed skills"
                age_text = (
                    f"{volunteer['assignment_age_days']} days since last assignment"
                    if volunteer.get("assignment_age_days") is not None
                    else "no recorded assignments"
                )
                lines.append(
                    f"- {volunteer['name']} ({volunteer.get('home_location') or 'Unknown'}): {skill_text}; {age_text}."
                )
        else:
            lines.append("I could not find any volunteers that satisfy the requested filters.")
        return "\n".join(lines)

    lines.append(
        f"Across {counts.get('total', 0)} problems, {counts.get('open', 0)} are still open and {counts.get('completed', 0)} are completed."
    )
    if villages:
        village_text = ", ".join(f"{entry['village']} ({entry['count']})" for entry in villages[:5])
        lines.append(f"Most affected villages: {village_text}.")
    if categories:
        category_text = ", ".join(f"{entry['category']} ({entry['count']})" for entry in categories[:5])
        lines.append(f"Top complaint categories: {category_text}.")
    if problems:
        lines.append("Representative recent issues:")
        for problem in problems[:5]:
            lines.append(
                f"- {problem['title']} in {problem.get('village_name') or 'Unknown'} "
                f"({problem.get('status') or 'unknown'}, {problem.get('severity') or 'NORMAL'})."
            )
    return "\n".join(lines)


def _gemini_chat_answer(query: str, bundle: Dict[str, Any]) -> Optional[str]:
    if not _has_gemini_key():
        return None
    try:
        client = _get_gemini_client()
        prompt = (
            "You are Gram-Sahayaka, the coordinator analytics assistant for Gram Connect.\n"
            "Answer the user's question using ONLY the supplied analysis bundle.\n"
            "Do not invent records or claim access to anything outside the bundle.\n"
            "Keep the response concise, practical, and specific. Use bullets when listing results.\n"
            "If the bundle does not fully answer the query, say what is missing.\n\n"
            f"QUERY:\n{query}\n\n"
            f"ANALYSIS BUNDLE (JSON):\n{json.dumps(bundle, ensure_ascii=False)}\n"
        )
        response = client.models.generate_content(model=DEFAULT_CHAT_MODEL, contents=[prompt])
        text = str(getattr(response, "text", "") or "").strip()
        return text or None
    except Exception as exc:
        logger.warning("Gemini chat answer failed, using local summary: %s", exc)
        return None


def _cluster_records(records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    normalized = [_normalize_problem(problem) for problem in records]
    if not normalized:
        return {"summary": "No open problems are available for clustering.", "clusters": [], "risk_level": "LOW", "total_problems": 0}

    texts = [_problem_text(problem) for problem in normalized]
    matrix, embedding_backend = _dense_embeddings(texts)
    if matrix.ndim == 1:
        matrix = matrix.reshape(-1, 1)

    n = len(normalized)
    parent = list(range(n))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(a: int, b: int) -> None:
        root_a = find(a)
        root_b = find(b)
        if root_a != root_b:
            parent[root_b] = root_a

    # Pairwise clustering with text, time, and geography signals.
    for i in range(n):
        for j in range(i + 1, n):
            text_sim = float(np.dot(matrix[i], matrix[j]) / ((np.linalg.norm(matrix[i]) * np.linalg.norm(matrix[j])) + 1e-9))
            geo_sim = _geo_similarity(normalized[i], normalized[j])
            time_sim = _time_similarity(normalized[i], normalized[j])
            signal_bonus = _shared_signal_bonus(normalized[i], normalized[j])
            score = (0.66 * text_sim) + (0.22 * geo_sim) + (0.08 * time_sim) + signal_bonus
            if score >= 0.60 or (geo_sim >= 0.85 and text_sim >= 0.35) or (signal_bonus >= 0.18 and text_sim >= 0.30):
                union(i, j)

    components: Dict[int, List[int]] = defaultdict(list)
    for index in range(n):
        components[find(index)].append(index)

    clusters: List[Dict[str, Any]] = []
    for indices in components.values():
        if len(indices) < 2:
            continue

        component = [normalized[index] for index in indices]
        dominant_terms = _dominant_terms(component)
        name = _cluster_name(component, dominant_terms)
        blob = " ".join(_problem_text(problem).lower() for problem in component)
        risk_type = "general"
        if any(term in blob for term in _HEALTH_TERMS):
            risk_type = "public-health"
        elif any(term in blob for term in _INFRA_TERMS):
            risk_type = "infrastructure"

        villages = sorted({problem["village_name"] or "Unknown" for problem in component})
        categories = sorted({problem["category"] or "uncategorized" for problem in component})
        severities = [problem["severity"] for problem in component]
        high_count = sum(1 for severity in severities if severity == "HIGH")
        avg_geo = _average_geo_distance(component)
        pairwise_text = _average_pairwise_text_similarity(matrix, indices)
        confidence = round(min(0.99, 0.35 + (0.4 * pairwise_text) + (0.15 * min(len(indices) / 5.0, 1.0)) + (0.1 if risk_type != "general" else 0.0)), 2)
        severity = "HIGH" if risk_type == "public-health" or high_count >= max(2, len(indices) // 2) else "NORMAL"
        clusters.append(
            {
                "id": f"cluster-{len(clusters) + 1}",
                "name": name,
                "risk_type": risk_type,
                "severity": severity,
                "confidence": confidence,
                "problem_count": len(indices),
                "village_count": len(villages),
                "villages": villages,
                "categories": categories,
                "related_problem_ids": [component[index]["id"] for index in range(len(component))],
                "dominant_terms": dominant_terms,
                "signals": _cluster_signals(component),
                "avg_geo_distance_km": round(avg_geo, 2) if avg_geo is not None else None,
                "recommendation": _cluster_recommendation(name, component),
                "sample_titles": [problem["title"] for problem in component[:4]],
            }
        )

    clusters.sort(key=lambda item: (item["severity"] != "HIGH", -item["problem_count"], -item["confidence"]))
    high_priority = sum(1 for cluster in clusters if cluster["severity"] == "HIGH")
    total = len(normalized)
    if not clusters:
        summary = "No strong multi-problem clusters were detected."
        risk_level = "LOW"
    else:
        summary = (
            f"Identified {len(clusters)} related clusters across {total} open problems. "
            f"{high_priority} cluster(s) are high priority and need proactive follow-up."
        )
        risk_level = "HIGH" if high_priority else "MODERATE"

    if _has_gemini_key() and clusters:
        gemini_summary = _gemini_cluster_summary(summary, clusters)
        if gemini_summary:
            summary = gemini_summary

    return {
        "summary": summary,
        "risk_level": risk_level,
        "total_problems": total,
        "clusters": clusters[:12],
        "embedding_backend": embedding_backend,
    }


def _average_pairwise_text_similarity(matrix: np.ndarray, indices: Sequence[int]) -> float:
    if len(indices) < 2:
        return 0.0
    sims = []
    for i, index_a in enumerate(indices):
        for index_b in indices[i + 1 :]:
            vec_a = matrix[index_a]
            vec_b = matrix[index_b]
            sims.append(float(np.dot(vec_a, vec_b) / ((np.linalg.norm(vec_a) * np.linalg.norm(vec_b)) + 1e-9)))
    return float(np.mean(sims)) if sims else 0.0


def _average_geo_distance(records: Sequence[Dict[str, Any]]) -> Optional[float]:
    if len(records) < 2:
        return None
    distances = []
    for i, record_a in enumerate(records):
        for record_b in records[i + 1 :]:
            distance = _geo_distance_km(record_a, record_b)
            if distance is not None:
                distances.append(distance)
    return float(np.mean(distances)) if distances else None


def _cluster_signals(records: Sequence[Dict[str, Any]]) -> List[str]:
    blob = " ".join(_problem_text(record).lower() for record in records)
    signals: List[str] = []
    if any(term in blob for term in ("fever", "sickness", "mosquito", "stagnant", "malaria", "dengue")):
        signals.append("health-risk")
    if any(term in blob for term in ("pump", "handpump", "borewell", "motor", "pipe")):
        signals.append("repeated-infrastructure-failure")
    if any(term in blob for term in ("road", "bridge", "culvert", "drain")):
        signals.append("transport-or-drainage-bottleneck")
    if not signals:
        signals.append("mixed-complaints")
    return signals


def _gemini_cluster_summary(summary: str, clusters: Sequence[Dict[str, Any]]) -> Optional[str]:
    try:
        client = _get_gemini_client()
        prompt = (
            "You are Gram-Sahayaka, summarizing cluster analysis for a rural coordinator.\n"
            "Rewrite the summary into one crisp paragraph and highlight the most urgent cluster in one sentence.\n"
            "Do not invent new facts; only use the JSON payload.\n\n"
            f"SUMMARY:\n{summary}\n\n"
            f"CLUSTERS JSON:\n{json.dumps(list(clusters), ensure_ascii=False)}\n"
        )
        response = client.models.generate_content(model=DEFAULT_CHAT_MODEL, contents=[prompt])
        text = str(getattr(response, "text", "") or "").strip()
        return text or None
    except Exception as exc:
        logger.info("Gemini cluster summary unavailable: %s", exc)
        return None


def chat_with_database(query: str, problems_data: str, volunteers_data: str) -> str:
    """Answer coordinator questions over live problem and volunteer data."""
    problems = _parse_records(problems_data)
    volunteers = _parse_records(volunteers_data)
    bundle = _build_chat_bundle(query, problems, volunteers)

    gemini_answer = _gemini_chat_answer(query, bundle)
    if gemini_answer:
        return gemini_answer
    return _render_chat_answer(bundle)


def cluster_problems(problems_data: str) -> Dict[str, Any]:
    """Detect geographic and semantic problem clusters for proactive action."""
    problems = _parse_records(problems_data)
    return _cluster_records(problems)
