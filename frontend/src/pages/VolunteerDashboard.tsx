import { useState, useEffect, useCallback } from 'react';
import {
    CheckCircle, Clock, Camera, MapPin,
    ChevronRight, ArrowLeft, Loader2, AlertTriangle, Tag, Wrench, RefreshCw
} from 'lucide-react';

const SEVERITY_STYLE: Record<string, string> = {
    HIGH:   'bg-red-600 text-white',
    NORMAL: 'bg-amber-100 text-amber-700',
    LOW:    'bg-gray-100 text-gray-500',
};

const CATEGORY_LABEL: Record<string, string> = {
    'water-sanitation':       'Water & Sanitation',
    'infrastructure':         'Infrastructure',
    'health-nutrition':       'Health & Nutrition',
    'agriculture-environment':'Agriculture & Environment',
    'education-digital':      'Education & Digital',
    'livelihood-governance':  'Livelihood & Governance',
    'others':                 'Others',
    // legacy labels (seed data)
    'education':              'Education',
    'health':                 'Health',
    'digital':                'Digital',
};
import { useAuth } from '../contexts/auth-shared';
import { useTranslation } from 'react-i18next';
import { api, type JugaadRepairResponse, type VolunteerTask } from '../services/api';
import { Navigate, useNavigate } from 'react-router-dom';
import { subscribeLiveRefresh } from '../lib/liveRefresh';

export default function VolunteerDashboard() {
    const { profile } = useAuth();
    const { t } = useTranslation();
    const navigate = useNavigate();
    const [tasks, setTasks] = useState<VolunteerTask[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedTask, setSelectedTask] = useState<VolunteerTask | null>(null);
    const [beforeImageFile, setBeforeImageFile] = useState<File | null>(null);
    const [afterImageFile, setAfterImageFile] = useState<File | null>(null);
    const [beforeImagePreview, setBeforeImagePreview] = useState<string | null>(null);
    const [afterImagePreview, setAfterImagePreview] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [showJugaadHelper, setShowJugaadHelper] = useState(false);
    const [jugaadBrokenFile, setJugaadBrokenFile] = useState<File | null>(null);
    const [jugaadMaterialsFile, setJugaadMaterialsFile] = useState<File | null>(null);
    const [jugaadBrokenPreview, setJugaadBrokenPreview] = useState<string | null>(null);
    const [jugaadMaterialsPreview, setJugaadMaterialsPreview] = useState<string | null>(null);
    const [jugaadLoading, setJugaadLoading] = useState(false);
    const [jugaadError, setJugaadError] = useState('');
    const [jugaadResult, setJugaadResult] = useState<JugaadRepairResponse | null>(null);
    const activeTasks = tasks.filter((task) => task.status !== 'completed');
    const completedTasks = tasks.filter((task) => task.status === 'completed');

    const revokeProofDraftUrls = () => {
        if (beforeImagePreview) {
            URL.revokeObjectURL(beforeImagePreview);
        }
        if (afterImagePreview) {
            URL.revokeObjectURL(afterImagePreview);
        }
    };

    const clearProofDraft = () => {
        revokeProofDraftUrls();
        setBeforeImageFile(null);
        setAfterImageFile(null);
        setBeforeImagePreview(null);
        setAfterImagePreview(null);
    };

    const revokeJugaadDraftUrls = () => {
        if (jugaadBrokenPreview) {
            URL.revokeObjectURL(jugaadBrokenPreview);
        }
        if (jugaadMaterialsPreview) {
            URL.revokeObjectURL(jugaadMaterialsPreview);
        }
    };

    const clearJugaadDraft = () => {
        revokeJugaadDraftUrls();
        setShowJugaadHelper(false);
        setJugaadBrokenFile(null);
        setJugaadMaterialsFile(null);
        setJugaadBrokenPreview(null);
        setJugaadMaterialsPreview(null);
        setJugaadLoading(false);
        setJugaadError('');
        setJugaadResult(null);
    };

    useEffect(() => {
        return () => {
            revokeProofDraftUrls();
            revokeJugaadDraftUrls();
        };
    }, [afterImagePreview, beforeImagePreview, jugaadBrokenPreview, jugaadMaterialsPreview]);

    const loadTasks = useCallback(async () => {
        if (!profile) return;
        setLoading(true);
        try {
            const data = await api.getVolunteerTasks(profile.id);
            setTasks(data);
        } catch (err) {
            console.error("Failed to load volunteer tasks:", err);
        } finally {
            setLoading(false);
        }
    }, [profile]);

    useEffect(() => {
        if (profile) {
            loadTasks();
        }
    }, [loadTasks, profile]);

    useEffect(() => {
        if (!profile) {
            return;
        }

        const unsubscribe = subscribeLiveRefresh(() => {
            loadTasks();
        });

        return () => {
            unsubscribe();
        };
    }, [loadTasks, profile]);

    useEffect(() => {
        if (!selectedTask) {
            return;
        }

        const latestTask = tasks.find((task) => task.id === selectedTask.id);
        if (!latestTask) {
            setSelectedTask(null);
            clearProofDraft();
            clearJugaadDraft();
            return;
        }

        if (latestTask !== selectedTask) {
            setSelectedTask(latestTask);
        }
    }, [selectedTask, tasks]);

    const handleRequestJugaadHelp = async () => {
        if (!selectedTask) {
            return;
        }
        if (!jugaadBrokenFile || !jugaadMaterialsFile) {
            alert('Please upload both the broken mechanism photo and the available materials photo.');
            return;
        }

        setJugaadLoading(true);
        setJugaadError('');
        try {
            const response = await api.requestJugaadHelp({
                broken_photo: jugaadBrokenFile,
                materials_photo: jugaadMaterialsFile,
                problem_title: selectedTask.title,
                problem_description: selectedTask.description,
                category: selectedTask.category,
                village_name: selectedTask.village,
                problem_id: selectedTask.id,
            });
            setJugaadResult(response.guidance);
        } catch (err) {
            setJugaadError(err instanceof Error ? err.message : 'Failed to generate a repair plan.');
        } finally {
            setJugaadLoading(false);
        }
    };

    const handleComplete = async () => {
        if (!afterImageFile) {
            alert("Please upload an 'After' photo as proof of work.");
            return;
        }
        if (!selectedTask) {
            return;
        }
        if (!profile) {
            alert('Your volunteer profile is required to complete a task.');
            return;
        }
        const taskId = selectedTask.id;
        setIsSubmitting(true);
        try {
            let beforeMediaId: string | undefined;
            let afterMediaId: string | undefined;

            if (beforeImageFile) {
                const beforeUpload = await api.uploadMedia(beforeImageFile, {
                    kind: 'proof_before',
                    problemId: taskId,
                    volunteerId: profile.id,
                    label: `${selectedTask.title} before`,
                });
                beforeMediaId = beforeUpload.media.id;
            }

            const afterUpload = await api.uploadMedia(afterImageFile, {
                kind: 'proof_after',
                problemId: taskId,
                volunteerId: profile.id,
                label: `${selectedTask.title} after`,
            });
            afterMediaId = afterUpload.media.id;

            await api.submitProof(taskId, {
                volunteer_id: profile.id,
                before_media_id: beforeMediaId,
                after_media_id: afterMediaId,
                notes: 'Volunteer submitted completion proof',
            });
            alert("Proof accepted. Gemini verified the visible fix.");
            setSelectedTask(null);
            clearProofDraft();
            loadTasks();
        } catch (err) {
            console.error("Task completion failed:", err);
            alert(err instanceof Error ? err.message : "Failed to verify impact. Please try again.");
        } finally {
            setIsSubmitting(false);
        }
    };

    if (!profile || profile.role !== 'volunteer') {
        return <Navigate to="/volunteer-login" replace />;
    }

    if (selectedTask) {
        return (
            <div className="min-h-screen bg-gray-50 py-12 px-4">
                <div className="max-w-2xl mx-auto">
                    <button
                        onClick={() => {
                            setSelectedTask(null);
                            clearProofDraft();
                            clearJugaadDraft();
                        }}
                        className="flex items-center gap-2 text-green-700 font-semibold mb-6"
                    >
                        <ArrowLeft size={20} /> {t('volunteer.back_to_tasks')}
                    </button>

                    <div className="bg-white rounded-2xl shadow-lg p-8">
                        <h2 className="text-2xl font-bold text-gray-900 mb-2">{t('seed.' + selectedTask.title, selectedTask.title)}</h2>
                        <p className="text-gray-600 mb-6">{t('seed.' + selectedTask.description, selectedTask.description)}</p>

                        <div className="flex items-center gap-2 text-sm text-gray-500 mb-8">
                            <MapPin size={16} className="text-green-600" />
                            <span>{t('seed.' + selectedTask.village, selectedTask.village)}, {t('seed.' + selectedTask.location, selectedTask.location)}</span>
                        </div>

                        {(selectedTask.media_assets?.length || selectedTask.proof_assets?.length) ? (
                            <div className="space-y-4 mb-8">
                                {selectedTask.media_assets?.length ? (
                                    <div>
                                        <h3 className="text-sm font-bold uppercase tracking-wide text-gray-500 mb-3">{t('volunteer.problem_media')}</h3>
                                        <div className="grid grid-cols-2 gap-3">
                                            {selectedTask.media_assets.map((asset) => (
                                                <div key={asset.id} className="rounded-xl border border-gray-200 p-3">
                                                    {asset.mime_type?.startsWith('image/') && asset.url ? (
                                                        <img src={asset.url} alt={asset.filename || asset.label || 'Uploaded media'} className="h-28 w-full rounded-lg object-cover mb-2" />
                                                    ) : (
                                                        <div className="h-28 w-full rounded-lg bg-gray-100 flex items-center justify-center text-xs text-gray-500 mb-2">
                                                            {asset.kind}
                                                        </div>
                                                    )}
                                                    <p className="text-xs font-medium text-gray-700 truncate">{asset.filename || asset.label || asset.kind}</p>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                ) : null}

                                {selectedTask.proof_assets?.length ? (
                                    <div>
                                        <h3 className="text-sm font-bold uppercase tracking-wide text-gray-500 mb-3">{t('volunteer.stored_proof')}</h3>
                                        <div className="grid grid-cols-2 gap-3">
                                            {selectedTask.proof_assets.map((asset) => (
                                                <div key={asset.id} className="rounded-xl border border-emerald-200 p-3 bg-emerald-50/40">
                                                    {asset.mime_type?.startsWith('image/') && asset.url ? (
                                                        <img src={asset.url} alt={asset.filename || asset.label || 'Proof media'} className="h-28 w-full rounded-lg object-cover mb-2" />
                                                    ) : (
                                                        <div className="h-28 w-full rounded-lg bg-emerald-100 flex items-center justify-center text-xs text-emerald-700 mb-2">
                                                            {asset.kind}
                                                        </div>
                                                    )}
                                                    <p className="text-xs font-medium text-gray-700 truncate">{asset.filename || asset.label || asset.kind}</p>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                ) : null}
                            </div>
                        ) : null}

                        <div className="mb-8 rounded-2xl border border-amber-200 bg-amber-50/70 p-5">
                            <div className="flex items-start justify-between gap-4">
                                <div>
                                    <div className="flex items-center gap-2 mb-2">
                                        <Wrench size={18} className="text-amber-700" />
                                        <h3 className="text-lg font-bold text-amber-900">Help Me Fix This</h3>
                                    </div>
                                    <p className="text-sm text-amber-900/80">
                                        Upload a photo of the broken mechanism and a photo of whatever materials you have on hand.
                                        The Jugaad Engine will suggest a safe, temporary field repair.
                                    </p>
                                </div>
                                <button
                                    type="button"
                                    onClick={() => setShowJugaadHelper((value) => !value)}
                                    className="rounded-lg bg-amber-600 px-3 py-2 text-sm font-semibold text-white hover:bg-amber-700"
                                >
                                    {showJugaadHelper ? 'Hide Helper' : 'Open Helper'}
                                </button>
                            </div>

                            {showJugaadHelper && (
                                <div className="mt-5 space-y-4">
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <p className="text-sm font-medium text-gray-700">Broken mechanism photo</p>
                                            <label className="aspect-square flex flex-col items-center justify-center border-2 border-dashed border-amber-300 rounded-xl cursor-pointer hover:bg-amber-50 bg-white object-cover overflow-hidden">
                                                {jugaadBrokenPreview ? (
                                                    <img src={jugaadBrokenPreview} className="w-full h-full object-cover" />
                                                ) : (
                                                    <>
                                                        <Camera size={32} className="text-amber-600 mb-2" />
                                                        <span className="text-xs text-amber-700 font-medium">Upload the broken part</span>
                                                    </>
                                                )}
                                                <input
                                                    data-testid="jugaad-broken-photo-input"
                                                    type="file"
                                                    className="hidden"
                                                    accept="image/*"
                                                    onChange={(e) => {
                                                        const file = e.target.files?.[0] ?? null;
                                                        if (jugaadBrokenPreview) {
                                                            URL.revokeObjectURL(jugaadBrokenPreview);
                                                        }
                                                        setJugaadBrokenFile(file);
                                                        setJugaadBrokenPreview(file ? URL.createObjectURL(file) : null);
                                                    }}
                                                />
                                            </label>
                                        </div>

                                        <div className="space-y-2">
                                            <p className="text-sm font-medium text-gray-700">Materials photo</p>
                                            <label className="aspect-square flex flex-col items-center justify-center border-2 border-dashed border-amber-300 rounded-xl cursor-pointer hover:bg-amber-50 bg-white object-cover overflow-hidden">
                                                {jugaadMaterialsPreview ? (
                                                    <img src={jugaadMaterialsPreview} className="w-full h-full object-cover" />
                                                ) : (
                                                    <>
                                                        <Camera size={32} className="text-amber-600 mb-2" />
                                                        <span className="text-xs text-amber-700 font-medium">Upload available materials</span>
                                                    </>
                                                )}
                                                <input
                                                    data-testid="jugaad-materials-photo-input"
                                                    type="file"
                                                    className="hidden"
                                                    accept="image/*"
                                                    onChange={(e) => {
                                                        const file = e.target.files?.[0] ?? null;
                                                        if (jugaadMaterialsPreview) {
                                                            URL.revokeObjectURL(jugaadMaterialsPreview);
                                                        }
                                                        setJugaadMaterialsFile(file);
                                                        setJugaadMaterialsPreview(file ? URL.createObjectURL(file) : null);
                                                    }}
                                                />
                                            </label>
                                        </div>
                                    </div>

                                    <button
                                        type="button"
                                        onClick={() => void handleRequestJugaadHelp()}
                                        disabled={jugaadLoading || !jugaadBrokenFile || !jugaadMaterialsFile}
                                        className="w-full bg-amber-600 text-white py-3 rounded-xl font-bold hover:bg-amber-700 transition disabled:bg-gray-400 flex items-center justify-center gap-3"
                                        data-testid="jugaad-help-button"
                                    >
                                        {jugaadLoading ? <RefreshCw className="animate-spin" size={18} /> : <Wrench size={18} />}
                                        {jugaadLoading ? 'Generating repair plan...' : 'Generate Jugaad Plan'}
                                    </button>

                                    {jugaadError && (
                                        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                                            {jugaadError}
                                        </div>
                                    )}

                                    {jugaadResult && (
                                        <div className="rounded-xl border border-amber-200 bg-white p-4">
                                            <div className="flex items-center justify-between gap-3 mb-3">
                                                <h4 className="font-bold text-gray-900">Temporary fix plan</h4>
                                                <span className="text-xs font-semibold uppercase tracking-wide text-amber-700 bg-amber-50 px-2 py-1 rounded-full">
                                                    {jugaadResult.source}
                                                </span>
                                            </div>
                                            <p className="text-sm text-gray-700 mb-4">{jugaadResult.situation_summary}</p>

                                            {jugaadResult.materials_identified.length > 0 && (
                                                <div className="mb-4">
                                                    <p className="text-xs font-bold uppercase tracking-wide text-gray-500 mb-2">Materials identified</p>
                                                    <div className="flex flex-wrap gap-2">
                                                        {jugaadResult.materials_identified.map((item) => (
                                                            <span key={item} className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-800">
                                                                {item}
                                                            </span>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}

                                            <div className="mb-4">
                                                <p className="text-xs font-bold uppercase tracking-wide text-gray-500 mb-2">Steps</p>
                                                <ol className="space-y-2 text-sm text-gray-700 list-decimal pl-5">
                                                    {jugaadResult.temporary_fix_steps.map((step) => (
                                                        <li key={step}>{step}</li>
                                                    ))}
                                                </ol>
                                            </div>

                                            <div className="mb-4">
                                                <p className="text-xs font-bold uppercase tracking-wide text-gray-500 mb-2">Safety warnings</p>
                                                <ul className="space-y-2 text-sm text-red-700 list-disc pl-5">
                                                    {jugaadResult.safety_warnings.map((warning) => (
                                                        <li key={warning}>{warning}</li>
                                                    ))}
                                                </ul>
                                            </div>

                                            <div className="grid gap-3 md:grid-cols-2 text-sm">
                                                <div className="rounded-lg bg-gray-50 p-3">
                                                    <p className="text-xs font-bold uppercase tracking-wide text-gray-500 mb-1">When to stop</p>
                                                    <p className="text-gray-700">{jugaadResult.when_to_stop}</p>
                                                </div>
                                                <div className="rounded-lg bg-gray-50 p-3">
                                                    <p className="text-xs font-bold uppercase tracking-wide text-gray-500 mb-1">Escalation</p>
                                                    <p className="text-gray-700">{jugaadResult.escalation}</p>
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>

                        <div className="space-y-8">
                            <h3 className="text-lg font-bold text-gray-800 border-b pb-2">{t('volunteer.verification_proof')}</h3>

                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <p className="text-sm font-medium text-gray-700">{t('volunteer.before_photo')}</p>
                                    <label className="aspect-square flex flex-col items-center justify-center border-2 border-dashed border-gray-300 rounded-xl cursor-pointer hover:bg-gray-50 bg-gray-50 object-cover overflow-hidden">
                                        {beforeImagePreview ? (
                                            <img src={beforeImagePreview} className="w-full h-full object-cover" />
                                        ) : (
                                            <>
                                                <Camera size={32} className="text-gray-400 mb-2" />
                                                <span className="text-xs text-gray-500">{t('volunteer.capture_upload')}</span>
                                            </>
                                        )}
                                        <input
                                            data-testid="before-photo-input"
                                            type="file"
                                            className="hidden"
                                            accept="image/*"
                                            onChange={(e) => {
                                                const file = e.target.files?.[0] ?? null;
                                                if (beforeImagePreview) {
                                                    URL.revokeObjectURL(beforeImagePreview);
                                                }
                                                setBeforeImageFile(file);
                                                setBeforeImagePreview(file ? URL.createObjectURL(file) : null);
                                            }}
                                        />
                                    </label>
                                </div>

                                <div className="space-y-2">
                                    <p className="text-sm font-medium text-gray-700">{t('volunteer.after_photo')}</p>
                                    <label className="aspect-square flex flex-col items-center justify-center border-2 border-dashed border-gray-300 rounded-xl cursor-pointer hover:bg-gray-50 bg-gray-50 object-cover overflow-hidden">
                                        {afterImagePreview ? (
                                            <img src={afterImagePreview} className="w-full h-full object-cover" />
                                        ) : (
                                            <>
                                                <Camera size={32} className="text-green-600 mb-2" />
                                                <span className="text-xs text-green-600 font-bold">{t('volunteer.verify_completion')}</span>
                                            </>
                                        )}
                                        <input
                                            data-testid="after-photo-input"
                                            type="file"
                                            className="hidden"
                                            accept="image/*"
                                            onChange={(e) => {
                                                const file = e.target.files?.[0] ?? null;
                                                if (afterImagePreview) {
                                                    URL.revokeObjectURL(afterImagePreview);
                                                }
                                                setAfterImageFile(file);
                                                setAfterImagePreview(file ? URL.createObjectURL(file) : null);
                                            }}
                                        />
                                    </label>
                                </div>
                            </div>

                            <button
                                onClick={handleComplete}
                                disabled={isSubmitting || !afterImageFile}
                                className="w-full bg-green-600 text-white py-4 rounded-xl font-bold text-lg hover:bg-green-700 transition disabled:bg-gray-400 flex items-center justify-center gap-3"
                            >
                                {isSubmitting ? <Loader2 className="animate-spin" /> : <CheckCircle />}
                                {isSubmitting ? t('volunteer.verifying') : t('volunteer.submit_proof')}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 py-12 px-4">
            <div className="max-w-4xl mx-auto">
                <div className="flex justify-between items-center mb-8">
                    <div>
                        <h1 className="text-3xl font-extrabold text-gray-900">{t('volunteer.dashboard_title')}</h1>
                        <p className="text-gray-600">{t('volunteer.dashboard_subtitle')}</p>
                    </div>
                    <div className="flex items-center gap-4">
                        <button onClick={() => navigate('/')} className="text-green-700 font-semibold">{t('common.home')}</button>
                        {profile && <span className="text-xs text-gray-400">ID: {profile.id.slice(0, 8)}</span>}
                    </div>
                </div>

                <div className="grid gap-6">
                    <h2 className="text-xl font-bold text-gray-800 flex items-center gap-2">
                        <Clock className="text-green-600" /> {t('volunteer.active_assignments')}
                    </h2>
                    {loading ? (
                        <div className="flex justify-center py-12">
                            <Loader2 className="animate-spin text-green-600" size={32} />
                        </div>
                    ) : activeTasks.length === 0 ? (
                        <div className="bg-white p-8 rounded-2xl shadow-sm border border-gray-100 text-center text-gray-500">
                            {t('volunteer.no_active_assignments')}
                        </div>
                    ) : (
                        activeTasks.map(task => (
                            <div
                                key={task.id}
                                data-testid={`task-card-${task.id}`}
                                className={`bg-white p-6 rounded-2xl shadow-sm border hover:shadow-md transition cursor-pointer flex justify-between items-center group ${task.severity === 'HIGH' ? 'border-red-200' : 'border-gray-100'}`}
                                onClick={() => setSelectedTask(task)}
                            >
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-1">
                                        {task.severity === 'HIGH' && <AlertTriangle size={14} className="text-red-500 shrink-0" />}
                                        <h3 className="text-xl font-bold text-gray-900 group-hover:text-green-600 transition truncate">{t('seed.' + task.title, task.title)}</h3>
                                    </div>
                                    <div className="flex items-center flex-wrap gap-2 text-sm text-gray-500">
                                        <span className="flex items-center gap-1"><MapPin size={14} /> {t('seed.' + task.village, task.village)}</span>
                                        <span className="bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider">{t(`common.${task.status}`, task.status)}</span>
                                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${SEVERITY_STYLE[task.severity] ?? SEVERITY_STYLE.NORMAL}`}>
                                            {t(`common.${(task.severity || 'normal').toLowerCase()}`, task.severity || 'NORMAL')}
                                        </span>
                                        {task.category && (
                                            <span className="flex items-center gap-1 text-[10px] font-medium text-gray-400">
                                                <Tag size={10} />{t(`common.${task.category}`, CATEGORY_LABEL[task.category] ?? task.category)}
                                            </span>
                                        )}
                                    </div>
                                </div>
                                <ChevronRight className="text-gray-300 group-hover:text-green-600 group-hover:translate-x-1 transition shrink-0 ml-4" />
                            </div>
                        ))

                    )}
                </div>

                {completedTasks.length > 0 && (
                    <div className="mt-10 grid gap-6">
                        <h2 className="text-xl font-bold text-gray-800 flex items-center gap-2">
                            <CheckCircle className="text-emerald-600" /> {t('volunteer.completed_assignments')}
                        </h2>
                        {completedTasks.map(task => (
                            <div
                                key={`completed-${task.id}`}
                                className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 flex justify-between items-center opacity-80"
                            >
                                <div className="flex-1 min-w-0">
                                    <h3 className="text-xl font-bold text-gray-900 mb-1 truncate">{t('seed.' + task.title, task.title)}</h3>
                                    <div className="flex items-center flex-wrap gap-2 text-sm text-gray-500">
                                        <span className="flex items-center gap-1"><MapPin size={14} /> {t('seed.' + task.village, task.village)}</span>
                                        <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider">{t(`common.${task.status}`, task.status)}</span>
                                        {task.category && (
                                            <span className="flex items-center gap-1 text-[10px] font-medium text-gray-400">
                                                <Tag size={10} />{t(`common.${task.category}`, CATEGORY_LABEL[task.category] ?? task.category)}
                                            </span>
                                        )}
                                    </div>
                                </div>
                                <CheckCircle className="text-emerald-500 shrink-0 ml-4" />
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
