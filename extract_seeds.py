import csv
import json
import os
import glob

seeds = {}

def add_seed(text):
    if not text: return
    if isinstance(text, (list, tuple)):
        for item in text: add_seed(item)
        return
    text = str(text).strip()
    # Ignore purely numeric strings, dates, and very short codes
    if len(text) <= 2: return
    if text.replace('.','').isdigit(): return
    if text.startswith('http'): return
    
    seeds[text] = text

def process_csv(fpath):
    print(f"Processing {fpath}...")
    try:
        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
            # Try to detect delimiter
            sample = f.read(2048)
            f.seek(0)
            if not sample: return
            
            dialect = csv.Sniffer().sniff(sample)
            reader = csv.reader(f, dialect)
            
            for row in reader:
                for cell in row:
                    # Handle common separators in our dataset
                    if ';' in cell and ' ' not in cell:
                        for s in cell.split(';'): add_seed(s)
                    elif '|' in cell:
                        for s in cell.split('|'): add_seed(s)
                    elif cell.startswith('[') and cell.endswith(']'):
                        try:
                            items = json.loads(cell.replace("'", '"'))
                            if isinstance(items, list):
                                for item in items: add_seed(item)
                        except:
                            add_seed(cell)
                    else:
                        add_seed(cell)
    except Exception as e:
        print(f"Error processing {fpath}: {e}")

# Crawl backend and data directories for ALL CSVs
target_dirs = ['backend', 'data']
for d in target_dirs:
    for fpath in glob.glob(os.path.join(d, "*.csv")):
        process_csv(fpath)

# Add hardcoded fallback statuses
for s in ['available', 'busy', 'inactive', 'rarely available', 'immediately available', 'generally available', 'pending', 'in progress', 'completed']:
    add_seed(s)

with open('frontend/src/locales/en.json', 'r') as f:
    en_data = json.load(f)

if 'seed' not in en_data:
    en_data['seed'] = {}

# Merge into registry
for k, v in seeds.items():
    en_data['seed'][k] = v

with open('frontend/src/locales/en.json', 'w') as f:
    json.dump(en_data, f, indent=4)

print(f"Done! Registry now contains {len(en_data['seed'])} unique seed strings.")
