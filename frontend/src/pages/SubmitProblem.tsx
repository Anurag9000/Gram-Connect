import { useState, useCallback, type ChangeEvent, type FormEvent } from 'react';
import {
  Droplets, HeartPulse, Building2, BookOpen, Sprout, Landmark, MoreHorizontal,
  CheckCircle, Upload, MapPin, Loader2, UserRound, Phone, Mail, AlertTriangle
} from 'lucide-react';
import { useAuth } from '../contexts/auth-shared';
import { useTranslation } from 'react-i18next';
import AudioRecorder from '../components/AudioRecorder';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { loadStoredProfile, saveStoredProfile, type ProfileRecord } from '../lib/profileStorage';

// Non-overlapping problem categories.
// Category is a routing/display label only. Actual multi-domain skill matching
// is driven by required_skills extracted from the problem description text.
const categories = [
  {
    id: 'water-sanitation',
    label: 'Water & Sanitation',
    icon: Droplets,
    color: 'bg-blue-100 text-blue-600',
    keywords: ['water', 'pump', 'handpump', 'drain', 'sanitation', 'toilet', 'latrine', 'contamination', 'borewell', 'pipe', 'sewage', 'wash'],
  },
  {
    id: 'infrastructure',
    label: 'Infrastructure',
    icon: Building2,
    color: 'bg-orange-100 text-orange-600',
    keywords: ['road', 'bridge', 'culvert', 'building', 'wall', 'house', 'electricity', 'solar', 'grid', 'wiring', 'path', 'construction'],
  },
  {
    id: 'health-nutrition',
    label: 'Health & Nutrition',
    icon: HeartPulse,
    color: 'bg-red-100 text-red-600',
    keywords: ['health', 'disease', 'fever', 'nutrition', 'anganwadi', 'vaccination', 'outbreak', 'medicine', 'hospital', 'malnutrition'],
  },
  {
    id: 'agriculture-environment',
    label: 'Agriculture & Environment',
    icon: Sprout,
    color: 'bg-green-100 text-green-600',
    keywords: ['agriculture', 'farm', 'crop', 'irrigation', 'drip', 'soil', 'harvest', 'forest', 'tree', 'erosion', 'plantation', 'livestock'],
  },
  {
    id: 'education-digital',
    label: 'Education & Digital',
    icon: BookOpen,
    color: 'bg-purple-100 text-purple-600',
    keywords: ['education', 'school', 'digital', 'literacy', 'computer', 'smartphone', 'internet', 'training', 'vocational', 'teacher'],
  },
  {
    id: 'livelihood-governance',
    label: 'Livelihood & Governance',
    icon: Landmark,
    color: 'bg-yellow-100 text-yellow-700',
    keywords: ['panchayat', 'mgnrega', 'shg', 'self help', 'women', 'microfinance', 'cooperative', 'gram sabha', 'beneficiary', 'survey', 'census'],
  },
  {
    id: 'others',
    label: 'Others',
    icon: MoreHorizontal,
    color: 'bg-gray-100 text-gray-600',
    keywords: [],
  },
];

const SEVERITY_OPTIONS = [
  { value: 'auto',   label: 'Auto-detect', description: 'Inferred from your description' },
  { value: 'LOW',    label: 'Low',         description: 'Routine, no immediate risk' },
  { value: 'NORMAL', label: 'Normal',      description: 'Needs attention within days' },
  { value: 'HIGH',   label: 'High',        description: 'Urgent / emergency' },
];

// Infer most likely category from free text by counting keyword hits.
function inferCategory(text: string): string | null {
  const t = text.toLowerCase();
  let best: string | null = null;
  let bestCount = 0;
  for (const cat of categories) {
    if (cat.id === 'others') continue;
    const count = cat.keywords.filter(kw => t.includes(kw)).length;
    if (count > bestCount) { bestCount = count; best = cat.id; }
  }
  return bestCount > 0 ? best : null;
}

// Mirrors backend estimate_severity keyword logic (nexus.py).
function inferSeverity(text: string): 'LOW' | 'NORMAL' | 'HIGH' {
  const t = text.toLowerCase();
  const highWords = ['urgent', 'emergency', 'critical', 'broken', 'no water', 'flooding', 'collapse', 'immediate', 'danger', 'severe', 'crisis'];
  const lowWords  = ['minor', 'low priority', 'routine', 'request', 'small'];
  if (highWords.some(w => t.includes(w))) return 'HIGH';
  if (lowWords.some(w => t.includes(w))) return 'LOW';
  return 'NORMAL';
}

export default function SubmitProblem() {
  const { t } = useTranslation();
  const { profile } = useAuth();
  const navigate = useNavigate();
  const storedProfile = loadStoredProfile();
  const reporterProfile: ProfileRecord | null = (profile?.role === 'coordinator' ? profile : storedProfile) ?? null;

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState<string>('');
  const [categoryAutoSet, setCategoryAutoSet] = useState(false);
  const [severityChoice, setSeverityChoice] = useState<'auto' | 'LOW' | 'NORMAL' | 'HIGH'>('auto');
  const [villageName, setVillageName] = useState(reporterProfile?.village_name ?? '');
  const [villageAddress, setVillageAddress] = useState('');
  const [reporterName, setReporterName] = useState(reporterProfile?.full_name ?? '');
  const [reporterPhone, setReporterPhone] = useState(reporterProfile?.phone ?? '');
  const [reporterEmail, setReporterEmail] = useState(reporterProfile?.email ?? '');
  const [loading, setLoading] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  const [selectedImageFile, setSelectedImageFile] = useState<File | null>(null);
  const [capturedAudioBlob, setCapturedAudioBlob] = useState<Blob | null>(null);
  const [capturedAudioLanguage, setCapturedAudioLanguage] = useState<string | null>(null);
  const [visualTags, setVisualTags] = useState<string[]>([]);
  const [isAnalyzingImage, setIsAnalyzingImage] = useState(false);

  const canSubmitAsCoordinator = profile?.role === 'coordinator';
  const needsReporterProfile = !canSubmitAsCoordinator;

  // Auto-infer category when user leaves the description field,
  // unless they have already manually selected a category.
  const handleDescriptionBlur = useCallback(() => {
    if (category && !categoryAutoSet) return;
    const inferred = inferCategory(`${title} ${description}`);
    if (inferred && inferred !== category) {
      setCategory(inferred);
      setCategoryAutoSet(true);
    }
  }, [title, description, category, categoryAutoSet]);


  const handleSaveReporterProfile = async (): Promise<ProfileRecord> => {
    if (!needsReporterProfile) {
      return reporterProfile as ProfileRecord;
    }
    if (!reporterName.trim()) {
      throw new Error('Please enter your name before continuing.');
    }
    if (!villageName.trim()) {
      throw new Error('Please enter your village name before continuing.');
    }

    setSavingProfile(true);
    setError('');
    try {
      const response = await api.upsertProfile({
        id: reporterProfile?.id,
        email: reporterEmail || undefined,
        full_name: reporterName,
        phone: reporterPhone || undefined,
        role: 'villager',
        village_name: villageName,
      });
      saveStoredProfile(response.profile);
      return response.profile;
    } finally {
      setSavingProfile(false);
    }
  };

  const handleFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      setSelectedImageFile(file);
      setFileName(file.name);

      setIsAnalyzingImage(true);
      setError('');
      try {
        const result = await api.analyzeImage(file);
        if (result.tags) {
          setVisualTags(result.tags);
          const primaryTag = result.tags[0]?.toLowerCase();
          if (primaryTag) {
            const matchedCat = categories.find((c) => c.id.includes(primaryTag) || primaryTag.includes(c.id));
            if (matchedCat) {
              setCategory(matchedCat.id);
            }
          }
        }
      } catch (err) {
        console.error('Image analysis failed:', err);
      } finally {
        setIsAnalyzingImage(false);
      }
    } else {
      setSelectedImageFile(null);
      setFileName(null);
      setVisualTags([]);
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    let problemId: string | null = null;

    try {
      if (!description) {
        throw new Error('Please enter a problem description.');
      }
      if (!category) {
        throw new Error('Please select a category.');
      }
      if (!villageAddress) {
        throw new Error('Please enter the village address/specific location for the problem.');
      }

      let villagerProfile: ProfileRecord | null = reporterProfile;
      if (needsReporterProfile) {
        villagerProfile = await handleSaveReporterProfile();
      }

      const resolvedSeverity: 'LOW' | 'NORMAL' | 'HIGH' = severityChoice === 'auto'
        ? inferSeverity(`${title} ${description}`)
        : severityChoice;

      const submission = await api.submitProblem({
        coordinator_id: canSubmitAsCoordinator ? profile?.id : undefined,
        villager_id: canSubmitAsCoordinator ? undefined : villagerProfile?.id,
        reporter_name: canSubmitAsCoordinator ? undefined : reporterName,
        reporter_phone: canSubmitAsCoordinator ? undefined : reporterPhone,
        title,
        description,
        category,
        severity: resolvedSeverity,
        village_name: villageName,
        village_address: villageAddress,
        visual_tags: visualTags,
        has_audio: Boolean(capturedAudioBlob) || description.includes('[Transcribed Audio]'),
        transcript: description,
        transcript_language: capturedAudioLanguage ?? undefined,
      });

      problemId = submission.id;

      const uploads: Promise<unknown>[] = [];
      if (selectedImageFile && problemId) {
        uploads.push(
          api.uploadMedia(selectedImageFile, {
            kind: 'problem_photo',
            problemId,
            label: title,
          }),
        );
      }
      if (capturedAudioBlob && problemId) {
        uploads.push(
          api.uploadMedia(capturedAudioBlob, {
            kind: 'problem_audio',
            problemId,
            label: title,
            filename: 'problem-audio.wav',
          }),
        );
      }
      if (uploads.length > 0) {
        await Promise.all(uploads);
      }

      setSuccess(true);
      setTitle('');
      setDescription('');
      setCategory('');
      setVillageName(needsReporterProfile ? villageName : '');
      setVillageAddress('');
      setReporterName(needsReporterProfile ? reporterName : '');
      setReporterPhone(needsReporterProfile ? reporterPhone : '');
      setReporterEmail(needsReporterProfile ? reporterEmail : '');
      setFileName(null);
      setSelectedImageFile(null);
      setCapturedAudioBlob(null);
      setCapturedAudioLanguage(null);
      setVisualTags([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit problem');
    } finally {
      setLoading(false);
    }
  };

  const handleAudioCaptured = (blob: Blob) => {
    setCapturedAudioBlob(blob);
  };

  const handleAudioTranscription = ({ text, language }: { text: string; language?: string | null }) => {
    setDescription((prev) => (prev ? `${prev}\n${text}` : text));
    setCapturedAudioLanguage(language ?? null);
  };

  if (success) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <div className="bg-white rounded-xl shadow-lg p-8 max-w-md w-full text-center">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <CheckCircle className="text-green-600" size={32} />
          </div>
          <h2 className="text-2xl font-bold text-green-700 mb-4">{t('submit.success_title')}</h2>
          <p className="text-gray-600 mb-6">
            {t('submit.success_desc')}
          </p>
          <div className="space-y-3">
            <button
              onClick={() => setSuccess(false)}
              className="w-full bg-green-600 text-white px-6 py-2 rounded-lg font-semibold hover:bg-green-700 transition"
            >
              {t('submit.submit_another')}
            </button>
            <button
              onClick={() => navigate('/map')}
              className="w-full border border-green-600 text-green-600 px-6 py-2 rounded-lg font-semibold hover:bg-green-50 transition"
            >
              {t('submit.view_on_map')}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-3xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <button onClick={() => navigate('/')} className="text-green-700 font-semibold">&larr; {t('common.home')}</button>
        </div>
        <div className="bg-white rounded-xl shadow-lg p-8">
          <h1 className="text-3xl font-bold text-green-700 mb-2">{t('submit.submit_heading')}</h1>
          <p className="text-gray-600 mb-8">
            {canSubmitAsCoordinator
              ? `${profile?.full_name}, ${t('submit.coordinator_intro')}`
              : t('submit.villager_intro')}
          </p>

          {needsReporterProfile && (
            <div className="mb-8 rounded-2xl border border-emerald-100 bg-emerald-50/70 p-5">
              <div className="flex items-center gap-2 mb-4">
                <UserRound size={18} className="text-emerald-700" />
                <h2 className="text-lg font-bold text-emerald-900">{t('submit.villager_onboarding')}</h2>
              </div>
              <div className="grid md:grid-cols-2 gap-4">
                <label className="block">
                  <span className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
                    <UserRound size={14} className="text-emerald-700" />
                    {t('submit.full_name')}
                  </span>
                  <input
                    value={reporterName}
                    onChange={(event) => setReporterName(event.target.value)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:border-green-500 focus:outline-none"
                    placeholder={t('submit.reporter_name_placeholder')}
                  />
                </label>
                <label className="block">
                  <span className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
                    <Phone size={14} className="text-emerald-700" />
                    {t('submit.phone')}
                  </span>
                  <input
                    value={reporterPhone}
                    onChange={(event) => setReporterPhone(event.target.value)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:border-green-500 focus:outline-none"
                    placeholder={t('submit.optional')}
                  />
                </label>
                <label className="block">
                  <span className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
                    <Mail size={14} className="text-emerald-700" />
                    {t('submit.email')}
                  </span>
                  <input
                    type="email"
                    value={reporterEmail}
                    onChange={(event) => setReporterEmail(event.target.value)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:border-green-500 focus:outline-none"
                    placeholder={t('submit.optional')}
                  />
                </label>
                <label className="block">
                  <span className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
                    <MapPin size={14} className="text-emerald-700" />
                    {t('submit.village_label')}
                  </span>
                  <input
                    value={villageName}
                    onChange={(event) => setVillageName(event.target.value)}
                    required
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:border-green-500 focus:outline-none"
                    placeholder={t('submit.village_placeholder')}
                  />
                </label>
              </div>
              <div className="mt-4 text-sm text-gray-600">
                {t('submit.profile_save_note')}
              </div>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {t('submit.village_name')} <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                required
                data-testid="village-name-input"
                value={villageName}
                onChange={(e) => setVillageName(e.target.value)}
                placeholder={t('submit.village_name')}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                <div className="flex items-center gap-1">
                  <MapPin size={16} className="text-green-600" /> {t('submit.village_address')} <span className="text-red-500">*</span>
                </div>
              </label>
              <input
                type="text"
                required
                data-testid="village-address-input"
                value={villageAddress}
                onChange={(e) => setVillageAddress(e.target.value)}
                placeholder={t('submit.address_placeholder')}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {t('submit.problem_title')} <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                required
                data-testid="problem-title-input"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder={t('submit.problem_title')}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-3">
                {t('submit.category')} <span className="text-red-500">*</span>
                {categoryAutoSet && <span className="ml-2 text-xs text-green-600 font-normal">{t('submit.category_auto')}</span>}
              </label>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {categories.map((cat) => (
                  <button
                    key={cat.id}
                    type="button"
                    onClick={() => { setCategory(cat.id); setCategoryAutoSet(false); }}
                    className={`p-4 rounded-lg border-2 transition ${category === cat.id
                      ? 'border-green-600 bg-green-50'
                      : 'border-gray-200 hover:border-green-300'
                      }`}
                  >
                    <div className={`w-10 h-10 ${cat.color} rounded-full flex items-center justify-center mx-auto mb-2`}>
                      <cat.icon size={20} />
                    </div>
                    <p className="text-xs font-medium text-gray-700 text-center leading-tight">
                      {t(`common.${cat.id}`, cat.label)}
                    </p>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-3">
                {t('submit.urgency_level')}
              </label>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {SEVERITY_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setSeverityChoice(opt.value as typeof severityChoice)}
                    className={`p-3 rounded-lg border-2 text-left transition ${
                      severityChoice === opt.value
                        ? opt.value === 'HIGH' ? 'border-red-500 bg-red-50'
                          : opt.value === 'LOW' ? 'border-gray-400 bg-gray-50'
                          : 'border-green-600 bg-green-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    {opt.value === 'HIGH' && <AlertTriangle size={14} className="text-red-500 mb-1" />}
                    <p className="text-sm font-semibold text-gray-800">{t(`submit.severity.${opt.value.toLowerCase()}_label`, opt.label)}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{t(`submit.severity.${opt.value.toLowerCase()}_desc`, opt.description)}</p>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="block text-sm font-medium text-gray-700">
                  {t('submit.description')} <span className="text-red-500">*</span>
                </label>
              </div>

              <div className="mb-4">
                <AudioRecorder
                  onTranscription={handleAudioTranscription}
                  onCapturedAudio={handleAudioCaptured}
                />
              </div>

              <textarea
                required
                data-testid="problem-description-input"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                onBlur={handleDescriptionBlur}
                placeholder={t('submit.description')}
                rows={6}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 resize-none"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {t('submit.upload_photo')}
              </label>
              <label className="w-full flex items-center justify-center px-4 py-3 border-2 border-gray-300 border-dashed rounded-lg cursor-pointer hover:border-green-500 hover:bg-green-50 transition">
                <Upload size={20} className="text-gray-500 mr-2" />
                <span className="text-sm text-gray-600">
                  {fileName || t('submit.upload_photo')}
                </span>
                <input
                  type="file"
                  className="hidden"
                  accept="image/*"
                  data-testid="problem-image-input"
                  onChange={handleFileChange}
                />
              </label>
              {isAnalyzingImage && (
                <div className="mt-2 flex items-center gap-2 text-blue-600 text-sm italic">
                  <Loader2 size={16} className="animate-spin" />
                  <span>{t('submit.ai_analyzing')}</span>
                </div>
              )}
              {visualTags.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2" data-testid="image-analysis-tags">
                  <span className="text-xs font-semibold text-gray-500">{t('submit.ai_detected')}</span>
                  {visualTags.map(tag => (
                    <span key={tag} className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded text-xs font-medium">#{t('seed.' + tag, tag)}</span>
                  ))}
                </div>
              )}
            </div>

            <button
              type="submit"
              disabled={loading || savingProfile || !category || !description}
              className="w-full bg-green-600 text-white py-3 rounded-lg font-semibold text-lg hover:bg-green-700 transition disabled:bg-gray-400"
            >
              {loading ? t('submit.submitting') : t('submit.submit_button')}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
