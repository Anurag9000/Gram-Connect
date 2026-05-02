import csv
import hashlib
import json
import logging
import os
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector
from sklearn.feature_extraction.text import HashingVectorizer

from path_utils import get_repo_paths
from utils import get_any, read_csv_norm

logger = logging.getLogger("postgres_store")

DEFAULT_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://gram_connect:gram_connect@127.0.0.1:5432/gram_connect",
)

_HASH_VECTORIZER = HashingVectorizer(
    n_features=256,
    alternate_sign=False,
    norm="l2",
    lowercase=True,
    ngram_range=(1, 2),
)


def _now_iso() -> str:
    from datetime import datetime

    return datetime.now().isoformat()


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _embedding_for_text(text: str) -> List[float]:
    matrix = _HASH_VECTORIZER.transform([text or ""]).toarray()
    return [float(value) for value in matrix[0].tolist()]


def _seed_record_id(dataset: str, row: Dict[str, Any]) -> str:
    if dataset == "people":
        return str(get_any(row, ["person_id", "student_id", "id"], "")).strip()
    if dataset == "proposals":
        return str(get_any(row, ["proposal_id", "id"], "")).strip()
    if dataset == "pairs":
        proposal_id = str(get_any(row, ["proposal_id"], "")).strip()
        person_id = str(get_any(row, ["person_id", "student_id", "id"], "")).strip()
        label = str(get_any(row, ["label"], "")).strip()
        return f"{proposal_id}:{person_id}:{label}"
    if dataset == "village_locations":
        return str(get_any(row, ["village_name", "name"], "")).strip()
    if dataset == "village_distances":
        village_a = str(get_any(row, ["village_a"], "")).strip()
        village_b = str(get_any(row, ["village_b"], "")).strip()
        return f"{village_a}:{village_b}"
    if dataset == "runtime_profiles":
        return str(get_any(row, ["id", "user_id"], "")).strip()
    return str(get_any(row, ["id"], "")).strip() or hashlib.sha256(json.dumps(row, sort_keys=True).encode("utf-8")).hexdigest()


def _seed_embedding_text(dataset: str, row: Dict[str, Any]) -> Optional[str]:
    if dataset == "people":
        return " ".join(
            part for part in [
                get_any(row, ["name", "full_name"], ""),
                get_any(row, ["skills", "text"], ""),
                get_any(row, ["home_location", "village"], ""),
            ]
            if part
        ).strip()
    if dataset == "proposals":
        return " ".join(
            part for part in [
                get_any(row, ["title"], ""),
                get_any(row, ["text", "description"], ""),
                get_any(row, ["village", "village_name"], ""),
                get_any(row, ["category"], ""),
            ]
            if part
        ).strip()
    if dataset == "village_locations":
        return " ".join(
            part for part in [
                get_any(row, ["village_name", "name"], ""),
                get_any(row, ["district"], ""),
                get_any(row, ["state"], ""),
            ]
            if part
        ).strip()
    return None


@dataclass
class RuntimeState:
    problems: List[Dict[str, Any]]
    volunteers: List[Dict[str, Any]]
    profiles: List[Dict[str, Any]]
    media_assets: List[Dict[str, Any]]


class PostgresStore:
    def __init__(self, database_url: str = DEFAULT_DATABASE_URL):
        self.database_url = database_url
        self._pool: Optional[ConnectionPool] = None
        self._schema_ready = False

    @classmethod
    def from_env(cls) -> "PostgresStore":
        return cls(DEFAULT_DATABASE_URL)

    def _get_pool(self) -> ConnectionPool:
        if self._pool is None:
            self._pool = ConnectionPool(
                conninfo=self.database_url,
                min_size=1,
                max_size=4,
                kwargs={"autocommit": True, "row_factory": dict_row},
            )
        return self._pool

    @contextmanager
    def _connect(self):
        pool = self._get_pool()
        with pool.connection() as conn:
            register_vector(conn)
            yield conn

    def ensure_schema(self) -> None:
        if self._schema_ready:
            return
        with self._connect() as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS seed_catalog (
                    dataset text NOT NULL,
                    record_id text NOT NULL,
                    data jsonb NOT NULL,
                    embedding vector,
                    created_at timestamptz NOT NULL DEFAULT now(),
                    PRIMARY KEY (dataset, record_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_profiles (
                    id text PRIMARY KEY,
                    data jsonb NOT NULL,
                    updated_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_volunteers (
                    id text PRIMARY KEY,
                    data jsonb NOT NULL,
                    updated_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_problems (
                    id text PRIMARY KEY,
                    data jsonb NOT NULL,
                    embedding vector,
                    updated_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_media_assets (
                    id text PRIMARY KEY,
                    data jsonb NOT NULL,
                    updated_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS learning_events (
                    id text PRIMARY KEY,
                    event_type text NOT NULL,
                    entity_type text,
                    entity_id text,
                    summary text,
                    data jsonb NOT NULL,
                    embedding vector,
                    created_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_meta (
                    key text PRIMARY KEY,
                    value jsonb NOT NULL,
                    updated_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_playbooks (
                    id text PRIMARY KEY,
                    topic text,
                    village_name text,
                    data jsonb NOT NULL,
                    embedding vector,
                    updated_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS inventory_items (
                    id text PRIMARY KEY,
                    owner_type text NOT NULL,
                    owner_id text NOT NULL,
                    item_name text NOT NULL,
                    quantity integer NOT NULL DEFAULT 0,
                    data jsonb NOT NULL,
                    updated_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS followup_feedback (
                    id text PRIMARY KEY,
                    problem_id text NOT NULL,
                    source text,
                    response text NOT NULL,
                    data jsonb NOT NULL,
                    created_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS platform_records (
                    id text PRIMARY KEY,
                    record_type text NOT NULL,
                    subtype text,
                    owner_id text,
                    status text,
                    data jsonb NOT NULL,
                    embedding vector,
                    updated_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS learning_events_entity_idx
                ON learning_events (entity_type, entity_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS learning_events_event_type_idx
                ON learning_events (event_type)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS platform_records_type_idx
                ON platform_records (record_type, subtype, owner_id)
                """
            )
        self._schema_ready = True

    def _table_has_rows(self, conn, table: str) -> bool:
        row = conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
        return bool(row)

    def ensure_seed_catalog_from_csv(self, dataset_name: str, csv_path: str, force: bool = False) -> int:
        self.ensure_schema()
        rows = read_csv_norm(csv_path)
        return self.upsert_seed_rows(dataset_name, rows, force=force)

    def upsert_seed_rows(self, dataset_name: str, rows: Iterable[Dict[str, Any]], force: bool = False) -> int:
        self.ensure_schema()
        inserted = 0
        with self._connect() as conn:
            if force:
                conn.execute("DELETE FROM seed_catalog WHERE dataset = %s", (dataset_name,))
            for row in rows:
                record_id = _seed_record_id(dataset_name, row)
                if not record_id:
                    continue
                payload = _jsonable(row)
                embedding_text = _seed_embedding_text(dataset_name, payload)
                embedding = _embedding_for_text(embedding_text) if embedding_text else None
                conn.execute(
                    """
                    INSERT INTO seed_catalog (dataset, record_id, data, embedding)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (dataset, record_id)
                    DO UPDATE SET data = EXCLUDED.data, embedding = EXCLUDED.embedding
                    """,
                    (dataset_name, record_id, Jsonb(payload), embedding),
                )
                inserted += 1
        return inserted

    def ensure_seed_catalog(self, *, data_dir: Optional[Path] = None, force: bool = False) -> None:
        self.ensure_schema()
        repo_paths = get_repo_paths()
        data_dir = data_dir or repo_paths.data_dir
        csv_map = {
            "people": data_dir / "people.csv",
            "proposals": data_dir / "proposals.csv",
            "pairs": data_dir / "pairs.csv",
            "village_locations": data_dir / "village_locations.csv",
            "village_distances": data_dir / "village_distances.csv",
            "runtime_profiles": data_dir / "runtime_profiles.csv",
        }
        for dataset, path in csv_map.items():
            if path.exists():
                self.ensure_seed_catalog_from_csv(dataset, str(path), force=force)

    def clear_runtime_state(self) -> None:
        self.ensure_schema()
        with self._connect() as conn:
            conn.execute("TRUNCATE runtime_profiles, runtime_volunteers, runtime_problems, runtime_media_assets RESTART IDENTITY")

    def save_runtime_state(
        self,
        *,
        problems: List[Dict[str, Any]],
        volunteers: List[Dict[str, Any]],
        profiles: List[Dict[str, Any]],
        media_assets: List[Dict[str, Any]],
    ) -> None:
        self.ensure_schema()
        with self._connect() as conn:
            conn.execute("TRUNCATE runtime_profiles, runtime_volunteers, runtime_problems, runtime_media_assets RESTART IDENTITY")
            for profile in profiles:
                profile_id = str(profile.get("id") or profile.get("user_id") or "")
                if not profile_id:
                    continue
                conn.execute(
                    """
                    INSERT INTO runtime_profiles (id, data, updated_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data, updated_at = EXCLUDED.updated_at
                    """,
                    (profile_id, Jsonb(_jsonable(profile)), _now_iso()),
                )

            for volunteer in volunteers:
                volunteer_id = str(volunteer.get("id") or volunteer.get("user_id") or "")
                if not volunteer_id:
                    continue
                conn.execute(
                    """
                    INSERT INTO runtime_volunteers (id, data, updated_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data, updated_at = EXCLUDED.updated_at
                    """,
                    (volunteer_id, Jsonb(_jsonable(volunteer)), _now_iso()),
                )

            for problem in problems:
                problem_id = str(problem.get("id") or "")
                if not problem_id:
                    continue
                embedding_text = " ".join(
                    str(part or "")
                    for part in [
                        problem.get("title"),
                        problem.get("description"),
                        problem.get("category"),
                        " ".join(problem.get("visual_tags") or []),
                        problem.get("village_name"),
                    ]
                    if part
                ).strip()
                embedding = _embedding_for_text(embedding_text) if embedding_text else None
                conn.execute(
                    """
                    INSERT INTO runtime_problems (id, data, embedding, updated_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE
                    SET data = EXCLUDED.data,
                        embedding = EXCLUDED.embedding,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (problem_id, Jsonb(_jsonable(problem)), embedding, _now_iso()),
                )

            for asset in media_assets:
                asset_id = str(asset.get("id") or "")
                if not asset_id:
                    continue
                conn.execute(
                    """
                    INSERT INTO runtime_media_assets (id, data, updated_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data, updated_at = EXCLUDED.updated_at
                    """,
                    (asset_id, Jsonb(_jsonable(asset)), _now_iso()),
                )

    def load_runtime_state(self) -> RuntimeState:
        self.ensure_schema()
        with self._connect() as conn:
            profiles = [dict(row["data"]) for row in conn.execute("SELECT data FROM runtime_profiles ORDER BY updated_at ASC").fetchall()]
            volunteers = [dict(row["data"]) for row in conn.execute("SELECT data FROM runtime_volunteers ORDER BY updated_at ASC").fetchall()]
            problems = [dict(row["data"]) for row in conn.execute("SELECT data FROM runtime_problems ORDER BY updated_at ASC").fetchall()]
            media_assets = [dict(row["data"]) for row in conn.execute("SELECT data FROM runtime_media_assets ORDER BY updated_at ASC").fetchall()]
        return RuntimeState(problems=problems, volunteers=volunteers, profiles=profiles, media_assets=media_assets)

    def load_seed_rows(self, dataset: str) -> List[Dict[str, Any]]:
        self.ensure_schema()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT data FROM seed_catalog WHERE dataset = %s ORDER BY record_id ASC",
                (dataset,),
            ).fetchall()
        return [dict(row["data"]) for row in rows]

    def set_meta(self, key: str, value: Any) -> None:
        self.ensure_schema()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO app_meta (key, value, updated_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at
                """,
                (key, Jsonb(_jsonable(value)), _now_iso()),
            )

    def get_meta(self, key: str, default: Any = None) -> Any:
        self.ensure_schema()
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM app_meta WHERE key = %s", (key,)).fetchone()
        if not row:
            return default
        return row["value"]

    def get_village_name_rows(self) -> List[Dict[str, Any]]:
        rows = self.load_seed_rows("village_locations")
        if not rows:
            return [
                {"village_name": "Sundarpur", "district": "Nagpur Rural", "state": "Maharashtra", "lat": 21.1458, "lng": 79.0882},
                {"village_name": "Nirmalgaon", "district": "Wardha", "state": "Maharashtra", "lat": 20.7453, "lng": 78.6022},
                {"village_name": "Lakshmipur", "district": "Sehore", "state": "Madhya Pradesh", "lat": 23.2, "lng": 77.0833},
                {"village_name": "Devnagar", "district": "Bhopal Rural", "state": "Madhya Pradesh", "lat": 23.2599, "lng": 77.4126},
                {"village_name": "Riverbend", "district": "Raipur", "state": "Chhattisgarh", "lat": 21.2514, "lng": 81.6296},
            ]
        return rows

    def get_village_names(self) -> List[str]:
        names = []
        for row in self.get_village_name_rows():
            name = str(get_any(row, ["village_name", "name"], "")).strip()
            if name:
                names.append(name)
        return names

    def get_village_coordinates(self) -> Dict[str, Tuple[float, float]]:
        coordinates: Dict[str, Tuple[float, float]] = {}
        for row in self.get_village_name_rows():
            name = str(get_any(row, ["village_name", "name"], "")).strip()
            lat = get_any(row, ["lat", "latitude"], None)
            lng = get_any(row, ["lng", "longitude"], None)
            if name and lat is not None and lng is not None:
                try:
                    coordinates[name] = (float(lat), float(lng))
                except (TypeError, ValueError):
                    continue
        return coordinates

    def get_distance_lookup(self) -> Dict[Tuple[str, str], Dict[str, float]]:
        rows = self.load_seed_rows("village_distances")
        lookup: Dict[Tuple[str, str], Dict[str, float]] = {}
        for row in rows:
            village_a = str(get_any(row, ["village_a"], "")).strip().lower()
            village_b = str(get_any(row, ["village_b"], "")).strip().lower()
            if not village_a or not village_b:
                continue
            payload = {
                "distance": float(get_any(row, ["distance_km"], 0) or 0),
                "travel": float(get_any(row, ["travel_time_min"], 0) or 0),
            }
            lookup[(village_a, village_b)] = payload
            lookup[(village_b, village_a)] = payload
        return lookup

    def get_people_rows(self) -> List[Dict[str, Any]]:
        seed_rows = self.load_seed_rows("people")
        seed_by_id: Dict[str, Dict[str, Any]] = {}
        for row in seed_rows:
            pid = str(get_any(row, ["person_id", "student_id", "id"], "")).strip()
            if pid:
                seed_by_id[pid] = dict(row)

        runtime_state = self.load_runtime_state()
        rows: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for volunteer in runtime_state.volunteers:
            volunteer_id = str(volunteer.get("id") or volunteer.get("user_id") or "").strip()
            if not volunteer_id:
                continue
            profile = volunteer.get("profiles") or volunteer.get("profile") or {}
            source = dict(seed_by_id.get(volunteer_id, {}))
            skills = [str(skill).strip() for skill in volunteer.get("skills", []) if str(skill).strip()]
            skills_text = ";".join(skills)
            row = {
                **source,
                "person_id": volunteer_id,
                "id": volunteer_id,
                "user_id": volunteer.get("user_id") or volunteer_id,
                "name": profile.get("full_name") or source.get("name") or volunteer_id,
                "full_name": profile.get("full_name") or source.get("full_name") or volunteer_id,
                "email": profile.get("email") or source.get("email"),
                "phone": profile.get("phone") or source.get("phone"),
                "skills": skills_text,
                "text": skills_text,
                "availability": str(volunteer.get("availability") or source.get("availability") or volunteer.get("availability_status") or "available").strip().lower(),
                "availability_status": volunteer.get("availability_status") or source.get("availability_status") or "available",
                "home_location": volunteer.get("home_location") or source.get("home_location") or source.get("village") or "",
            }
            if "willingness_eff" not in row:
                row["willingness_eff"] = source.get("willingness_eff", 0.5)
            if "willingness_bias" not in row:
                row["willingness_bias"] = source.get("willingness_bias", 0.5)
            rows.append(row)
            seen.add(volunteer_id)

        for volunteer_id, row in seed_by_id.items():
            if volunteer_id in seen:
                continue
            rows.append(dict(row))

        return rows

    def record_learning_event(
        self,
        *,
        event_type: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        summary: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        text: Optional[str] = None,
    ) -> None:
        self.ensure_schema()
        event_id = f"evt-{uuid.uuid4().hex[:12]}"
        data = payload or {}
        embedding = _embedding_for_text(text or summary or json.dumps(data, ensure_ascii=False, sort_keys=True))
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO learning_events (id, event_type, entity_type, entity_id, summary, data, embedding, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    event_id,
                    event_type,
                    entity_type,
                    entity_id,
                    summary,
                    Jsonb(_jsonable(data)),
                    embedding,
                    _now_iso(),
                ),
            )

    def get_recent_learning_events(
        self,
        *,
        limit: int = 50,
        event_type: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        self.ensure_schema()
        clauses: List[str] = []
        params: List[Any] = []
        if event_type:
            clauses.append("event_type = %s")
            params.append(event_type)
        if entity_type:
            clauses.append("entity_type = %s")
            params.append(entity_type)
        if entity_id:
            clauses.append("entity_id = %s")
            params.append(entity_id)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, int(limit)))
        query = f"""
            SELECT id, event_type, entity_type, entity_id, summary, data, created_at
            FROM learning_events
            {where_sql}
            ORDER BY created_at DESC
            LIMIT %s
        """
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            {
                "id": row["id"],
                "event_type": row["event_type"],
                "entity_type": row["entity_type"],
                "entity_id": row["entity_id"],
                "summary": row["summary"],
                "data": dict(row["data"]) if row["data"] is not None else {},
                "created_at": row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else row["created_at"],
            }
            for row in rows
        ]

    def upsert_inventory_item(
        self,
        *,
        owner_type: str,
        owner_id: str,
        item_name: str,
        quantity: int,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.ensure_schema()
        item_id = hashlib.sha256(
            f"{owner_type}:{owner_id}:{item_name}".encode("utf-8")
        ).hexdigest()[:24]
        updated_at = _now_iso()
        payload = {
            "id": item_id,
            "owner_type": owner_type,
            "owner_id": owner_id,
            "item_name": item_name,
            "quantity": int(quantity),
            **(data or {}),
            "updated_at": updated_at,
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO inventory_items (id, owner_type, owner_id, item_name, quantity, data, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                SET owner_type = EXCLUDED.owner_type,
                    owner_id = EXCLUDED.owner_id,
                    item_name = EXCLUDED.item_name,
                    quantity = EXCLUDED.quantity,
                    data = EXCLUDED.data,
                    updated_at = EXCLUDED.updated_at
                """,
                (item_id, owner_type, owner_id, item_name, int(quantity), Jsonb(_jsonable(payload)), updated_at),
            )
        return payload

    def list_inventory(
        self,
        *,
        owner_type: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        self.ensure_schema()
        clauses: List[str] = []
        params: List[Any] = []
        if owner_type:
            clauses.append("owner_type = %s")
            params.append(owner_type)
        if owner_id:
            clauses.append("owner_id = %s")
            params.append(owner_id)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"""
            SELECT id, owner_type, owner_id, item_name, quantity, data, updated_at
            FROM inventory_items
            {where_sql}
            ORDER BY owner_type ASC, owner_id ASC, item_name ASC
        """
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            {
                "id": row["id"],
                "owner_type": row["owner_type"],
                "owner_id": row["owner_id"],
                "item_name": row["item_name"],
                "quantity": row["quantity"],
                "data": dict(row["data"]) if row["data"] is not None else {},
                "updated_at": row["updated_at"].isoformat() if hasattr(row["updated_at"], "isoformat") else row["updated_at"],
            }
            for row in rows
        ]

    def save_playbook(
        self,
        *,
        playbook_id: str,
        topic: str,
        village_name: Optional[str],
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        self.ensure_schema()
        payload = {
            "id": playbook_id,
            "topic": topic,
            "village_name": village_name,
            **data,
        }
        embedding = _embedding_for_text(" ".join([
            str(payload.get("title") or ""),
            str(payload.get("summary") or ""),
            str(payload.get("topic") or ""),
            str(payload.get("materials") or ""),
            str(payload.get("problem_title") or ""),
        ]))
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO knowledge_playbooks (id, topic, village_name, data, embedding, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                SET topic = EXCLUDED.topic,
                    village_name = EXCLUDED.village_name,
                    data = EXCLUDED.data,
                    embedding = EXCLUDED.embedding,
                    updated_at = EXCLUDED.updated_at
                """,
                (playbook_id, topic, village_name, Jsonb(_jsonable(payload)), embedding, _now_iso()),
            )
        return payload

    def list_playbooks(
        self,
        *,
        topic: Optional[str] = None,
        village_name: Optional[str] = None,
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        self.ensure_schema()
        clauses: List[str] = []
        params: List[Any] = []
        if topic:
            clauses.append("topic = %s")
            params.append(topic)
        if village_name:
            clauses.append("village_name = %s")
            params.append(village_name)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, int(limit)))
        query = f"""
            SELECT id, topic, village_name, data, updated_at
            FROM knowledge_playbooks
            {where_sql}
            ORDER BY updated_at DESC
            LIMIT %s
        """
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            {
                "id": row["id"],
                "topic": row["topic"],
                "village_name": row["village_name"],
                "data": dict(row["data"]) if row["data"] is not None else {},
                "updated_at": row["updated_at"].isoformat() if hasattr(row["updated_at"], "isoformat") else row["updated_at"],
            }
            for row in rows
        ]

    def record_followup_feedback(
        self,
        *,
        problem_id: str,
        source: str,
        response: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.ensure_schema()
        feedback_id = f"fb-{uuid.uuid4().hex[:12]}"
        payload = {
            "id": feedback_id,
            "problem_id": problem_id,
            "source": source,
            "response": response,
            **(data or {}),
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO followup_feedback (id, problem_id, source, response, data, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (feedback_id, problem_id, source, response, Jsonb(_jsonable(payload)), _now_iso()),
            )
        return payload

    def upsert_platform_record(
        self,
        *,
        record_type: str,
        record_id: str,
        data: Dict[str, Any],
        subtype: Optional[str] = None,
        owner_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        self.ensure_schema()
        payload = {
            "id": record_id,
            "record_type": record_type,
            "subtype": subtype,
            "owner_id": owner_id,
            "status": status,
            **data,
        }
        embedding = _embedding_for_text(" ".join(
            part for part in [
                record_type,
                subtype or "",
                owner_id or "",
                status or "",
                str(data.get("title") or data.get("name") or ""),
                str(data.get("summary") or data.get("description") or ""),
            ]
            if part
        ))
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO platform_records (id, record_type, subtype, owner_id, status, data, embedding, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                SET record_type = EXCLUDED.record_type,
                    subtype = EXCLUDED.subtype,
                    owner_id = EXCLUDED.owner_id,
                    status = EXCLUDED.status,
                    data = EXCLUDED.data,
                    embedding = EXCLUDED.embedding,
                    updated_at = EXCLUDED.updated_at
                """,
                (record_id, record_type, subtype, owner_id, status, Jsonb(_jsonable(payload)), embedding, _now_iso()),
            )
        return payload

    def list_platform_records(
        self,
        *,
        record_type: str,
        subtype: Optional[str] = None,
        owner_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        self.ensure_schema()
        clauses: List[str] = ["record_type = %s"]
        params: List[Any] = [record_type]
        if subtype:
            clauses.append("subtype = %s")
            params.append(subtype)
        if owner_id:
            clauses.append("owner_id = %s")
            params.append(owner_id)
        params.append(max(1, int(limit)))
        where_sql = "WHERE " + " AND ".join(clauses)
        query = f"""
            SELECT id, record_type, subtype, owner_id, status, data, updated_at
            FROM platform_records
            {where_sql}
            ORDER BY updated_at DESC
            LIMIT %s
        """
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            {
                "id": row["id"],
                "record_type": row["record_type"],
                "subtype": row["subtype"],
                "owner_id": row["owner_id"],
                "status": row["status"],
                "data": dict(row["data"]) if row["data"] is not None else {},
                "updated_at": row["updated_at"].isoformat() if hasattr(row["updated_at"], "isoformat") else row["updated_at"],
            }
            for row in rows
        ]

    def has_runtime_data(self) -> bool:
        self.ensure_schema()
        with self._connect() as conn:
            return any(
                self._table_has_rows(conn, table)
                for table in [
                    "runtime_profiles",
                    "runtime_volunteers",
                    "runtime_problems",
                    "runtime_media_assets",
                    "platform_records",
                ]
            )
