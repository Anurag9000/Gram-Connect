import os
import pickle
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from m3_recommend import run_recommender, RecommendationConfig
from utils import get_any, SEVERITY_LABELS

logger = logging.getLogger("recommender_service")

class RecommenderService:
    def __init__(self, model_path: str, people_csv: str, dataset_root: str):
        self.model_path = model_path
        self.people_csv = people_csv
        self.dataset_root = dataset_root
        
        # Paths for auxiliary data
        self.village_locations = os.path.join(dataset_root, "village_locations.csv")
        self.distance_csv = os.path.join(dataset_root, "village_distances.csv")
        
        if not os.path.exists(model_path):
            logger.warning(f"Model file not found at {model_path}. Optimization will be disabled until trained.")
            self.model_bundle = None
        else:
            logger.info(f"Loading M3 Model from {model_path}...")
            with open(model_path, "rb") as f:
                self.model_bundle = pickle.load(f)
            logger.info("Model loaded successfully.")

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

        # Prepare RecommendationConfig for the core engine
        m3_cfg = RecommendationConfig(
            model=self.model_path,
            people=self.people_csv,
            proposal_text=proposal_text,
            transcription=transcription,
            visual_tags=visual_tags,
            task_start=task_start,
            task_end=task_end,
            village_locations=self.village_locations,
            distance_csv=self.distance_csv,
            # Pass through other optional parameters if present in config
            required_skills=config.get("required_skills"),
            auto_extract=config.get("auto_extract", True),
            threshold=float(config.get("threshold", 0.25)),
            tau=float(config.get("tau", 0.35)),
            weekly_quota=float(config.get("weekly_quota", 5.0)),
            soft_cap=int(config.get("soft_cap", 6)),
            k_robust=int(config.get("k_robust", 1)),
            severity_override=config.get("severity"),
            loaded_bundle=self.model_bundle
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
