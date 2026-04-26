import json

with open('frontend/src/locales/en.json', 'r') as f:
    data = json.load(f)

# Add missing common keys
data['common'].update({
    "pending": "Pending",
    "in_progress": "In Progress",
    "completed": "Completed",
    "high": "High",
    "normal": "Normal",
    "low": "Low",
    "water-sanitation": "Water & Sanitation",
    "infrastructure": "Infrastructure",
    "health-nutrition": "Health & Nutrition",
    "agriculture-environment": "Agriculture & Environment",
    "education-digital": "Education & Digital",
    "livelihood-governance": "Livelihood & Governance",
    "others": "Others",
    "education": "Education",
    "health": "Health",
    "digital": "Digital"
})

# Add missing map keys
data['map'] = {
    "live_geospatial_view": "Live Geospatial View",
    "title": "Problem locations & volunteer deployments",
    "subtitle": "Browse reported issues on the map, filter by location or status, and inspect the live problem stream.",
    "back_to_dashboard": "Back to dashboard",
    "all_problems": "All problems",
    "filter_village": "Filter by village…",
    "showing": "Showing",
    "problems": "problems",
    "problem": "problem",
    "in": "in",
    "problem_map": "Problem map",
    "markers": "markers",
    "all_cases": "All cases",
    "live_backend_state": "live backend state",
    "loading_map": "Loading map…",
    "loading": "Loading…",
    "no_problems": "No problems match the current filters."
}

# Add home highlight
data['home']['hero_heading_highlight'] = "Intelligent Action"

# Add skills
data['skills'] = {
    "digital literacy": "Digital Literacy",
    "teaching": "Teaching",
    "excel training": "Excel Training",
    "household survey": "Household Survey",
    "Computer Repair": "Computer Repair",
    "Teaching": "Teaching",
    "Plumbing": "Plumbing",
    "Electrical Work": "Electrical Work",
    "Construction": "Construction",
    "Digital Literacy": "Digital Literacy",
    "Agriculture": "Agriculture",
    "Healthcare": "Healthcare",
    "Tutoring": "Tutoring",
    "Web Development": "Web Development",
    "Marketing": "Marketing",
    "Accounting": "Accounting"
}

with open('frontend/src/locales/en.json', 'w') as f:
    json.dump(data, f, indent=4)
