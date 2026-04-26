import json
import os
from deep_translator import GoogleTranslator
from concurrent.futures import ThreadPoolExecutor

def get_missing_keys(en_dict, target_dict):
    missing = {}
    for k, v in en_dict.items():
        if isinstance(v, dict):
            if k not in target_dict or not isinstance(target_dict[k], dict):
                missing[k] = v
            else:
                sub_missing = get_missing_keys(v, target_dict[k])
                if sub_missing:
                    missing[k] = sub_missing
        else:
            if k not in target_dict:
                missing[k] = v
    return missing

def translate_values(d, lang_code, translator):
    translated = {}
    for k, v in d.items():
        if isinstance(v, dict):
            translated[k] = translate_values(v, lang_code, translator)
        else:
            try:
                if not v.strip():
                    translated[k] = v
                    continue
                result = translator.translate(v)
                translated[k] = result
            except Exception as e:
                print(f"Error translating {v} to {lang_code}: {e}")
                translated[k] = v # fallback
    return translated

def merge_dicts(base, overlay):
    for k, v in overlay.items():
        if isinstance(v, dict):
            base[k] = merge_dicts(base.get(k, {}), v)
        else:
            base[k] = v
    return base

def process_lang(lang, en_data):
    file_path = f'frontend/src/locales/{lang}.json'
    print(f"Processing {lang}...")
    
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            target_data = json.load(f)
    else:
        target_data = {}
        
    missing = get_missing_keys(en_data, target_data)
    
    if not missing:
        print(f"[{lang}] Already up to date.")
        return
        
    translator = GoogleTranslator(source='en', target=lang)
    translated_missing = translate_values(missing, lang, translator)
    
    updated_data = merge_dicts(target_data, translated_missing)
    
    with open(file_path, 'w') as f:
        json.dump(updated_data, f, ensure_ascii=False, indent=4)
        
    print(f"[{lang}] Completed updating missing keys.")

def main():
    with open('frontend/src/locales/en.json', 'r') as f:
        en_data = json.load(f)
        
    langs = ['hi', 'bn', 'te', 'mr', 'ta', 'ur', 'gu', 'kn', 'ml', 'or', 'pa', 'as']
    
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = [executor.submit(process_lang, lang, en_data) for lang in langs]
        for f in futures:
            f.result()
            
    print("All translations complete!")

if __name__ == '__main__':
    main()
