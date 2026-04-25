"""
recommender_service.py — Thin service wrapper around the Forge engine.

Previously held ML model loading and LightGBM inference.
Now just bridges the raw API config dict → ForgeConfig → run_forge().
No model file, no embeddings, no training data.
"""

import logging
from typing import Any, Dict, List, Optional

from forge import ForgeConfig, run_forge, load_distance_lookup, load_village_names, read_people

logger = logging.getLogger("recommender_service")


class RecommenderService:
    def __init__(self, model_path: str, people_csv: str, dataset_root: str):
        import os
        self.people_csv       = people_csv
        self.dataset_root     = dataset_root
        self.village_locations = os.path.join(dataset_root, "village_locations.csv")
        self.distance_csv      = os.path.join(dataset_root, "village_distances.csv")

        # Pre-load static lookup tables once at startup
        self._distance_lookup  = load_distance_lookup(self.distance_csv)
        self._village_names    = load_village_names(self.village_locations)

        # model_path kept for API compat but unused by Forge
        self.model_path = model_path
        logger.info("RecommenderService ready (Forge engine — no ML model required).")

    def set_model_path(self, model_path: str) -> None:
        """Legacy no-op: Forge does not use a trained model."""
        self.model_path = model_path
        logger.debug("set_model_path called (%s) — ignored by Forge engine.", model_path)

    def generate_recommendations(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point. Accepts the same flat dict the /recommend endpoint passes.
        Returns the same response schema as the old run_recommender() did.
        """
        people_csv = config.get("people_csv") or self.people_csv

        forge_cfg = ForgeConfig(
            people_csv                 = people_csv,
            proposal_text              = config.get("proposal_text", ""),
            village_locations          = config.get("village_locations") or self.village_locations,
            distance_csv               = config.get("distance_csv") or self.distance_csv,
            required_skills            = config.get("required_skills"),
            auto_extract               = config.get("auto_extract", True),
            proposal_location_override = (
                config.get("proposal_location_override")
                or config.get("village_name")
            ),
            task_start                 = config.get("task_start"),
            task_end                   = config.get("task_end"),
            team_size                  = config.get("team_size"),
            num_teams                  = int(config.get("num_teams") or 3),
            soft_cap                   = int(config.get("soft_cap") or 6),
            severity_override          = config.get("severity"),
            weekly_quota               = float(config.get("weekly_quota") or 5.0),
            overwork_penalty           = float(config.get("overwork_penalty") or 0.1),
            transcription              = config.get("transcription"),
            visual_tags                = config.get("visual_tags") or [],
            # Pre-loaded lookups (avoid disk I/O on every request)
            _distance_lookup           = self._distance_lookup,
            _village_names             = self._village_names,
        )

        try:
            return run_forge(forge_cfg)
        except Exception as e:
            logger.error("Forge engine error: %s", e, exc_info=True)
            raise

    def score_team(self, proposal_text: str, member_ids: List[str]) -> Dict[str, Any]:
        """
        Evaluate a manually selected team against a proposal.
        """
        from forge import (
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
        gm       = _geometric_mean([v["forge_score"] for v in scored])
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
