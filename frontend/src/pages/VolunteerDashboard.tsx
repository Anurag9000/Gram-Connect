import { useState, useEffect, useCallback } from 'react';
import {
    CheckCircle, Clock, Camera, MapPin, Sparkles, Wrench,
    ChevronRight, ArrowLeft, Loader2, AlertTriangle, Tag
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

const OFFLINE_QUEUE_KEY = 'gram-connect-volunteer-offline-drafts';

type OfflineProofDraft = {
    id: string;
    kind: 'proof';
    problemId: string;
    taskTitle: string;
    volunteerId: string;
    createdAt: string;
    beforeImage?: string | null;
    afterImage: string;
    notes?: string;
};

type OfflineJugaadDraft = {
    id: string;
    kind: 'jugaad';
    problemId: string;
    taskTitle: string;
    volunteerId: string;
    createdAt: string;
    brokenImage: string;
    materialsImage: string;
    materialsNote?: string;
};

type OfflineDraft = OfflineProofDraft | OfflineJugaadDraft;

async function blobToDataUrl(blob: Blob): Promise<string> {
    return await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onerror = () => reject(new Error('Failed to read file for offline storage.'));
        reader.onload = () => resolve(String(reader.result || ''));
        reader.readAsDataURL(blob);
    });
}

async function dataUrlToBlob(dataUrl: string): Promise<Blob> {
    const response = await fetch(dataUrl);
    return await response.blob();
}

function loadOfflineDrafts(): OfflineDraft[] {
    try {
        const raw = localStorage.getItem(OFFLINE_QUEUE_KEY);
        if (!raw) {
            return [];
        }
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed as OfflineDraft[] : [];
    } catch {
        return [];
    }
}

function saveOfflineDrafts(drafts: OfflineDraft[]) {
    try {
        localStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(drafts));
    } catch {
        // Ignore storage quota / privacy-mode failures.
    }
}
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
    const [selectedTaskTab, setSelectedTaskTab] = useState<'details' | 'repair'>('details');
    const [beforeImageFile, setBeforeImageFile] = useState<File | null>(null);
    const [afterImageFile, setAfterImageFile] = useState<File | null>(null);
    const [beforeImagePreview, setBeforeImagePreview] = useState<string | null>(null);
    const [afterImagePreview, setAfterImagePreview] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [jugaadBrokenFile, setJugaadBrokenFile] = useState<File | null>(null);
    const [jugaadMaterialsFile, setJugaadMaterialsFile] = useState<File | null>(null);
    const [jugaadBrokenPreview, setJugaadBrokenPreview] = useState<string | null>(null);
    const [jugaadMaterialsPreview, setJugaadMaterialsPreview] = useState<string | null>(null);
    const [jugaadMaterialsNote, setJugaadMaterialsNote] = useState('');
    const [jugaadLoading, setJugaadLoading] = useState(false);
    const [jugaadResult, setJugaadResult] = useState<JugaadRepairResponse | null>(null);
    const [jugaadError, setJugaadError] = useState<string | null>(null);
    const [offlineDrafts, setOfflineDrafts] = useState<OfflineDraft[]>(() => loadOfflineDrafts());
    const [syncingDrafts, setSyncingDrafts] = useState(false);
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

    const revokeJugaadUrls = () => {
        if (jugaadBrokenPreview) {
            URL.revokeObjectURL(jugaadBrokenPreview);
        }
        if (jugaadMaterialsPreview) {
            URL.revokeObjectURL(jugaadMaterialsPreview);
        }
    };

    const clearJugaadDraft = () => {
        revokeJugaadUrls();
        setJugaadBrokenFile(null);
        setJugaadMaterialsFile(null);
        setJugaadBrokenPreview(null);
        setJugaadMaterialsPreview(null);
        setJugaadMaterialsNote('');
    };

    useEffect(() => {
        return () => {
            revokeProofDraftUrls();
        };
    }, [afterImagePreview, beforeImagePreview]);

    useEffect(() => {
        return () => {
            revokeJugaadUrls();
        };
    }, [jugaadBrokenPreview, jugaadMaterialsPreview]);

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
        saveOfflineDrafts(offlineDrafts);
    }, [offlineDrafts]);

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

    const syncOfflineDrafts = useCallback(async () => {
        if (!profile || offlineDrafts.length === 0) {
            return;
        }
        if (!navigator.onLine) {
            return;
        }

        setSyncingDrafts(true);
        try {
            const remaining: OfflineDraft[] = [];
            for (const draft of offlineDrafts) {
                try {
                    if (draft.kind === 'proof') {
                        const afterBlob = await dataUrlToBlob(draft.afterImage);
                        const beforeBlob = draft.beforeImage ? await dataUrlToBlob(draft.beforeImage) : null;
                        let beforeMediaId: string | undefined;
                        let afterMediaId: string | undefined;
                        if (beforeBlob) {
                            const beforeUpload = await api.uploadMedia(beforeBlob, {
                                kind: 'proof_before',
                                problemId: draft.problemId,
                                volunteerId: draft.volunteerId,
                                label: `${draft.taskTitle} before`,
                                filename: 'offline-before.jpg',
                            });
                            beforeMediaId = beforeUpload.media.id;
                        }
                        const afterUpload = await api.uploadMedia(afterBlob, {
                            kind: 'proof_after',
                            problemId: draft.problemId,
                            volunteerId: draft.volunteerId,
                            label: `${draft.taskTitle} after`,
                            filename: 'offline-after.jpg',
                        });
                        afterMediaId = afterUpload.media.id;
                        await api.submitProof(draft.problemId, {
                            volunteer_id: draft.volunteerId,
                            before_media_id: beforeMediaId,
                            after_media_id: afterMediaId,
                            notes: draft.notes || 'Synced from offline draft',
                        });
                    } else {
                        const brokenBlob = await dataUrlToBlob(draft.brokenImage);
                        const materialsBlob = await dataUrlToBlob(draft.materialsImage);
                        const [brokenUpload, materialsUpload] = await Promise.all([
                            api.uploadMedia(brokenBlob, {
                                kind: 'jugaad_broken',
                                problemId: draft.problemId,
                                volunteerId: draft.volunteerId,
                                label: `${draft.taskTitle} broken mechanism`,
                                filename: 'offline-broken.jpg',
                            }),
                            api.uploadMedia(materialsBlob, {
                                kind: 'jugaad_materials',
                                problemId: draft.problemId,
                                volunteerId: draft.volunteerId,
                                label: `${draft.taskTitle} available materials`,
                                filename: 'offline-materials.jpg',
                            }),
                        ]);
                        await api.requestJugaadRepair({
                            problem_id: draft.problemId,
                            volunteer_id: draft.volunteerId,
                            broken_media_id: brokenUpload.media.id,
                            materials_media_id: materialsUpload.media.id,
                            notes: draft.materialsNote || undefined,
                        });
                    }
                } catch (err) {
                    console.error('Failed to sync offline draft', err);
                    remaining.push(draft);
                }
            }
            setOfflineDrafts(remaining);
            if (remaining.length < offlineDrafts.length) {
                await loadTasks();
            }
        } finally {
            setSyncingDrafts(false);
        }
    }, [loadTasks, offlineDrafts, profile]);

    useEffect(() => {
        if (!profile) {
            return;
        }
        void syncOfflineDrafts();
        const handleOnline = () => {
            void syncOfflineDrafts();
        };
        window.addEventListener('online', handleOnline);
        return () => {
            window.removeEventListener('online', handleOnline);
        };
    }, [profile, syncOfflineDrafts]);

    useEffect(() => {
        if (!selectedTask) {
            return;
        }

        const latestTask = tasks.find((task) => task.id === selectedTask.id);
        if (!latestTask) {
            setSelectedTask(null);
            clearProofDraft();
            clearJugaadDraft();
            setJugaadResult(null);
            setJugaadError(null);
            return;
        }

        if (latestTask !== selectedTask) {
            setSelectedTask(latestTask);
        }
    }, [selectedTask, tasks]);

    useEffect(() => {
        if (selectedTask) {
            setSelectedTaskTab('details');
        }
    }, [selectedTask]);

    const queueProofDraft = useCallback(async () => {
        if (!selectedTask || !profile || !afterImageFile) {
            return false;
        }
        try {
            const afterImage = await blobToDataUrl(afterImageFile);
            const beforeImage = beforeImageFile ? await blobToDataUrl(beforeImageFile) : null;
            setOfflineDrafts((current) => [
                ...current,
                {
                    id: `draft-proof-${Date.now()}`,
                    kind: 'proof',
                    problemId: selectedTask.id,
                    taskTitle: selectedTask.title,
                    volunteerId: profile.id,
                    createdAt: new Date().toISOString(),
                    beforeImage,
                    afterImage,
                    notes: 'Stored offline while network was unavailable.',
                },
            ]);
            return true;
        } catch (err) {
            console.error('Failed to store offline proof draft', err);
            return false;
        }
    }, [afterImageFile, beforeImageFile, profile, selectedTask]);

    const queueJugaadDraft = useCallback(async () => {
        if (!selectedTask || !profile || !jugaadBrokenFile || !jugaadMaterialsFile) {
            return false;
        }
        try {
            const [brokenImage, materialsImage] = await Promise.all([
                blobToDataUrl(jugaadBrokenFile),
                blobToDataUrl(jugaadMaterialsFile),
            ]);
            setOfflineDrafts((current) => [
                ...current,
                {
                    id: `draft-jugaad-${Date.now()}`,
                    kind: 'jugaad',
                    problemId: selectedTask.id,
                    taskTitle: selectedTask.title,
                    volunteerId: profile.id,
                    createdAt: new Date().toISOString(),
                    brokenImage,
                    materialsImage,
                    materialsNote: jugaadMaterialsNote.trim() || undefined,
                },
            ]);
            return true;
        } catch (err) {
            console.error('Failed to store offline jugaad draft', err);
            return false;
        }
    }, [jugaadBrokenFile, jugaadMaterialsFile, jugaadMaterialsNote, profile, selectedTask]);

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
            const stored = !navigator.onLine && await queueProofDraft();
            alert(stored
                ? "No connection detected. The proof was saved offline and will sync automatically."
                : err instanceof Error
                    ? err.message
                    : "Failed to verify impact. Please try again.");
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleJugaadAssist = async () => {
        if (!selectedTask) {
            return;
        }
        if (!profile) {
            alert('Your volunteer profile is required to request repair guidance.');
            return;
        }
        if (!jugaadBrokenFile || !jugaadMaterialsFile) {
            alert("Please upload both the broken-part photo and the materials photo.");
            return;
        }

        setJugaadLoading(true);
        setJugaadError(null);
        setJugaadResult(null);

        try {
            const [brokenUpload, materialsUpload] = await Promise.all([
                api.uploadMedia(jugaadBrokenFile, {
                    kind: 'jugaad_broken',
                    problemId: selectedTask.id,
                    volunteerId: profile.id,
                    label: `${selectedTask.title} broken mechanism`,
                }),
                api.uploadMedia(jugaadMaterialsFile, {
                    kind: 'jugaad_materials',
                    problemId: selectedTask.id,
                    volunteerId: profile.id,
                    label: `${selectedTask.title} available materials`,
                }),
            ]);

            const result = await api.requestJugaadRepair({
                problem_id: selectedTask.id,
                volunteer_id: profile.id,
                broken_media_id: brokenUpload.media.id,
                materials_media_id: materialsUpload.media.id,
                notes: jugaadMaterialsNote.trim() || undefined,
            });

            setJugaadResult(result);
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Failed to generate temporary repair guidance.';
            setJugaadError(message);
            const stored = !navigator.onLine && await queueJugaadDraft();
            if (stored) {
                setJugaadError('No connection detected. The repair request was saved offline and will sync automatically.');
            }
        } finally {
            setJugaadLoading(false);
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
                            setJugaadResult(null);
                            setJugaadError(null);
                        }}
                        className="flex items-center gap-2 text-green-700 font-semibold mb-6"
                    >
                        <ArrowLeft size={20} /> {t('volunteer.back_to_tasks')}
                    </button>

                    {offlineDrafts.length > 0 && (
                        <div className="mb-6 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                            <div className="flex flex-wrap items-center justify-between gap-3">
                                <div>
                                    <div className="font-bold">Offline drafts waiting to sync</div>
                                    <div className="mt-1">{offlineDrafts.length} proof or repair updates are stored locally.</div>
                                </div>
                                <button
                                    type="button"
                                    onClick={() => void syncOfflineDrafts()}
                                    disabled={syncingDrafts || !navigator.onLine}
                                    className="rounded-xl bg-amber-500 px-4 py-2 font-semibold text-white transition hover:bg-amber-600 disabled:opacity-60"
                                >
                                    {syncingDrafts ? 'Syncing...' : navigator.onLine ? 'Sync now' : 'Offline'}
                                </button>
                            </div>
                        </div>
                    )}

                    <div className="bg-white rounded-2xl shadow-lg p-8">
                        <h2 className="text-2xl font-bold text-gray-900 mb-2">{t('seed.' + selectedTask.title, selectedTask.title)}</h2>
                        <p className="text-gray-600 mb-6">{t('seed.' + selectedTask.description, selectedTask.description)}</p>

                        <div className="flex items-center gap-2 text-sm text-gray-500 mb-8">
                            <MapPin size={16} className="text-green-600" />
                            <span>{t('seed.' + selectedTask.village, selectedTask.village)}, {t('seed.' + selectedTask.location, selectedTask.location)}</span>
                        </div>

                        <div className="mb-6 inline-flex rounded-2xl border border-gray-200 bg-white p-1 shadow-sm">
                            <button
                                type="button"
                                onClick={() => setSelectedTaskTab('details')}
                                className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${
                                    selectedTaskTab === 'details'
                                        ? 'bg-green-600 text-white shadow'
                                        : 'text-gray-600 hover:bg-gray-100'
                                }`}
                            >
                                Task details
                            </button>
                            <button
                                type="button"
                                onClick={() => setSelectedTaskTab('repair')}
                                className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${
                                    selectedTaskTab === 'repair'
                                        ? 'bg-amber-500 text-white shadow'
                                        : 'text-gray-600 hover:bg-gray-100'
                                }`}
                            >
                                Repair Assistant
                            </button>
                        </div>

                        {selectedTaskTab === 'details' ? (
                            <>
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
                            </>
                        ) : (
                            <div className="mb-8 rounded-2xl border border-amber-200 bg-gradient-to-br from-amber-50 via-white to-orange-50 p-6 shadow-sm">
                                <div className="flex flex-wrap items-start justify-between gap-4">
                                    <div>
                                        <div className="inline-flex items-center gap-2 rounded-full bg-amber-100 px-3 py-1 text-xs font-bold uppercase tracking-wider text-amber-700">
                                            <Sparkles size={14} /> Jugaad engine
                                        </div>
                                        <h3 className="mt-3 text-xl font-bold text-gray-900 flex items-center gap-2">
                                            <Wrench size={18} className="text-amber-600" />
                                            Help me fix this
                                        </h3>
                                        <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-600">
                                            Upload a photo of the broken mechanism and a photo of the materials you have on hand.
                                            The assistant will suggest a safe, temporary repair to keep the system usable until the proper part arrives.
                                        </p>
                                    </div>
                                    <div className="rounded-xl bg-white px-3 py-2 text-xs text-amber-800 shadow-sm border border-amber-100">
                                        Temporary only
                                    </div>
                                </div>

                                <div className="mt-5 grid gap-4 md:grid-cols-2">
                                    <div className="space-y-2">
                                        <p className="text-sm font-medium text-gray-700">Broken part photo</p>
                                        <label className="aspect-square flex flex-col items-center justify-center border-2 border-dashed border-amber-200 rounded-xl cursor-pointer hover:bg-amber-50 bg-white overflow-hidden">
                                            {jugaadBrokenPreview ? (
                                                <img src={jugaadBrokenPreview} className="w-full h-full object-cover" />
                                            ) : (
                                                <>
                                                    <Camera size={32} className="text-amber-500 mb-2" />
                                                    <span className="text-xs text-amber-700 font-bold">Upload broken part</span>
                                                </>
                                            )}
                                            <input
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
                                        <p className="text-sm font-medium text-gray-700">Materials on hand</p>
                                        <label className="aspect-square flex flex-col items-center justify-center border-2 border-dashed border-amber-200 rounded-xl cursor-pointer hover:bg-amber-50 bg-white overflow-hidden">
                                            {jugaadMaterialsPreview ? (
                                                <img src={jugaadMaterialsPreview} className="w-full h-full object-cover" />
                                            ) : (
                                                <>
                                                    <Camera size={32} className="text-amber-500 mb-2" />
                                                    <span className="text-xs text-amber-700 font-bold">Upload materials</span>
                                                </>
                                            )}
                                            <input
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

                                <div className="mt-4">
                                    <label className="mb-2 block text-sm font-medium text-gray-700">
                                        Optional note about the materials
                                    </label>
                                    <textarea
                                        value={jugaadMaterialsNote}
                                        onChange={(event) => setJugaadMaterialsNote(event.target.value)}
                                        rows={3}
                                        className="w-full rounded-xl border border-amber-200 bg-white px-4 py-3 text-sm text-gray-900 outline-none focus:border-amber-400"
                                        placeholder="Example: rubber tube, thin wire, bamboo stick, cloth, tape"
                                    />
                                </div>

                                <div className="mt-4 flex flex-col gap-3 sm:flex-row">
                                    <button
                                        type="button"
                                        onClick={handleJugaadAssist}
                                        disabled={jugaadLoading || !jugaadBrokenFile || !jugaadMaterialsFile}
                                        className="inline-flex items-center justify-center gap-2 rounded-xl bg-amber-500 px-5 py-3 font-bold text-white transition hover:bg-amber-600 disabled:cursor-not-allowed disabled:bg-gray-300"
                                    >
                                        {jugaadLoading ? <Loader2 className="animate-spin" size={16} /> : <Wrench size={16} />}
                                        {jugaadLoading ? 'Analyzing photos...' : 'Get temporary fix plan'}
                                    </button>
                                    {(jugaadBrokenFile || jugaadMaterialsFile || jugaadResult) && (
                                        <button
                                            type="button"
                                            onClick={() => {
                                                clearJugaadDraft();
                                                setJugaadResult(null);
                                                setJugaadError(null);
                                            }}
                                            className="inline-flex items-center justify-center gap-2 rounded-xl border border-amber-200 bg-white px-5 py-3 font-semibold text-amber-700 transition hover:bg-amber-50"
                                        >
                                            Clear photos
                                        </button>
                                    )}
                                </div>

                                {jugaadError && (
                                    <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                                        {jugaadError}
                                    </div>
                                )}

                                {jugaadResult && (
                                    <div className="mt-5 space-y-4 rounded-2xl border border-amber-200 bg-white p-5">
                                        <div className="flex flex-wrap items-start justify-between gap-3">
                                            <div>
                                                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-700">Assistant output</div>
                                                <h4 className="mt-1 text-lg font-bold text-gray-900">{jugaadResult.summary}</h4>
                                                <p className="mt-1 text-sm text-gray-600">{jugaadResult.problem_read}</p>
                                            </div>
                                            <div className="rounded-xl bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800">
                                                Confidence {(jugaadResult.confidence * 100).toFixed(0)}%
                                            </div>
                                        </div>

                                        <div className="rounded-xl border border-amber-100 bg-amber-50/60 p-4">
                                            <div className="text-sm font-bold text-amber-900">Temporary fix</div>
                                            <p className="mt-1 text-sm leading-6 text-amber-900">{jugaadResult.temporary_fix}</p>
                                        </div>

                                        <div className="grid gap-4 md:grid-cols-2">
                                            <div>
                                                <div className="text-sm font-bold text-gray-900 mb-2">Step-by-step</div>
                                                <ol className="space-y-2">
                                                    {jugaadResult.step_by_step.map((step, index) => (
                                                        <li key={`${index}-${step}`} className="rounded-xl bg-gray-50 px-3 py-2 text-sm text-gray-700">
                                                            <span className="font-bold text-amber-700">{index + 1}.</span> {step}
                                                        </li>
                                                    ))}
                                                </ol>
                                            </div>
                                            <div className="space-y-4">
                                                <div>
                                                    <div className="text-sm font-bold text-gray-900 mb-2">Use these materials</div>
                                                    <div className="flex flex-wrap gap-2">
                                                        {jugaadResult.materials_to_use.map((item) => (
                                                            <span key={item} className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800">
                                                                {item}
                                                            </span>
                                                        ))}
                                                    </div>
                                                </div>
                                                <div>
                                                    <div className="text-sm font-bold text-gray-900 mb-2">Avoid these</div>
                                                    <div className="flex flex-wrap gap-2">
                                                        {jugaadResult.materials_to_avoid.map((item) => (
                                                            <span key={item} className="rounded-full bg-red-100 px-3 py-1 text-xs font-semibold text-red-700">
                                                                {item}
                                                            </span>
                                                        ))}
                                                    </div>
                                                </div>
                                            </div>
                                        </div>

                                        <div className="grid gap-4 md:grid-cols-2">
                                            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                                                <div className="text-sm font-bold text-slate-900">Safety notes</div>
                                                <ul className="mt-2 space-y-2 text-sm text-slate-700">
                                                    {jugaadResult.safety_notes.map((item) => (
                                                        <li key={item}>• {item}</li>
                                                    ))}
                                                </ul>
                                            </div>
                                            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                                                <div className="text-sm font-bold text-slate-900">Stop immediately if</div>
                                                <ul className="mt-2 space-y-2 text-sm text-slate-700">
                                                    {jugaadResult.when_to_stop.map((item) => (
                                                        <li key={item}>• {item}</li>
                                                    ))}
                                                </ul>
                                                <div className="mt-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
                                                    {jugaadResult.needs_official_part ? 'Official part still needed' : 'Temporary fix may be enough for now'}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
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

                {offlineDrafts.length > 0 && (
                    <div className="mb-6 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                            <div>
                                <div className="font-bold">Offline drafts waiting to sync</div>
                                <div className="mt-1">{offlineDrafts.length} proof or repair updates are stored locally.</div>
                            </div>
                            <button
                                type="button"
                                onClick={() => void syncOfflineDrafts()}
                                disabled={syncingDrafts || !navigator.onLine}
                                className="rounded-xl bg-amber-500 px-4 py-2 font-semibold text-white transition hover:bg-amber-600 disabled:opacity-60"
                            >
                                {syncingDrafts ? 'Syncing...' : navigator.onLine ? 'Sync now' : 'Offline'}
                            </button>
                        </div>
                    </div>
                )}

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
