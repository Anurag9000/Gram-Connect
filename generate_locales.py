import json
import os

with open('frontend/src/locales/en.json', 'r') as f:
    en_data = json.load(f)

translations = {
    'hi': {'title': 'ग्राम कनेक्ट', 'hero_title': 'स्वयंसेवकों को गाँव की जरूरतों से जोड़ना', 'smart_matching': 'स्मार्ट मिलान'},
    'bn': {'title': 'গ্রাম কানেক্ট', 'hero_title': 'স্বেচ্ছাসেবকদের গ্রামের প্রয়োজনের সাথে সংযুক্ত করা', 'smart_matching': 'স্মার্ট ম্যাচিং'},
    'te': {'title': 'గ్రామ్ కనెక్ట్', 'hero_title': 'గ్రామ అవసరాలకు వాలంటీర్లను కలుపుతోంది', 'smart_matching': 'స్మార్ట్ మ్యాచింగ్'},
    'mr': {'title': 'ग्राम कनेक्ट', 'hero_title': 'स्वयंसेवकांना गावाच्या गरजांशी जोडणे', 'smart_matching': 'स्मार्ट मॅचिंग'},
    'ta': {'title': 'கிராம் கனெக்ட்', 'hero_title': 'கிராம தேவைகளுக்கு தன்னார்வலர்களை இணைத்தல்', 'smart_matching': 'ஸ்மார்ட் மேட்சிங்'},
    'ur': {'title': 'گرام کنیکٹ', 'hero_title': 'رضاکاروں کو گاؤں کی ضروریات سے جوڑنا', 'smart_matching': 'سمارٹ میچنگ'},
    'gu': {'title': 'ગ્રામ કનેક્ટ', 'hero_title': 'સ્વયંસેવકોને ગામની જરૂરિયાતો સાથે જોડવા', 'smart_matching': 'સ્માર્ટ મેચિંગ'},
    'kn': {'title': 'ಗ್ರಾಮ್ ಕನೆಕ್ಟ್', 'hero_title': 'ಸ್ವಯಂಸೇವಕರನ್ನು ಗ್ರಾಮದ ಅಗತ್ಯಗಳಿಗೆ ಸಂಪರ್ಕಿಸುವುದು', 'smart_matching': 'ಸ್ಮಾರ್ಟ್ ಮ್ಯಾಚಿಂಗ್'},
    'ml': {'title': 'ഗ്രാം കണക്റ്റ്', 'hero_title': 'ഗ്രാമ ആവശ്യങ്ങളിലേക്ക് വോളന്റിയർമാരെ ബന്ധിപ്പിക്കുന്നു', 'smart_matching': 'സ്മാർട്ട് മാച്ചിംഗ്'},
    'or': {'title': 'ଗ୍ରାମ କନେକ୍ଟ', 'hero_title': 'ଗ୍ରାମର ଆବଶ୍ୟକତା ସହିତ ସ୍ଵେଚ୍ଛାସେବୀମାନଙ୍କୁ ଯୋଡିବା', 'smart_matching': 'ସ୍ମାର୍ଟ ମ୍ୟାଚିଂ'},
    'pa': {'title': 'ਗ੍ਰਾਮ ਕਨੈਕਟ', 'hero_title': 'ਵਲੰਟੀਅਰਾਂ ਨੂੰ ਪਿੰਡ ਦੀਆਂ ਲੋੜਾਂ ਨਾਲ ਜੋੜਨਾ', 'smart_matching': 'ਸਮਾਰਟ ਮੈਚਿੰਗ'},
    'as': {'title': 'গ্ৰাম কানেক্ট', 'hero_title': 'স্বেচ্ছাসেৱকসকলক গাঁৱৰ প্ৰয়োজনৰ সৈতে সংযোগ কৰা', 'smart_matching': 'স্মাৰ্ট মেচিং'}
}

for code, trans in translations.items():
    data = json.loads(json.dumps(en_data))
    data['common']['title'] = trans['title']
    data['home']['hero_title'] = trans['hero_title']
    # Adding Smart matching for the feature card if missing
    data['home']['dashboard_title'] = trans['title'] + " " + "Dashboard"
    
    with open(f'frontend/src/locales/{code}.json', 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

