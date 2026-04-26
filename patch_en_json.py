import json

with open('frontend/src/locales/en.json', 'r') as f:
    data = json.load(f)

# Update dashboard section
if 'dashboard' not in data: data['dashboard'] = {}
data['dashboard'].update({
    "clear": "Clear",
    "volunteers_selected": "volunteers selected",
    "home_location": "Home Location",
    "availability": "Availability",
    "willingness_eff": "Willingness (eff)",
    "full_skill_set": "Full Skill Set",
    "hide": "Hide",
    "view": "View",
    "search_volunteer_placeholder": "Search volunteers by name or skill..."
})

# Add common statuses to seed
if 'seed' not in data: data['seed'] = {}
data['seed'].update({
    "available": "Available",
    "busy": "Busy",
    "inactive": "Inactive",
    "rarely available": "Rarely Available",
    "immediately available": "Immediately Available",
    "generally available": "Generally Available",
    "unknown": "Unknown"
})

with open('frontend/src/locales/en.json', 'w') as f:
    json.dump(data, f, indent=4)
