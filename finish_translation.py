import json
import os
import time
from deep_translator import GoogleTranslator

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
                time.sleep(0.5)
                result = translator.translate(v)
                translated[k] = result
                print(f"[{lang_code}] Translated '{v[:15]}...'")
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

def main():
    with open('frontend/src/locales/en.json', 'r') as f:
        en_data = json.load(f)
        
    langs = ['hi', 'bn', 'te', 'mr', 'ta', 'ur', 'gu', 'kn', 'ml', 'or', 'pa', 'as']
    
    for lang in langs:
        file_path = f'frontend/src/locales/{lang}.json'
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                target_data = json.load(f)
        else:
            target_data = {}
            
        missing = get_missing_keys(en_data, target_data)
        if not missing:
            print(f"[{lang}] up to date.")
            continue
            
        print(f"[{lang}] Translating {len(str(missing))} chars of missing data...")
        translator = GoogleTranslator(source='en', target=lang)
        translated_missing = translate_values(missing, lang, translator)
        updated_data = merge_dicts(target_data, translated_missing)
        
        with open(file_path, 'w') as f:
            json.dump(updated_data, f, ensure_ascii=False, indent=4)
        print(f"[{lang}] Saved.")

main()
