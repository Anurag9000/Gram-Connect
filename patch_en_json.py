import json

with open('frontend/src/locales/en.json', 'r') as f:
    data = json.load(f)

# Update dashboard section
if 'dashboard' not in data: data['dashboard'] = {}
data['dashboard'].update({
    "team_score": "Team Score:",
    "skill_coverage": "Skill Coverage:",
    "avg_dist": "Avg Dist:",
    "avg_will": "Avg Will:",
    "domain_exp": "Domain Exp.",
    "willingness": "Willingness",
    "distance": "Distance",
    "avail_level": "Avail Level",
    "skills": "Skills:",
    "why_this_team": "Why this team? (Nexus Engine)",
    "ranked": "Ranked",
    "skill_coverage_label": "skill coverage",
    "avg_will_label": "avg willingness",
    "km_avg_dist": "km avg distance",
    "all_local": "all local to problem village",
    "nexus_explanation": "Individual score = DOMAIN\u00b2 * WILL * AVAIL\u2070\u22c5\u2075 * PROX * FRESH\u2070\u22c5\u2075. Multiplicative: any factor at zero eliminates the candidate regardless of other strengths. Teams ranked by skill coverage first, then by geometric mean of member scores."
})

# Update common section
if 'common' not in data: data['common'] = {}
data['common'].update({
    "pending": "Pending",
    "in_progress": "In Progress",
    "completed": "Completed",
    "high": "High",
    "normal": "Normal",
    "low": "Low",
    "all": "All"
})

with open('frontend/src/locales/en.json', 'w') as f:
    json.dump(data, f, indent=4)
