import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import enTranslation from './locales/en.json';
import hiTranslation from './locales/hi.json';
import bnTranslation from './locales/bn.json';
import teTranslation from './locales/te.json';
import mrTranslation from './locales/mr.json';
import taTranslation from './locales/ta.json';
import urTranslation from './locales/ur.json';
import guTranslation from './locales/gu.json';
import knTranslation from './locales/kn.json';
import mlTranslation from './locales/ml.json';
import orTranslation from './locales/or.json';
import paTranslation from './locales/pa.json';
import asTranslation from './locales/as.json';

i18n
    .use(initReactI18next)
    .init({
        resources: {
            en: { translation: enTranslation },
            hi: { translation: hiTranslation },
            bn: { translation: bnTranslation },
            te: { translation: teTranslation },
            mr: { translation: mrTranslation },
            ta: { translation: taTranslation },
            ur: { translation: urTranslation },
            gu: { translation: guTranslation },
            kn: { translation: knTranslation },
            ml: { translation: mlTranslation },
            or: { translation: orTranslation },
            pa: { translation: paTranslation },
            as: { translation: asTranslation }
        },
        lng: 'en',
        fallbackLng: 'en',
        interpolation: {
            escapeValue: false
        }
    });

export default i18n;
