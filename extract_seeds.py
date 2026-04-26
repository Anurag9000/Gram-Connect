import csv
import json
import os

seeds = {}

def add_seed(text):
    if not text: return
    text = str(text).strip()
    if text:
        seeds[text] = text

# Parse proposals.csv (problems)
with open('data/proposals.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        add_seed(row.get('title'))
        add_seed(row.get('description'))
        add_seed(row.get('village_name'))
        add_seed(row.get('village_address'))

# Parse people.csv (volunteers & villagers)
with open('data/people.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        add_seed(row.get('name'))
        # Skills might be JSON arrays or pipe-separated
        skills = row.get('skills', '')
        if '[' in skills:
            try:
                for s in json.loads(skills):
                    add_seed(s)
            except:
                pass
        else:
            for s in skills.split('|'):
                add_seed(s)

with open('frontend/src/locales/en.json', 'r') as f:
    en_data = json.load(f)

if 'seed' not in en_data:
    en_data['seed'] = {}

en_data['seed'].update(seeds)

# Also add common UI strings the user pointed out
if 'common' not in en_data: en_data['common'] = {}
en_data['common'].update({"all": "All"})

with open('frontend/src/locales/en.json', 'w') as f:
    json.dump(en_data, f, indent=4)

print(f"Extracted {len(seeds)} unique seed strings.")
