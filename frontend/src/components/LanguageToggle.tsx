import React from 'react';
import { useTranslation } from 'react-i18next';
import { Languages } from 'lucide-react';

const LanguageToggle: React.FC = () => {
    const { i18n } = useTranslation();

    const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        i18n.changeLanguage(e.target.value);
    };

    const languages = [
        { code: 'en', name: 'English' },
        { code: 'hi', name: 'हिन्दी' },
        { code: 'bn', name: 'বাংলা' },
        { code: 'te', name: 'తెలుగు' },
        { code: 'mr', name: 'मराठी' },
        { code: 'ta', name: 'தமிழ்' },
        { code: 'ur', name: 'اردو' },
        { code: 'gu', name: 'ગુજરાતી' },
        { code: 'kn', name: 'ಕನ್ನಡ' },
        { code: 'ml', name: 'മലയാളം' },
        { code: 'or', name: 'ଓଡ଼ିଆ' },
        { code: 'pa', name: 'ਪੰਜਾਬੀ' },
        { code: 'as', name: 'অসমীয়া' }
    ];

    return (
        <div className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-300 rounded-lg shadow-sm hover:bg-gray-50 transition">
            <Languages size={18} className="text-green-600" />
            <select
                value={i18n.language}
                onChange={handleChange}
                className="bg-transparent border-none text-sm font-medium text-gray-700 focus:outline-none cursor-pointer"
                title="Select Language"
            >
                {languages.map((lng) => (
                    <option key={lng.code} value={lng.code}>
                        {lng.name}
                    </option>
                ))}
            </select>
        </div>
    );
};

export default LanguageToggle;
