"""
recommender_service.py — Thin service wrapper around the Nexus engine.

Previously held ML model loading and LightGBM inference.
Now just bridges the raw API config dict → NexusConfig → run_nexus().
No model file, no embeddings, no training data.
"""

import logging
import os
import pickle
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from nexus import NexusConfig, run_nexus, load_distance_lookup, load_village_names, read_people
from postgres_store import PostgresStore

logger = logging.getLogger("recommender_service")


@dataclass
class RecommendationConfig:
    people_csv: str
    proposal_text: str
    village_locations: str
    distance_csv: str
    required_skills: Optional[List[str]] = None
    auto_extract: bool = True
    proposal_location_override: Optional[str] = None
    task_start: Optional[str] = None
    task_end: Optional[str] = None
    team_size: Optional[int] = None
    num_teams: int = 3
    soft_cap: int = 6
    severity_override: Optional[str] = None
    weekly_quota: float = 5.0
    overwork_penalty: float = 0.1
    transcription: Optional[str] = None
    visual_tags: Optional[List[str]] = None
    schedule_csv: Optional[str] = None
    size_buckets: Optional[str] = None
    lambda_red: float = 1.0
    lambda_size: float = 1.0
    lambda_will: float = 0.5
    topk_swap: int = 10
    k_robust: int = 1
    distance_scale: float = 50.0
    distance_decay: float = 30.0
    loaded_bundle: Optional[Any] = None


def run_recommender(config: RecommendationConfig) -> Dict[str, Any]:
    nexus_cfg = NexusConfig(
        people_csv=config.people_csv,
        proposal_text=config.proposal_text,
        village_locations=config.village_locations,
        distance_csv=config.distance_csv,
        required_skills=config.required_skills,
        auto_extract=config.auto_extract,
        proposal_location_override=config.proposal_location_override,
        task_start=config.task_start,
        task_end=config.task_end,
        team_size=config.team_size,
        num_teams=config.num_teams,
        soft_cap=config.soft_cap,
        severity_override=config.severity_override,
        weekly_quota=config.weekly_quota,
        overwork_penalty=config.overwork_penalty,
        transcription=config.transcription,
        visual_tags=config.visual_tags,
        schedule_csv=config.schedule_csv,
        _distance_lookup=config.loaded_bundle.get("_distance_lookup") if isinstance(config.loaded_bundle, dict) else None,
        _village_names=config.loaded_bundle.get("_village_names") if isinstance(config.loaded_bundle, dict) else None,
    )
    return run_nexus(nexus_cfg)


class RecommenderService:
    def __init__(self, model_path: str, people_csv: str, dataset_root: str):
        self.people_csv       = people_csv
        self.dataset_root     = dataset_root
        self.village_locations = os.path.join(dataset_root, "village_locations.csv")
        self.distance_csv      = os.path.join(dataset_root, "village_distances.csv")
        self._store = PostgresStore.from_env()

        # Pre-load static lookup tables once at startup; prefer Postgres when available.
        try:
            self._store.ensure_schema()
            if self._store.has_runtime_data() or self._store.load_seed_rows("people"):
                self._distance_lookup = self._store.get_distance_lookup()
                self._village_names = self._store.get_village_names()
            else:
                self._distance_lookup  = load_distance_lookup(self.distance_csv)
                self._village_names    = load_village_names(self.village_locations)
        except Exception as exc:
            logger.warning("Postgres lookup bootstrap failed, falling back to CSV files: %s", exc)
            self._distance_lookup  = load_distance_lookup(self.distance_csv)
            self._village_names    = load_village_names(self.village_locations)

        # model_path kept for API compat but unused by Nexus
        self.model_path = model_path
        self.model_bundle = None
        if model_path and os.path.exists(model_path):
            try:
                with open(model_path, "rb") as handle:
                    self.model_bundle = pickle.load(handle)
            except Exception as exc:
                logger.warning("Failed to load legacy model bundle from %s: %s", model_path, exc)
                self.model_bundle = None
        logger.info("RecommenderService ready (Nexus engine — no ML model required).")

    def set_model_path(self, model_path: str) -> None:
        """Legacy no-op: Nexus does not use a trained model."""
        self.model_path = model_path
        logger.debug("set_model_path called (%s) — ignored by Nexus engine.", model_path)

    def generate_recommendations(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point. Accepts the same flat dict the /recommend endpoint passes.
        Returns the same response schema as the old run_recommender() did.
        """
        people_csv = config.get("people_csv") or self.people_csv
        people_rows = config.get("people_rows")
        use_database = bool(config.get("use_database"))
        if people_rows is None and use_database:
            try:
                if self._store:
                    people_rows = self._store.get_people_rows()
            except Exception as exc:
                logger.warning("Failed to load people rows from Postgres, falling back to CSV: %s", exc)
                people_rows = None

        distance_lookup = config.get("distance_lookup") or (self._store.get_distance_lookup() if use_database and self._store else self._distance_lookup)
        village_names = config.get("village_names") or (self._store.get_village_names() if use_database and self._store else self._village_names)

        legacy_cfg = RecommendationConfig(
            people_csv=people_csv,
            proposal_text=config.get("proposal_text", ""),
            village_locations=config.get("village_locations") or self.village_locations,
            distance_csv=config.get("distance_csv") or self.distance_csv,
            required_skills=config.get("required_skills"),
            auto_extract=config.get("auto_extract", True),
            proposal_location_override=config.get("proposal_location_override") or config.get("village_name"),
            task_start=config.get("task_start"),
            task_end=config.get("task_end"),
            team_size=config.get("team_size"),
            num_teams=int(config.get("num_teams") or 3),
            soft_cap=int(config.get("soft_cap") or 6),
            severity_override=config.get("severity"),
            weekly_quota=float(config.get("weekly_quota") or 5.0),
            overwork_penalty=float(config.get("overwork_penalty") or 0.1),
            transcription=config.get("transcription"),
            visual_tags=config.get("visual_tags") or [],
            schedule_csv=config.get("schedule_csv"),
            size_buckets=config.get("size_buckets"),
            lambda_red=float(config.get("lambda_red") or 1.0),
            lambda_size=float(config.get("lambda_size") or 1.0),
            lambda_will=float(config.get("lambda_will") or 0.5),
            topk_swap=int(config.get("topk_swap") or 10),
            k_robust=int(config.get("k_robust") or 1),
            distance_scale=float(config.get("distance_scale") or 50.0),
            distance_decay=float(config.get("distance_decay") or 30.0),
            loaded_bundle={
                "_distance_lookup": self._distance_lookup,
                "_village_names": self._village_names,
            },
        )

        try:
            if use_database or people_rows is not None:
                nexus_cfg = NexusConfig(
                    people_csv=people_csv,
                    proposal_text=legacy_cfg.proposal_text,
                    village_locations=legacy_cfg.village_locations,
                    distance_csv=legacy_cfg.distance_csv,
                    required_skills=legacy_cfg.required_skills,
                    auto_extract=legacy_cfg.auto_extract,
                    proposal_location_override=legacy_cfg.proposal_location_override,
                    task_start=legacy_cfg.task_start,
                    task_end=legacy_cfg.task_end,
                    team_size=legacy_cfg.team_size,
                    num_teams=legacy_cfg.num_teams,
                    soft_cap=legacy_cfg.soft_cap,
                    severity_override=legacy_cfg.severity_override,
                    weekly_quota=legacy_cfg.weekly_quota,
                    overwork_penalty=legacy_cfg.overwork_penalty,
                    transcription=legacy_cfg.transcription,
                    visual_tags=legacy_cfg.visual_tags,
                    schedule_csv=legacy_cfg.schedule_csv,
                    _people=people_rows,
                    _distance_lookup=distance_lookup,
                    _village_names=village_names,
                )
                return run_nexus(nexus_cfg)
            return run_recommender(legacy_cfg)
        except Exception as e:
            logger.error("Nexus engine error: %s", e, exc_info=True)
            raise

    def score_team(self, proposal_text: str, member_ids: List[str]) -> Dict[str, Any]:
        """
        Evaluate a manually selected team against a proposal.
        """
        from nexus import (
            read_people, extract_required_skills, score_volunteer,
            _team_coverage, _geometric_mean, TEAM_DISTANCE_WEIGHT,
        )

        all_people = read_people(self.people_csv)
        people_map = {p["person_id"]: p for p in all_people}
        team_members = [people_map[pid] for pid in member_ids if pid in people_map]

        if not team_members:
            return {"goodness": 0.0, "coverage": 0.0}

        required = extract_required_skills(proposal_text)
        scored   = [
            score_volunteer(v, required, "", self._distance_lookup, 1)
            for v in team_members
        ]
        coverage = _team_coverage(scored, required)
        gm       = _geometric_mean([v["nexus_score"] for v in scored])
        avg_dist = sum(v["distance_km"] for v in scored) / max(len(scored), 1)
        team_score = coverage * gm - TEAM_DISTANCE_WEIGHT * avg_dist

        return {
            "goodness":  round(team_score, 4),
            "coverage":  round(coverage, 4),
            "members":   [
                {k: v[k] for k in ["person_id", "name", "domain_score", "willingness_score", "distance_km"]}
                for v in scored
            ],
        }
