import json
import os
import concurrent.futures
from deep_translator import GoogleTranslator

langs = ['ta', 'bn', 'hi', 'te', 'mr', 'kn', 'ur', 'gu', 'ml', 'or', 'pa', 'as']

with open('frontend/src/locales/en.json', 'r') as f:
    en_data = json.load(f)

seeds = en_data.get('seed', {})
keys = list(seeds.keys())
values = list(seeds.values())

def chunk_list(lst, chunk_size):
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]

def translate_lang(lang):
    file_path = f'frontend/src/locales/{lang}.json'
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            target_data = json.load(f)
    else:
        target_data = {}

    target_seed = target_data.get('seed', {})
    
    missing_keys = []
    missing_values = []
    for k, v in zip(keys, values):
        if k not in target_seed:
            missing_keys.append(k)
            missing_values.append(v)
            
    if not missing_keys:
        print(f"[{lang}] OK")
        return

    print(f"[{lang}] Translating {len(missing_keys)} missing seeds...")
    
    translated_values = []
    translator = GoogleTranslator(source='en', target=lang)
    
    chunks = list(chunk_list(missing_values, 50))
    
    def process_chunk(chunk):
        try:
            return translator.translate_batch(chunk)
        except Exception:
            try:
                # Retry once
                return translator.translate_batch(chunk)
            except:
                return chunk # fallback
                
    # Use ThreadPool inside the language function to parallelize batches
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(process_chunk, chunks))
        
    for res in results:
        translated_values.extend(res)

    for k, v in zip(missing_keys, translated_values):
        target_seed[k] = v
        
    target_data['seed'] = target_seed
    
    with open(file_path, 'w') as f:
        json.dump(target_data, f, ensure_ascii=False, indent=4)
    print(f"[{lang}] Saved!")

# Only do 'ta' first synchronously to fix the user's issue immediately
translate_lang('ta')

# Then do the rest in parallel
with concurrent.futures.ThreadPoolExecutor(max_workers=11) as executor:
    executor.map(translate_lang, [l for l in langs if l != 'ta'])
    
print("All done!")
