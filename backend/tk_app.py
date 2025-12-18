import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from datetime import datetime, timedelta
import csv
import os

from recommender_service import RecommendationConfig, generate_recommendations

DATASET_ROOT = os.path.join(os.path.dirname(__file__), "..", "data")
DEFAULT_MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.pkl")
DEFAULT_PEOPLE_CSV = os.path.join(DATASET_ROOT, "people.csv")
DEFAULT_VILLAGE_LOCATIONS = os.path.join(DATASET_ROOT, "village_locations.csv")
DEFAULT_DISTANCE_CSV = os.path.join(DATASET_ROOT, "village_distances.csv")

class RecommendationApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SocialCode Team Recommender")
        self.geometry("900x700")
        self._build_ui()

    def _build_ui(self):
        main = ttk.Frame(self, padding=12)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="Problem statement:").grid(row=0, column=0, sticky="w")
        self.problem_text = tk.Text(main, height=6, width=70)
        self.problem_text.grid(row=1, column=0, columnspan=3, sticky="we", pady=4)

        ttk.Label(main, text="Village (Gram):").grid(row=2, column=0, sticky="w", pady=(8,0))
        self.village_var = tk.StringVar()
        village_values = self._load_villages()
        self.village_combo = ttk.Combobox(main, textvariable=self.village_var, values=village_values, state="readonly", width=40)
        self.village_combo.grid(row=3, column=0, sticky="w")
        if village_values:
            self.village_combo.current(0)

        ttk.Label(main, text="Team size (volunteers per team):").grid(row=2, column=1, sticky="w", pady=(8,0))
        self.team_size_var = tk.IntVar(value=4)
        ttk.Entry(main, textvariable=self.team_size_var, width=10).grid(row=3, column=1, sticky="w")

        ttk.Label(main, text="Number of teams:").grid(row=2, column=2, sticky="w", pady=(8,0))
        self.num_teams_var = tk.IntVar(value=5)
        ttk.Entry(main, textvariable=self.num_teams_var, width=10).grid(row=3, column=2, sticky="w")

        ttk.Label(main, text="Task start (YYYY-MM-DD HH:MM):").grid(row=4, column=0, sticky="w", pady=(8,0))
        default_start = datetime.now().replace(second=0, microsecond=0).strftime("%Y-%m-%d %H:%M")
        self.start_var = tk.StringVar(value=default_start)
        ttk.Entry(main, textvariable=self.start_var, width=20).grid(row=5, column=0, sticky="w")

        ttk.Label(main, text="Duration (hours):").grid(row=4, column=1, sticky="w", pady=(8,0))
        self.duration_var = tk.DoubleVar(value=4.0)
        ttk.Entry(main, textvariable=self.duration_var, width=10).grid(row=5, column=1, sticky="w")

        ttk.Label(main, text="Severity override:").grid(row=4, column=2, sticky="w", pady=(8,0))
        self.severity_var = tk.StringVar(value="AUTO")
        ttk.Combobox(main, textvariable=self.severity_var, values=["AUTO","LOW","NORMAL","HIGH"], state="readonly", width=10).grid(row=5, column=2, sticky="w")

        ttk.Label(main, text="Weekly quota (hours):").grid(row=6, column=0, sticky="w", pady=(8,0))
        self.quota_var = tk.DoubleVar(value=5.0)
        ttk.Entry(main, textvariable=self.quota_var, width=10).grid(row=7, column=0, sticky="w")

        ttk.Label(main, text="Overwork penalty:").grid(row=6, column=1, sticky="w", pady=(8,0))
        self.penalty_var = tk.DoubleVar(value=0.1)
        ttk.Entry(main, textvariable=self.penalty_var, width=10).grid(row=7, column=1, sticky="w")

        ttk.Label(main, text="Schedule CSV (optional):").grid(row=6, column=2, sticky="w", pady=(8,0))
        self.schedule_var = tk.StringVar()
        ttk.Entry(main, textvariable=self.schedule_var, width=30).grid(row=7, column=2, sticky="w")

        ttk.Label(main, text="Model path:").grid(row=8, column=0, sticky="w", pady=(8,0))
        self.model_var = tk.StringVar(value=DEFAULT_MODEL_PATH)
        ttk.Entry(main, textvariable=self.model_var, width=40).grid(row=9, column=0, sticky="w")

        run_button = ttk.Button(main, text="Generate Teams", command=self.run_recommendation)
        run_button.grid(row=9, column=1, pady=12, sticky="w")

        self.output = scrolledtext.ScrolledText(main, wrap=tk.WORD, width=100, height=20)
        self.output.grid(row=10, column=0, columnspan=3, pady=(10,0), sticky="nsew")

        main.rowconfigure(10, weight=1)
        main.columnconfigure(0, weight=1)

    def _load_villages(self):
        try:
            with open(DEFAULT_VILLAGE_LOCATIONS, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                return [row.get('village_name', '').strip() for row in reader if row.get('village_name')]
        except FileNotFoundError:
            messagebox.showwarning("Dataset missing", f"Could not find {DEFAULT_VILLAGE_LOCATIONS}")
            return []

    def run_recommendation(self):
        problem = self.problem_text.get("1.0", "end").strip()
        if not problem:
            messagebox.showerror("Input error", "Please enter a problem statement.")
            return
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
        payload = RecommendationConfig(
            model=self.model_var.get().strip() or DEFAULT_MODEL_PATH,
            people=DEFAULT_PEOPLE_CSV,
            proposal_text=problem,
            proposal_location_override=self.village_var.get().strip() or None,
            task_start=start_dt.isoformat(),
            task_end=end_dt.isoformat(),
            team_size=team_size,
            num_teams=num_teams,
            severity_override=None if severity == "AUTO" else severity,
            schedule_csv=self.schedule_var.get().strip() or None,
            weekly_quota=float(self.quota_var.get()),
            overwork_penalty=float(self.penalty_var.get()),
            auto_extract=True,
            threshold=0.25,
            lambda_red=1.0,
            lambda_size=1.0,
            lambda_will=0.5,
            village_locations=DEFAULT_VILLAGE_LOCATIONS,
            distance_csv=DEFAULT_DISTANCE_CSV,
            distance_scale=50.0,
            distance_decay=30.0,
        )
        try:
            results = generate_recommendations(payload, write_output=False)
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
