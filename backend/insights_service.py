import hashlib
import json
import logging
import math
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from embeddings import cosine_sim, embed_texts
from env_loader import load_local_env
from nexus import extract_location
from path_utils import get_repo_paths
from utils import get_any, load_village_names, normalize_phrase, read_csv_norm

load_local_env()

logger = logging.getLogger("insights_service")

INSIGHTS_MODEL = os.getenv("GEMINI_ANALYTICS_MODEL", "gemini-1.5-pro")
EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "text-embedding-004")

_STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "there", "their", "need", "needs",
    "issue", "problem", "complaint", "reports", "reported", "report", "villagers", "village",
    "please", "urgent", "near", "about", "into", "over", "after", "before", "been", "have",
    "has", "had", "but", "not", "are", "was", "were", "your", "our", "they", "them", "him",
    "her", "its", "too", "very", "more", "most", "less", "all", "any", "who", "what", "when",
    "where", "which", "why", "how", "show", "tell", "summarize", "summary", "month", "weeks",
    "week", "days", "day", "today", "month", "maybe", "been", "only", "been", "need", "needs",
}

_TOPIC_KEYWORDS: Dict[str, List[str]] = {
    "water": [
        "water", "handpump", "pump", "borewell", "drinking water", "stagnant water",
        "contamination", "contaminated", "sanitation", "toilet", "latrine", "drain",
        "drainage", "sewer", "sewage", "pipeline", "pipe",
    ],
    "health": [
        "health", "fever", "sick", "sickness", "dengue", "malaria", "outbreak", "mosquito",
        "medical", "clinic", "nutrition", "vaccination", "diarrhea", "cough",
    ],
    "infrastructure": [
        "road", "bridge", "culvert", "pothole", "electricity", "wiring", "power", "solar",
        "construction", "building", "damage", "pump", "pipe", "drain", "road repair",
    ],
    "agriculture": [
        "agriculture", "farm", "crop", "irrigation", "soil", "harvest", "seed", "fertility",
        "livestock", "dairy", "sprinkler", "drip",
    ],
    "digital": [
        "digital", "computer", "internet", "smartphone", "spreadsheet", "literacy", "excel",
        "training", "dashboard",
    ],
}

_HEALTH_ALERT_TERMS = {
    "fever", "sick", "sickness", "dengue", "malaria", "mosquito", "outbreak", "stagnant water",
    "diarrhea", "vomiting", "cough", "infection", "medical",
}

_WATER_ALERT_TERMS = {
    "water", "handpump", "pump", "borewell", "contamination", "contaminated", "stagnant water",
    "drain", "drainage", "sewer", "sewage", "pipeline", "pipe", "sanitation",
}

_INFRA_ALERT_TERMS = {
    "road", "bridge", "culvert", "pothole", "construction", "electricity", "wiring", "power",
    "pump", "pipe", "drain", "sewer",
}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _normalize_text(value: Any) -> str:
    return normalize_phrase(str(value or ""))


def _problem_text(problem: Dict[str, Any]) -> str:
    pieces = [
        problem.get("title"),
        problem.get("description"),
        problem.get("category"),
        " ".join(problem.get("visual_tags") or []),
        problem.get("transcript"),
        problem.get("village_name"),
    ]
    return " ".join(str(part or "") for part in pieces).strip()


def _village_coordinates(village_name: Optional[str]) -> Tuple[float, float]:
    coordinates: Dict[str, Tuple[float, float]] = {
        "Sundarpur": (21.1458, 79.0882),
        "Nirmalgaon": (20.7453, 78.6022),
        "Lakshmipur": (23.2000, 77.0833),
        "Devnagar": (23.2599, 77.4126),
        "Riverbend": (21.2514, 81.6296),
    }
    if village_name and village_name in coordinates:
        return coordinates[village_name]

    seed = (village_name or "unknown-village").encode("utf-8")
    digest = hashlib.sha256(seed).hexdigest()
    lat_ratio = int(digest[:8], 16) / 0xFFFFFFFF
    lng_ratio = int(digest[8:16], 16) / 0xFFFFFFFF
    lat = 8.0 + (lat_ratio * 29.0)
    lng = 68.0 + (lng_ratio * 29.0)
    return round(lat, 4), round(lng, 4)


def _haversine_km(a_lat: float, a_lng: float, b_lat: float, b_lng: float) -> float:
    r = 6371.0
    lat1 = math.radians(a_lat)
    lat2 = math.radians(b_lat)
    dlat = math.radians(b_lat - a_lat)
    dlng = math.radians(b_lng - a_lng)
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    )
    return 2 * r * math.asin(min(1.0, math.sqrt(h)))


def _flatten_problem_index(problems: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    indexed: List[Dict[str, Any]] = []
    for problem in problems:
        created_at = _parse_dt(problem.get("created_at")) or _parse_dt(problem.get("updated_at")) or _now()
        village_name = problem.get("village_name") or ""
        lat = problem.get("lat")
        lng = problem.get("lng")
        if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
            lat, lng = _village_coordinates(village_name)
        text = _problem_text(problem)
        indexed.append({
            "problem": problem,
            "created_at": created_at,
            "text": text,
            "norm_text": _normalize_text(text),
            "lat": float(lat),
            "lng": float(lng),
            "village_name": village_name,
            "status": problem.get("status", "pending"),
        })
    return indexed


def _recent_window(items: Sequence[Dict[str, Any]], days_back: int) -> List[Dict[str, Any]]:
    cutoff = _now() - timedelta(days=max(1, int(days_back)))
    return [item for item in items if item["created_at"] >= cutoff]


def _top_topic_for_text(text: str) -> str:
    norm = _normalize_text(text)
    best_topic = "general"
    best_score = 0
    for topic, keywords in _TOPIC_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in norm)
        if score > best_score:
            best_topic = topic
            best_score = score
    return best_topic


def _extract_keyphrases(texts: Sequence[str], limit: int = 6) -> List[str]:
    counter: Counter[str] = Counter()
    for text in texts:
        tokens = [token for token in re.split(r"[^a-z0-9]+", _normalize_text(text)) if token]
        for token in tokens:
            if len(token) < 4 or token in _STOPWORDS:
                continue
            counter[token] += 1
    return [token for token, _ in counter.most_common(limit)]


def _count_topic_issues(items: Sequence[Dict[str, Any]], topic: str) -> int:
    keywords = _TOPIC_KEYWORDS.get(topic, [])
    if not keywords:
        return 0
    count = 0
    for item in items:
        norm_text = item["norm_text"]
        if any(keyword in norm_text for keyword in keywords):
            count += 1
    return count


def _volunteer_name(volunteer: Dict[str, Any]) -> str:
    profile = volunteer.get("profiles") or volunteer.get("profile") or {}
    return (
        profile.get("full_name")
        or profile.get("name")
        or volunteer.get("full_name")
        or volunteer.get("name")
        or volunteer.get("id")
        or volunteer.get("user_id")
        or "Volunteer"
    )


def _volunteer_skills(volunteer: Dict[str, Any]) -> List[str]:
    raw = volunteer.get("skills") or []
    if isinstance(raw, str):
        raw = re.split(r"[;,]", raw)
    return [str(skill).strip() for skill in raw if str(skill).strip()]


def _matches_skill(skill_query: str, skills: Sequence[str]) -> bool:
    query = _normalize_text(skill_query)
    if not query:
        return False
    query_tokens = [token for token in query.split() if token not in _STOPWORDS]
    for skill in skills:
        skill_norm = _normalize_text(skill)
        if query in skill_norm or skill_norm in query:
            return True
        if query_tokens and all(token in skill_norm for token in query_tokens):
            return True
    return False


def _latest_assignment_map(problems: Sequence[Dict[str, Any]]) -> Dict[str, datetime]:
    latest: Dict[str, datetime] = {}
    for problem in problems:
        for match in problem.get("matches") or []:
            volunteer = match.get("volunteers") or {}
            candidate_ids = {
                str(match.get("volunteer_id") or ""),
                str(volunteer.get("id") or ""),
                str(volunteer.get("user_id") or ""),
            }
            assigned_at = _parse_dt(match.get("assigned_at")) or _parse_dt(problem.get("updated_at")) or _now()
            for candidate_id in candidate_ids:
                if not candidate_id:
                    continue
                previous = latest.get(candidate_id)
                if previous is None or assigned_at > previous:
                    latest[candidate_id] = assigned_at
    return latest


def _problem_records_for_village(items: Sequence[Dict[str, Any]], village_name: str) -> List[Dict[str, Any]]:
    village_norm = _normalize_text(village_name)
    return [item for item in items if _normalize_text(item["village_name"]) == village_norm]


def _recent_problem_examples(items: Sequence[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    ordered = sorted(items, key=lambda item: item["created_at"], reverse=True)
    return [
        {
            "id": item["problem"].get("id"),
            "title": item["problem"].get("title"),
            "village_name": item["village_name"],
            "status": item["status"],
            "category": item["problem"].get("category"),
            "created_at": item["problem"].get("created_at"),
        }
        for item in ordered[:limit]
    ]


def _query_villages_by_topic(items: Sequence[Dict[str, Any]], topic: str, days_back: int, limit: int) -> Dict[str, Any]:
    recent = _recent_window(items, days_back)
    matched = [item for item in recent if any(keyword in item["norm_text"] for keyword in _TOPIC_KEYWORDS.get(topic, []))]
    counts: Counter[str] = Counter(item["village_name"] or "Unknown" for item in matched)
    ordered = counts.most_common(limit)
    return {
        "topic": topic,
        "days_back": days_back,
        "villages": [
            {
                "village_name": village,
                "count": count,
                "examples": _recent_problem_examples([item for item in matched if item["village_name"] == village], limit=2),
            }
            for village, count in ordered
        ],
        "matched_problem_count": len(matched),
    }


def _query_volunteers_by_skill_gap(
    volunteers: Sequence[Dict[str, Any]],
    problems: Sequence[Dict[str, Any]],
    village_name: Optional[str],
    skill_query: str,
    inactive_days: int,
    limit: int,
) -> Dict[str, Any]:
    latest_assignments = _latest_assignment_map(problems)
    cutoff = _now() - timedelta(days=max(1, inactive_days))
    matches: List[Dict[str, Any]] = []
    for volunteer in volunteers:
        volunteer_id = str(volunteer.get("id") or volunteer.get("user_id") or "")
        if not volunteer_id:
            continue
        if village_name and _normalize_text(volunteer.get("home_location") or "") != _normalize_text(village_name):
            continue
        skills = _volunteer_skills(volunteer)
        if skill_query and not _matches_skill(skill_query, skills):
            continue
        last_assigned = latest_assignments.get(volunteer_id)
        idle_days = None
        if last_assigned:
            idle_days = max(0, int((_now() - last_assigned).days))
        if not last_assigned or last_assigned <= cutoff:
            matches.append({
                "volunteer_id": volunteer_id,
                "name": _volunteer_name(volunteer),
                "home_location": volunteer.get("home_location") or "",
                "skills": skills,
                "availability": volunteer.get("availability") or volunteer.get("availability_status") or "available",
                "last_assigned_at": last_assigned.isoformat() if last_assigned else None,
                "idle_days": idle_days if idle_days is not None else inactive_days + 1,
            })
    matches.sort(key=lambda item: (item["idle_days"], item["name"]), reverse=True)
    return {
        "village_name": village_name,
        "skill_query": skill_query,
        "inactive_days": inactive_days,
        "volunteers": matches[:limit],
        "count": len(matches),
    }


def _query_village_summary(items: Sequence[Dict[str, Any]], village_name: str, days_back: int, limit: int) -> Dict[str, Any]:
    recent = _recent_window(items, days_back)
    village_items = _problem_records_for_village(recent, village_name)
    topic_counts: Counter[str] = Counter(_top_topic_for_text(item["text"]) for item in village_items)
    keyphrases = _extract_keyphrases([item["text"] for item in village_items], limit=limit)
    statuses = Counter(item["status"] for item in village_items)
    examples = _recent_problem_examples(village_items, limit=limit)
    return {
        "village_name": village_name,
        "days_back": days_back,
        "problem_count": len(village_items),
        "status_counts": dict(statuses),
        "top_topics": topic_counts.most_common(limit),
        "keyphrases": keyphrases,
        "examples": examples,
    }


def _semantic_embeddings(texts: Sequence[str]) -> np.ndarray:
    try:
        from importlib import import_module

        google_genai = import_module("google.genai")
        client = google_genai.Client()
        vectors: List[List[float]] = []
        for text in texts:
            response = client.models.embed_content(model=EMBEDDING_MODEL, contents=text)
            embedding = getattr(response, "embedding", None)
            if embedding is None:
                embeddings = getattr(response, "embeddings", None)
                if embeddings:
                    embedding = embeddings[0]
            values = None
            if embedding is not None:
                values = getattr(embedding, "values", None) or getattr(embedding, "vector", None)
                if values is None and hasattr(embedding, "embedding"):
                    values = getattr(embedding, "embedding")
            if values is None and hasattr(response, "values"):
                values = getattr(response, "values")
            if values is None:
                raise ValueError("Unable to extract embedding values from Gemini response")
            vectors.append([float(value) for value in values])
        return np.asarray(vectors, dtype=float)
    except Exception as exc:
        logger.info("Gemini embeddings unavailable, falling back to local embeddings: %s", exc)
        _, embs, backend = embed_texts(list(texts), model_name="tfidf")
        if backend == "sentence-transformers":
            return np.asarray(embs, dtype=float)
        return embs.toarray() if hasattr(embs, "toarray") else np.asarray(embs, dtype=float)


def _risk_type_from_cluster(cluster: Sequence[Dict[str, Any]]) -> Tuple[Optional[str], float, str]:
    texts = " ".join(item["norm_text"] for item in cluster)
    size = len(cluster)
    village_count = len({item["village_name"] for item in cluster if item["village_name"]})
    health_hits = sum(1 for item in cluster if any(term in item["norm_text"] for term in _HEALTH_ALERT_TERMS))
    water_hits = sum(1 for item in cluster if any(term in item["norm_text"] for term in _WATER_ALERT_TERMS))
    infra_hits = sum(1 for item in cluster if any(term in item["norm_text"] for term in _INFRA_ALERT_TERMS))
    geo_span = 0.0
    for i, left in enumerate(cluster):
        for right in cluster[i + 1:]:
            geo_span = max(geo_span, _haversine_km(left["lat"], left["lng"], right["lat"], right["lng"]))

    if health_hits >= 3 and (water_hits >= 1 or geo_span <= 35.0 or village_count >= 2):
        score = min(1.0, 0.45 + 0.12 * health_hits + 0.08 * water_hits + 0.05 * size)
        return (
            "possible_outbreak_risk",
            score,
            "Health-related complaints are clustering across nearby villages and may indicate a local outbreak.",
        )

    if water_hits >= 3 and (infra_hits >= 1 or village_count >= 2):
        score = min(1.0, 0.42 + 0.11 * water_hits + 0.04 * size)
        return (
            "systemic_water_issue",
            score,
            "Repeated water and sanitation complaints suggest a wider infrastructure failure, not isolated tickets.",
        )

    if infra_hits >= 3 and (geo_span <= 40.0 or village_count >= 2):
        score = min(1.0, 0.38 + 0.10 * infra_hits + 0.04 * size)
        return (
            "systemic_infrastructure_flaw",
            score,
            "Infrastructure complaints are repeating across villages and may require a coordinated fix.",
        )

    if size >= 4 and village_count >= 2:
        score = min(1.0, 0.25 + 0.05 * size)
        return (
            "emerging_cluster",
            score,
            "Several related complaints are arriving together and deserve a closer look.",
        )

    return None, 0.0, ""


def _cluster_problem_items(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if len(items) < 2:
        return []

    texts = [item["text"] for item in items]
    embeddings = _semantic_embeddings(texts)
    if len(embeddings.shape) == 1:
        embeddings = embeddings.reshape(1, -1)

    try:
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        normalized = embeddings / np.clip(norms, 1e-12, None)
    except Exception:
        normalized = embeddings

    parents = list(range(len(items)))

    def find(x: int) -> int:
        while parents[x] != x:
            parents[x] = parents[parents[x]]
            x = parents[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parents[rb] = ra

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            semantic = float(np.dot(normalized[i], normalized[j]))
            geo = _haversine_km(items[i]["lat"], items[i]["lng"], items[j]["lat"], items[j]["lng"])
            same_village = _normalize_text(items[i]["village_name"]) == _normalize_text(items[j]["village_name"])
            if semantic >= 0.68 and geo <= 60.0:
                union(i, j)
            elif same_village and semantic >= 0.52:
                union(i, j)
            elif semantic >= 0.78 and geo <= 120.0:
                union(i, j)

    groups: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for index, item in enumerate(items):
        groups[find(index)].append(item)

    clusters: List[Dict[str, Any]] = []
    for cluster_index, cluster_items in enumerate(sorted(groups.values(), key=len, reverse=True), start=1):
        risk_type, risk_score, risk_summary = _risk_type_from_cluster(cluster_items)
        if len(cluster_items) < 2 and not risk_type:
            continue

        villages = sorted({item["village_name"] or "Unknown" for item in cluster_items})
        statuses = Counter(item["status"] for item in cluster_items)
        topic_counts = Counter(_top_topic_for_text(item["text"]) for item in cluster_items)
        time_values = [item["created_at"] for item in cluster_items]
        geo_span = 0.0
        for i, left in enumerate(cluster_items):
            for right in cluster_items[i + 1:]:
                geo_span = max(geo_span, _haversine_km(left["lat"], left["lng"], right["lat"], right["lng"]))

        examples = _recent_problem_examples(cluster_items, limit=4)
        summary_topic = topic_counts.most_common(1)[0][0] if topic_counts else "general"
        if risk_type == "possible_outbreak_risk":
            summary = f"Possible outbreak cluster: {len(cluster_items)} related complaints across {len(villages)} villages."
        elif risk_type == "systemic_water_issue":
            summary = f"Systemic water issue cluster: {len(cluster_items)} complaints across {len(villages)} villages."
        elif risk_type == "systemic_infrastructure_flaw":
            summary = f"Systemic infrastructure flaw cluster: {len(cluster_items)} complaints across {len(villages)} villages."
        elif len(cluster_items) >= 4:
            summary = f"Emerging {summary_topic} cluster: {len(cluster_items)} complaints across {len(villages)} villages."
        else:
            summary = f"Related complaints cluster with {len(cluster_items)} items across {len(villages)} villages."

        clusters.append({
            "cluster_id": f"cluster-{cluster_index}",
            "risk_type": risk_type,
            "risk_score": round(risk_score, 3),
            "summary": summary,
            "risk_summary": risk_summary,
            "topic": summary_topic,
            "problem_count": len(cluster_items),
            "villages": villages,
            "status_counts": dict(statuses),
            "top_topics": topic_counts.most_common(5),
            "time_range": {
                "earliest": min(time_values).isoformat() if time_values else None,
                "latest": max(time_values).isoformat() if time_values else None,
            },
            "geo_span_km": round(geo_span, 2),
            "examples": examples,
        })

    clusters.sort(key=lambda item: (item["risk_score"], item["problem_count"]), reverse=True)
    return clusters


def build_insight_overview(problems: Sequence[Dict[str, Any]], volunteers: Sequence[Dict[str, Any]], days_back: int = 30) -> Dict[str, Any]:
    indexed = _flatten_problem_index(problems)
    recent = _recent_window(indexed, days_back)
    clusters = _cluster_problem_items(recent)
    alerts = [cluster for cluster in clusters if cluster.get("risk_type")]
    return {
        "generated_at": _now().isoformat(),
        "window_days": days_back,
        "stats": {
            "problem_count": len(recent),
            "open_problem_count": sum(1 for item in recent if item["status"] != "completed"),
            "completed_problem_count": sum(1 for item in recent if item["status"] == "completed"),
            "volunteer_count": len(volunteers),
            "water_problem_count": _count_topic_issues(recent, "water"),
            "health_problem_count": _count_topic_issues(recent, "health"),
            "infrastructure_problem_count": _count_topic_issues(recent, "infrastructure"),
        },
        "alerts": alerts[:5],
        "clusters": clusters[:10],
    }


def _plan_query_with_gemini(query: str, overview: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        from importlib import import_module

        google_genai = import_module("google.genai")
        client = google_genai.Client()
        prompt = (
            "You are Gram-Sahayaka, a rural operations analyst. "
            "Convert the user question into a JSON tool plan for a local data analyst.\n"
            "Available intents:\n"
            "- top_villages_by_topic\n"
            "- volunteer_skill_gap\n"
            "- village_summary\n"
            "- risk_clusters\n"
            "- overview\n\n"
            "Return strict JSON only with keys:\n"
            '{ "intent": string, "parameters": object, "reason": string }\n\n'
            "Parameter examples:\n"
            '- topic: "water" | "health" | "infrastructure" | "agriculture" | "digital"\n'
            '- village_name: string\n'
            '- skill_query: string\n'
            '- days_back: number\n'
            '- limit: number\n'
            '- inactive_days: number\n\n'
            f"Current overview: {json.dumps(overview)[:2000]}\n"
            f"User question: {query}"
        )
        response = client.models.generate_content(model=INSIGHTS_MODEL, contents=[prompt])
        text = getattr(response, "text", "") or ""
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None
        payload = json.loads(match.group(0))
        if not isinstance(payload, dict):
            return None
        return payload
    except Exception as exc:
        logger.info("Gemini planner unavailable, using heuristic routing: %s", exc)
        return None


def _heuristic_plan(query: str, overview: Dict[str, Any]) -> Dict[str, Any]:
    q = _normalize_text(query)
    village_names = load_village_names(str((get_repo_paths().data_dir / "village_locations.csv").resolve()))
    village_name = extract_location(q, village_names) or None
    if "volunteer" in q and ("assigned" in q or "assignment" in q or "assigned anything" in q):
        match = re.search(r"know(?:s)? ([a-z0-9 \-]+?)(?: but| who| and|$)", q)
        skill_query = match.group(1).strip() if match else ""
        return {
            "intent": "volunteer_skill_gap",
            "parameters": {
                "village_name": village_name,
                "skill_query": skill_query,
                "inactive_days": 14 if "2 week" in q or "two week" in q or "2 weeks" in q else 21,
                "limit": 8,
            },
            "reason": "Skill-gap volunteer lookup",
        }

    if any(word in q for word in ["outbreak", "cluster", "dengue", "malaria", "fever", "stagnant water"]):
        return {
            "intent": "risk_clusters",
            "parameters": {"days_back": 30, "limit": 8},
            "reason": "Risk cluster scan",
        }

    if "summarize" in q or "summary" in q or "complaint" in q:
        return {
            "intent": "village_summary",
            "parameters": {
                "village_name": village_name or _guess_village_from_query(q) or "",
                "days_back": 30,
                "limit": 6,
            },
            "reason": "Village complaint summary",
        }

    topic = _infer_topic_from_query(q)
    if ("which village" in q or "most" in q or "top" in q) and topic:
        return {
            "intent": "top_villages_by_topic",
            "parameters": {
                "topic": topic,
                "days_back": 30,
                "limit": 5,
            },
            "reason": "Topic trend lookup",
        }

    if village_name:
        return {
            "intent": "village_summary",
            "parameters": {"village_name": village_name, "days_back": 30, "limit": 6},
            "reason": "Defaulted to village summary",
        }

    return {
        "intent": "overview",
        "parameters": {"days_back": 30},
        "reason": "Fallback overview",
    }


def _guess_village_from_query(query: str) -> Optional[str]:
    village_names = load_village_names(str((get_repo_paths().data_dir / "village_locations.csv").resolve()))
    return extract_location(query, village_names)


def _infer_topic_from_query(query: str) -> Optional[str]:
    q = _normalize_text(query)
    scores: Dict[str, int] = {}
    for topic, keywords in _TOPIC_KEYWORDS.items():
        scores[topic] = sum(1 for keyword in keywords if keyword in q)
    best_topic = max(scores, key=scores.get) if scores else "water"
    return best_topic if scores.get(best_topic, 0) > 0 else None


def _compose_response(query: str, plan: Dict[str, Any], payload: Dict[str, Any]) -> str:
    try:
        from importlib import import_module

        google_genai = import_module("google.genai")
        client = google_genai.Client()
        prompt = (
            "You are Gram-Sahayaka, a concise analyst for Gram Connect. "
            "Write a direct answer to the coordinator using the structured data below. "
            "Do not mention JSON or internal tooling. Keep it specific and actionable.\n\n"
            f"Question: {query}\n"
            f"Plan: {json.dumps(plan)[:1200]}\n"
            f"Data: {json.dumps(payload, default=str)[:3000]}"
        )
        response = client.models.generate_content(model=INSIGHTS_MODEL, contents=[prompt])
        answer = getattr(response, "text", "") or ""
        if answer.strip():
            return answer.strip()
    except Exception as exc:
        logger.info("Gemini response synthesis unavailable, using template answer: %s", exc)
    return _template_answer(plan, payload)


def _template_answer(plan: Dict[str, Any], payload: Dict[str, Any]) -> str:
    intent = plan.get("intent")
    if intent == "top_villages_by_topic":
        villages = payload.get("villages") or []
        if not villages:
            return "I could not find any matching issues in the selected window."
        top = villages[0]
        remainder = ", ".join(f"{item['village_name']} ({item['count']})" for item in villages[:5])
        return f"The highest concentration is in {top['village_name']} with {top['count']} matching issues. Top villages: {remainder}."

    if intent == "volunteer_skill_gap":
        volunteers = payload.get("volunteers") or []
        if not volunteers:
            return "No matching volunteers were found for that skill and inactivity window."
        names = ", ".join(f"{item['name']} ({item['idle_days']} days idle)" for item in volunteers[:5])
        village = payload.get("village_name") or "the selected location"
        skill = payload.get("skill_query") or "the requested skill"
        return f"In {village}, I found {len(volunteers)} volunteers with {skill} who have been idle for at least {payload.get('inactive_days')} days. Examples: {names}."

    if intent == "village_summary":
        village = payload.get("village_name") or "the selected village"
        count = payload.get("problem_count", 0)
        topics = payload.get("top_topics") or []
        top_text = ", ".join(f"{topic} ({num})" for topic, num in topics[:4]) if topics else "no clear dominant topic"
        return f"{village} has {count} recent complaints. The main themes are {top_text}."

    if intent == "risk_clusters":
        alerts = payload.get("alerts") or []
        if not alerts:
            return "No strong outbreak or systemic infrastructure clusters are visible right now."
        top = alerts[0]
        return f"Top alert: {top['summary']} ({top['risk_type']}, score {top['risk_score']:.2f})."

    overview = payload.get("stats") or {}
    return (
        f"Across the selected window, I found {overview.get('problem_count', 0)} problems, "
        f"{overview.get('open_problem_count', 0)} open items, and {overview.get('volunteer_count', 0)} volunteers."
    )


def analyze_coordinator_query(
    query: str,
    *,
    problems: Sequence[Dict[str, Any]],
    volunteers: Sequence[Dict[str, Any]],
    days_back: int = 30,
    limit: int = 5,
) -> Dict[str, Any]:
    indexed = _flatten_problem_index(problems)
    overview = build_insight_overview(problems, volunteers, days_back=days_back)
    plan = _plan_query_with_gemini(query, overview) or _heuristic_plan(query, overview)

    intent = plan.get("intent", "overview")
    parameters = plan.get("parameters") or {}
    used_days_back = int(parameters.get("days_back") or days_back or 30)
    used_limit = int(parameters.get("limit") or limit or 5)

    payload: Dict[str, Any]
    if intent == "top_villages_by_topic":
        topic = str(parameters.get("topic") or _infer_topic_from_query(query) or "water")
        payload = _query_villages_by_topic(indexed, topic, used_days_back, used_limit)
    elif intent == "volunteer_skill_gap":
        payload = _query_volunteers_by_skill_gap(
            volunteers,
            problems,
            parameters.get("village_name") or _guess_village_from_query(query),
            str(parameters.get("skill_query") or ""),
            int(parameters.get("inactive_days") or 14),
            used_limit,
        )
    elif intent == "village_summary":
        village_name = str(parameters.get("village_name") or _guess_village_from_query(query) or "")
        payload = _query_village_summary(indexed, village_name, used_days_back, used_limit) if village_name else overview
    elif intent == "risk_clusters":
        payload = build_insight_overview(problems, volunteers, days_back=used_days_back)
    else:
        payload = overview

    answer = _compose_response(query, plan, payload)
    return {
        "query": query,
        "intent": intent,
        "reason": plan.get("reason") or "",
        "answer": answer,
        "parameters": parameters,
        "overview": overview,
        "payload": payload,
        "suggested_questions": [
            "Which villages have had the most water-related issues this month?",
            "Show me volunteers in Nirmalgaon who know masonry but have not been assigned anything in 2 weeks.",
            "Summarize the major complaints from Sundarpur.",
            "Scan for outbreak or infrastructure risk clusters.",
        ],
    }

