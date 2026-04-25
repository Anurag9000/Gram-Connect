import React from 'react';
import { useTranslation } from 'react-i18next';
import { Languages } from 'lucide-react';

const LanguageToggle: React.FC = () => {
    const { i18n, t } = useTranslation();

    const toggleLanguage = () => {
        const nextLng = i18n.language === 'en' ? 'hi' : 'en';
        i18n.changeLanguage(nextLng);
    };

    return (
        <button
            onClick={toggleLanguage}
            className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-300 rounded-lg shadow-sm hover:bg-gray-50 transition text-sm font-medium text-gray-700"
            title={t('common.language')}
        >
            <Languages size={18} className="text-green-600" />
            <span>{i18n.language === 'en' ? 'हिन्दी' : 'English'}</span>
        </button>
    );
};

export default LanguageToggle;
