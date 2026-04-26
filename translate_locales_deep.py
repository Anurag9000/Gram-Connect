import json
from deep_translator import GoogleTranslator
import time

def translate_dict(d, lang_code, translator):
    translated = {}
    for k, v in d.items():
        if isinstance(v, dict):
            translated[k] = translate_dict(v, lang_code, translator)
        else:
            try:
                # Handle empty strings and formatting
                if not v.strip():
                    translated[k] = v
                    continue
                    
                # Small delay to avoid rate limiting
                time.sleep(0.1)
                
                # Google translator uses target language code
                # Some codes might need mapping
                mapped_code = lang_code
                if lang_code == 'or': mapped_code = 'or' # odia
                
                result = translator.translate(v)
                translated[k] = result
                print(f"[{lang_code}] {k} -> {result}")
            except Exception as e:
                print(f"Error translating {v} to {lang_code}: {e}")
                translated[k] = v # fallback to english
    return translated

def main():
    with open('frontend/src/locales/en.json', 'r') as f:
        en_data = json.load(f)
        
    langs = ['hi', 'bn', 'te', 'mr', 'ta', 'ur', 'gu', 'kn', 'ml', 'or', 'pa', 'as']
    
    for lang in langs:
        print(f"--- Translating to {lang} ---")
        translator = GoogleTranslator(source='en', target=lang)
        translated_data = translate_dict(en_data, lang, translator)
        
        with open(f'frontend/src/locales/{lang}.json', 'w') as f:
            json.dump(translated_data, f, ensure_ascii=False, indent=4)
            
if __name__ == '__main__':
    main()
