import os
import pickle
import logging
from typing import List, Dict, Any, Optional
from datetime import timedelta

from m3_recommend import run_recommender, RecommendationConfig
from utils import get_any

logger = logging.getLogger("recommender_service")

class RecommenderService:
    def __init__(self, model_path: str, people_csv: str, dataset_root: str):
        self.model_path = model_path
        self.people_csv = people_csv
        self.dataset_root = dataset_root
        
        # Paths for auxiliary data
        self.village_locations = os.path.join(dataset_root, "village_locations.csv")
        self.distance_csv = os.path.join(dataset_root, "village_distances.csv")
        
        self.model_bundle = self._load_model_bundle(model_path)

    def _load_model_bundle(self, model_path: str):
        if not os.path.exists(model_path):
            logger.warning(f"Model file not found at {model_path}. Optimization will be disabled until trained.")
            return None

        logger.info(f"Loading M3 Model from {model_path}...")
        with open(model_path, "rb") as f:
            bundle = pickle.load(f)
        logger.info("Model loaded successfully.")
        return bundle

    def set_model_path(self, model_path: str) -> None:
        if model_path == self.model_path:
            return
        self.model_path = model_path
        self.model_bundle = self._load_model_bundle(model_path)

    def generate_recommendations(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for generating AI team recommendations.
        """
        # Extract inputs from config
        proposal_text = config.get("proposal_text", "")
        transcription = config.get("transcription")
        visual_tags = config.get("visual_tags", [])
        
        task_start = config.get("task_start")
        duration_hours = float(config.get("duration_hours", 4.0))
        
        # Calculate task_end if not provided
        if task_start and not config.get("task_end"):
            try:
                from utils import parse_datetime
                start_dt = parse_datetime(task_start, "task_start")
                end_dt = start_dt + timedelta(hours=duration_hours)
                task_end = end_dt.isoformat()
            except Exception as e:
                logger.warning(f"Failed to parse task_start for duration calculation: {e}")
                task_end = task_start # fallback
        else:
            task_end = config.get("task_end", task_start)

        model_path = self.model_path
        people_csv = config.get("people_csv") or self.people_csv
        village_locations = config.get("village_locations") or self.village_locations
        distance_csv = config.get("distance_csv") or self.distance_csv

        loaded_bundle = self.model_bundle
        if not loaded_bundle and not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Trained model bundle not found at {model_path}. "
                "Run the canonical training bootstrap before serving recommendations."
            )

        # Prepare RecommendationConfig for the core engine
        m3_cfg = RecommendationConfig(
            model=model_path,
            people=people_csv,
            proposal_text=proposal_text,
            transcription=transcription,
            visual_tags=visual_tags,
            task_start=task_start,
            task_end=task_end,
            proposal_location_override=config.get("proposal_location_override") or config.get("village_name"),
            village_locations=village_locations,
            distance_csv=distance_csv,
            # Pass through other optional parameters if present in config
            required_skills=config.get("required_skills"),
            skills_json=config.get("skills_json"),
            auto_extract=config.get("auto_extract", True),
            threshold=float(config.get("threshold", 0.25)),
            tau=float(config.get("tau", 0.35)),
            weekly_quota=float(config.get("weekly_quota", 5.0)),
            overwork_penalty=float(config.get("overwork_penalty", 0.1)),
            soft_cap=int(config.get("soft_cap", 6)),
            topk_swap=int(config.get("topk_swap", 10)),
            k_robust=int(config.get("k_robust", 1)),
            lambda_red=float(config.get("lambda_red", 1.0)),
            lambda_size=float(config.get("lambda_size", 1.0)),
            lambda_will=float(config.get("lambda_will", 0.5)),
            size_buckets=config.get("size_buckets"),
            team_size=config.get("team_size"),
            num_teams=config.get("num_teams"),
            severity_override=config.get("severity"),
            schedule_csv=config.get("schedule_csv"),
            distance_scale=float(config.get("distance_scale", 50.0)),
            distance_decay=float(config.get("distance_decay", 30.0)),
            loaded_bundle=loaded_bundle,
        )

        try:
            return run_recommender(m3_cfg)
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}", exc_info=True)
            raise

    def score_team(self, proposal_text: str, member_ids: List[str]) -> Dict[str, Any]:
        """
        Evaluate a specific manually selected team.
        """
        from m3_recommend import team_metrics, goodness
        from utils import read_csv_norm
        import pickle
        
        if not self.model_bundle:
            return {"goodness": 0, "coverage": 0}
            
        bundle = self.model_bundle
        
        all_people = read_csv_norm(self.people_csv)
        people_map = {get_any(p, ["person_id", "id"]): p for p in all_people}
        team_members = [people_map[pid] for pid in member_ids if pid in people_map]
        
        if not team_members:
            return {"goodness": 0, "coverage": 0}
            
        from m3_recommend import _auto_extract_skills
        required = _auto_extract_skills(proposal_text, 0.25)
        
        mets = team_metrics(required, team_members, bundle["backend"], bundle["people_model"])
        score = goodness(mets)
        
        return {
            "goodness": round(score, 4),
            "metrics": {k: round(v, 3) for k, v in mets.items()}
        }
