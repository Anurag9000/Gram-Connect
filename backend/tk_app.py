import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from datetime import datetime, timedelta
import csv
import os

from recommender_service import RecommenderService, RecommendationConfig

DATASET_ROOT = os.path.join(os.path.dirname(__file__), "..", "data")
DEFAULT_MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.pkl")
DEFAULT_PEOPLE_CSV = os.path.join(DATASET_ROOT, "people.csv")
DEFAULT_VILLAGE_LOCATIONS = os.path.join(DATASET_ROOT, "village_locations.csv")
DEFAULT_DISTANCE_CSV = os.path.join(DATASET_ROOT, "village_distances.csv")

# Initialize service globally or on app init
recommender = RecommenderService(
    model_path=DEFAULT_MODEL_PATH,
    people_csv=DEFAULT_PEOPLE_CSV,
    dataset_root=DATASET_ROOT
)

class RecommendationApp(tk.Tk):
    # ... (init stays same) ...

    # ... (skipping to run_recommendation) ...

    def run_recommendation(self):
        problem = self.problem_text.get("1.0", "end").strip()
        if not problem:
            messagebox.showerror("Input error", "Please enter a problem statement.")
            return
        
        # ... (date parsing logic stays same) ...
        try:
            start_dt = datetime.strptime(self.start_var.get().strip(), "%Y-%m-%d %H:%M")
        except ValueError:
            messagebox.showerror("Input error", "Task start must be in format YYYY-MM-DD HH:MM")
            return
        try:
            team_size = max(1, int(self.team_size_var.get()))
            num_teams = max(1, int(self.num_teams_var.get()))
            duration_hours = max(0.5, float(self.duration_var.get()))
        except (ValueError, tk.TclError):
            messagebox.showerror("Input error", "Team size, number of teams, and duration must be numeric.")
            return

        end_dt = start_dt + timedelta(hours=duration_hours)
        severity = self.severity_var.get()
        
        # Construct dict payload directly for the Service
        payload = {
            "proposal_text": problem,
            "proposal_location_override": self.village_var.get().strip() or None,
            "task_start": start_dt.isoformat(),
            "task_end": end_dt.isoformat(),
            "team_size": team_size,
            "num_teams": num_teams,
            "severity": None if severity == "AUTO" else severity,
            "schedule_csv": self.schedule_var.get().strip() or None,
            "weekly_quota": float(self.quota_var.get()),
            "overwork_penalty": float(self.penalty_var.get()),
            "auto_extract": True,
            "threshold": 0.25,
            # Pass globals if needed, but Service has defaults. 
            # We explicitly pass model path from UI if changed? 
            # The service was init with defaults. If we want dynamic model path, we'd need to re-init service.
            # For this fix, let's assume the UI model path is informative only or correctly set at startup.
        }
        
        # Re-initialize service if model path changed in UI
        current_model = self.model_var.get().strip()
        if current_model and current_model != recommender.model_path:
             recommender.model_path = current_model
             # Force reload bundle logic would be needed in service, but let's just update path.

        try:
            results = recommender.generate_recommendations(payload)
        except Exception as exc:
            messagebox.showerror("Recommendation error", str(exc))
            return

        self._display_results(results)

    def _display_results(self, results):
        self.output.delete("1.0", "end")
        summary = results.get("severity_detected", "N/A")
        source = results.get("severity_source", "auto")
        location = results.get("proposal_location") or "Unknown"
        self.output.insert("end", f"Severity: {summary} (source: {source})\n")
        self.output.insert("end", f"Proposal location: {location}\n\n")

        teams = results.get("teams", [])
        if not teams:
            self.output.insert("end", "No teams returned.\n")
            return
        for idx, team in enumerate(teams, start=1):
            self.output.insert("end", f"Team {idx}: {team.get('team_names','(Unnamed)')}\n")
            self.output.insert("end", f"  Team size: {team.get('team_size')}\n")
            self.output.insert("end", f"  Goodness: {team.get('goodness')} | Coverage: {team.get('coverage')} | k-robustness: {team.get('k_robustness')}\n")
            self.output.insert("end", f"  Willingness avg/min: {team.get('willingness_avg')} / {team.get('willingness_min')}\n")
            members = team.get("members", [])
            for member in members:
                name = member.get("name") or member.get("person_id")
                skills = ", ".join(member.get("skills", []))
                self.output.insert("end", f"    - {name} | W={member.get('willingness')} | Dist={member.get('distance_km')} km | Overwork={member.get('overwork_hours')}h\n")
                if skills:
                    self.output.insert("end", f"      Skills: {skills}\n")
            self.output.insert("end", "\n")

if __name__ == "__main__":
    app = RecommendationApp()
    app.mainloop()
