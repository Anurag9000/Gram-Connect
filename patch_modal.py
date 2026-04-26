import json

with open('frontend/src/locales/en.json', 'r') as f:
    data = json.load(f)

if 'dashboard' not in data:
    data['dashboard'] = {}

data['dashboard'].update({
    "hide": "Hide",
    "view": "View",
    "home_location": "Home Location",
    "availability": "Availability",
    "willingness_eff": "Willingness (eff)",
    "full_skill_set": "Full Skill Set",
    "team_score": "Team Score:",
    "skill_coverage": "Skill Coverage:",
    "avg_dist": "Avg Dist:",
    "avg_will": "Avg Will:",
    "domain_exp": "Domain Exp.",
    "willingness": "Willingness",
    "distance": "Distance",
    "avail_level": "Avail Level",
    "skills": "Skills:"
})

with open('frontend/src/locales/en.json', 'w') as f:
    json.dump(data, f, indent=4)
