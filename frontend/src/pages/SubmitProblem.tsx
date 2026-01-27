import React, { useState } from 'react';
import {
  GraduationCap, Heart, Building, Laptop, MoreHorizontal,
  CheckCircle, Upload, MapPin, Loader2
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useTranslation } from 'react-i18next';
import AudioRecorder from '../components/AudioRecorder';
import LanguageToggle from '../components/LanguageToggle';

interface SubmitProblemProps {
  onNavigate: (page: string) => void;
}

const categories = [
  { id: 'education', label: 'Education', icon: GraduationCap, color: 'bg-blue-100 text-blue-600' },
  { id: 'health', label: 'Health', icon: Heart, color: 'bg-red-100 text-red-600' },
  { id: 'infrastructure', label: 'Infrastructure', icon: Building, color: 'bg-orange-100 text-orange-600' },
  { id: 'digital', label: 'Digital Help', icon: Laptop, color: 'bg-green-100 text-green-600' },
  { id: 'others', label: 'Others', icon: MoreHorizontal, color: 'bg-gray-100 text-gray-600' },
];

export default function SubmitProblem({ onNavigate }: SubmitProblemProps) {
  const { t } = useTranslation();
  const { profile } = useAuth();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState<string>('');
  const [villageName, setVillageName] = useState('');
  const [villageAddress, setVillageAddress] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  const [visualTags, setVisualTags] = useState<string[]>([]);
  const [isAnalyzingImage, setIsAnalyzingImage] = useState(false);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      setFileName(file.name);

      // Simulate Visual Analysis (CLIP)
      setIsAnalyzingImage(true);
      await new Promise(res => setTimeout(res, 1500));
      setVisualTags(["Infrastructure", "Water Issue"]);
      setCategory("infrastructure");
      setIsAnalyzingImage(false);
    } else {
      setFileName(null);
      setVisualTags([]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (!profile || profile.role !== 'coordinator') {
        throw new Error('You must be a coordinator to submit a problem.');
      }
      if (!description) {
        throw new Error('Please enter a problem description.');
      }
      if (!category) {
        throw new Error('Please select a category.');
      }
      if (!villageAddress) {
        throw new Error('Please enter the village address/specific location for the problem.');
      }

      const submitterId = profile.id;

      console.log('Mock Problem Submission:', {
        coordinator_id: submitterId,
        title,
        description,
        category,
        village_name: villageName,
        village_address: villageAddress,
        fileName,
        visual_tags: visualTags,
        transcription_fused: !!description.includes("[Transcribed Audio]")
      });

      await new Promise(res => setTimeout(res, 1000));
      setSuccess(true);
      setTitle('');
      setDescription('');
      setCategory('');
      setVillageName('');
      setVillageAddress('');
      setFileName(null);
      setVisualTags([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit problem');
    } finally {
      setLoading(false);
    }
  };

  if (!profile || profile.role !== 'coordinator') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <div className="bg-white rounded-xl shadow-lg p-8 max-w-md w-full text-center">
          <h2 className="text-2xl font-bold text-red-600 mb-4">Access Denied</h2>
          <p className="text-gray-600 mb-6">
            You must be logged in as a Coordinator to submit a new problem.
          </p>
          <button
            onClick={() => onNavigate('home')}
            className="w-full bg-green-600 text-white px-6 py-2 rounded-lg font-semibold hover:bg-green-700 transition"
          >
            Back to Home
          </button>
        </div>
      </div>
    );
  }

  if (success) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <div className="bg-white rounded-xl shadow-lg p-8 max-w-md w-full text-center">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <CheckCircle className="text-green-600" size={32} />
          </div>
          <h2 className="text-2xl font-bold text-green-700 mb-4">Submitted Successfully!</h2>
          <p className="text-gray-600 mb-6">
            Your problem has been submitted and is now available on the dashboard.
          </p>
          <div className="space-y-3">
            <button
              onClick={() => setSuccess(false)}
              className="w-full bg-green-600 text-white px-6 py-2 rounded-lg font-semibold hover:bg-green-700 transition"
            >
              Submit Another Problem
            </button>
            <button
              onClick={() => onNavigate('dashboard')}
              className="w-full border border-green-600 text-green-600 px-6 py-2 rounded-lg font-semibold hover:bg-green-50 transition"
            >
              Go to Dashboard
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
          <button onClick={() => onNavigate('home')} className="text-green-700 font-semibold">&larr; {t('common.home')}</button>
          <LanguageToggle />
        </div>
        <div className="bg-white rounded-xl shadow-lg p-8">
          <h1 className="text-3xl font-bold text-green-700 mb-2">{t('submit.submit_heading')}</h1>
          <p className="text-gray-600 mb-8">
            {profile?.full_name}, help us understand the problem. You can type, speak, or upload photos.
          </p>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Village Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                required
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
                value={villageAddress}
                onChange={(e) => setVillageAddress(e.target.value)}
                placeholder="E.g., 45, Gandhi Road"
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
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder={t('submit.problem_title')}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-3">
                Category <span className="text-red-500">*</span>
              </label>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                {categories.map((cat) => (
                  <button
                    key={cat.id}
                    type="button"
                    onClick={() => setCategory(cat.id)}
                    className={`p-4 rounded-lg border-2 transition ${category === cat.id
                        ? 'border-green-600 bg-green-50'
                        : 'border-gray-200 hover:border-green-300'
                      }`}
                  >
                    <div className={`w-12 h-12 ${cat.color} rounded-full flex items-center justify-center mx-auto mb-2`}>
                      <cat.icon size={24} />
                    </div>
                    <p className="text-sm font-medium text-gray-700 text-center">
                      {cat.label}
                    </p>
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
                <AudioRecorder onTranscription={(text) => setDescription(prev => prev + "\n" + `[Transcribed Audio]: ${text}`)} />
              </div>

              <textarea
                required
                value={description}
                onChange={(e) => setDescription(e.target.value)}
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
                  onChange={handleFileChange}
                />
              </label>
              {isAnalyzingImage && (
                <div className="mt-2 flex items-center gap-2 text-blue-600 text-sm italic">
                  <Loader2 size={16} className="animate-spin" />
                  <span>AI is analyzing image contents...</span>
                </div>
              )}
              {visualTags.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2">
                  <span className="text-xs font-semibold text-gray-500">AI Detected:</span>
                  {visualTags.map(tag => (
                    <span key={tag} className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded text-xs font-medium">#{tag}</span>
                  ))}
                </div>
              )}
            </div>

            <button
              type="submit"
              disabled={loading || !category}
              className="w-full bg-green-600 text-white py-3 rounded-lg font-semibold text-lg hover:bg-green-700 transition disabled:bg-gray-400"
            >
              {loading ? 'Submitting...' : 'Submit Problem'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}