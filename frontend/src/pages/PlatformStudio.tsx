import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { BookOpen, Brain, Building2, ClipboardList, FileSignature, Gauge, Megaphone, ShieldCheck, Sparkles, Users } from 'lucide-react';
import { useAuth } from '../contexts/auth-shared';
import { api, type PlatformOverviewResponse } from '../services/api';
import { Navigate } from 'react-router-dom';

type RecordDraft = {
  record_id?: string;
  subtype?: string;
  owner_id?: string;
  status?: string;
  data: string;
};

function Card({ title, icon, children, accent = 'text-slate-700' }: { title: string; icon: JSX.Element; children: ReactNode; accent?: string }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center gap-2">
        <div className={accent}>{icon}</div>
        <h2 className="text-lg font-bold text-slate-900">{title}</h2>
      </div>
      <div className="mt-4 space-y-3">{children}</div>
    </section>
  );
}

function JsonList({ items }: { items: Array<Record<string, unknown>> }) {
  if (!items.length) {
    return <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-500">No records yet.</div>;
  }
  return (
    <div className="space-y-3">
      {items.slice(0, 4).map((item, index) => (
        <pre key={String(item.id || index)} className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
          {JSON.stringify(item, null, 2)}
        </pre>
      ))}
    </div>
  );
}

export default function PlatformStudio() {
  const { profile } = useAuth();
  const [overview, setOverview] = useState<PlatformOverviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [problemId, setProblemId] = useState('');
  const [formText, setFormText] = useState('');
  const [policyQuestion, setPolicyQuestion] = useState('');
  const [residentResponse, setResidentResponse] = useState<'resolved' | 'still_broken' | 'needs_more_help'>('resolved');
  const [residentNote, setResidentNote] = useState('');
  const [similarity, setSimilarity] = useState<Record<string, unknown> | null>(null);
  const [auditPack, setAuditPack] = useState<Record<string, unknown> | null>(null);
  const [autofill, setAutofill] = useState<Record<string, unknown> | null>(null);
  const [policyAnswer, setPolicyAnswer] = useState<Record<string, unknown> | null>(null);
  const [residentConfirmation, setResidentConfirmation] = useState<Record<string, unknown> | null>(null);
  const [exportPack, setExportPack] = useState<Record<string, unknown> | null>(null);
  const [recordError, setRecordError] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, RecordDraft>>({
    asset: { data: '{}' },
    procurement: { data: '{}' },
    privacy_setting: { data: '{}' },
    certification: { data: '{}' },
    shift_plan: { data: '{}' },
    training_module: { data: '{}' },
    burnout_signal: { data: '{}' },
    suggestion: { data: '{}' },
    poll: { data: '{}' },
    announcement: { data: '{}' },
    champion: { data: '{}' },
    custom_form: { data: '{}' },
    webhook_event: { data: '{}' },
    conversation_memory: { data: '{}' },
  });

  const loadOverview = async () => {
    setLoading(true);
    try {
      const data = await api.getPlatformOverview();
      setOverview(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load platform studio');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadOverview();
  }, []);

  if (!profile || !['coordinator', 'supervisor', 'partner'].includes(profile.role)) {
    return <Navigate to="/" replace />;
  }

  const sectionCounts = useMemo(() => overview?.record_counts || {}, [overview]);
  const assetRows = (((overview as any)?.asset_registry?.assets ?? []) as Array<Record<string, unknown>>);
  const procurementRows = (((overview as any)?.procurement_tracker?.items ?? []) as Array<Record<string, unknown>>);
  const spoofRows = (((overview as any)?.proof_spoofing ?? []) as Array<Record<string, unknown>>);
  const residentRows = (((overview as any)?.resident_confirmation ?? []) as Array<Record<string, unknown>>);
  const certificationRows = (((overview as any)?.skill_certifications ?? []) as Array<Record<string, unknown>>);
  const suggestionRows = (((overview as any)?.suggestion_box ?? []) as Array<Record<string, unknown>>);
  const pollRows = (((overview as any)?.community_polls ?? []) as Array<Record<string, unknown>>);
  const announcementRows = (((overview as any)?.announcements ?? []) as Array<Record<string, unknown>>);
  const championRows = (((overview as any)?.village_champions ?? []) as Array<Record<string, unknown>>);
  const anomalyRows = (((overview as any)?.anomalies ?? []) as Array<Record<string, unknown>>);
  const abRows = (((overview as any)?.ab_tests ?? []) as Array<Record<string, unknown>>);
  const workOrderRows = (((overview as any)?.work_order_templates ?? []) as Array<Record<string, unknown>>);
  const districtRows = (((overview as any)?.district_hierarchy ?? {}) as Record<string, unknown>);
  const trainingRows = (((overview as any)?.training_mode ?? []) as Array<Record<string, unknown>>);
  const impactRows = (((overview as any)?.impact ?? {}) as Record<string, unknown>);
  const budgetRows = (((overview as any)?.budget_forecast ?? {}) as Record<string, unknown>);
  const memoryRows = (((overview as any)?.conversation_memory ?? {}) as Record<string, unknown>);

  const saveRecord = async (recordType: string) => {
    const draft = drafts[recordType];
    try {
      const parsedData = JSON.parse(draft.data || '{}');
      setRecordError(null);
      await api.savePlatformRecord(recordType, {
        record_id: draft.record_id,
        subtype: draft.subtype,
        owner_id: draft.owner_id,
        status: draft.status,
        data: parsedData,
      });
      await loadOverview();
    } catch (err) {
      setRecordError(err instanceof Error ? err.message : `Failed to save ${recordType} record`);
    }
  };

  const addRecordInput = (recordType: string, label: string) => (
    <div className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-3">
      <div className="text-xs font-bold uppercase tracking-wide text-slate-500">{label}</div>
      <input
        value={drafts[recordType].record_id || ''}
        onChange={(event) => setDrafts((current) => ({ ...current, [recordType]: { ...current[recordType], record_id: event.target.value } }))}
        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
        placeholder="Record ID (optional)"
      />
      <input
        value={drafts[recordType].subtype || ''}
        onChange={(event) => setDrafts((current) => ({ ...current, [recordType]: { ...current[recordType], subtype: event.target.value } }))}
        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
        placeholder="Subtype"
      />
      <input
        value={drafts[recordType].owner_id || ''}
        onChange={(event) => setDrafts((current) => ({ ...current, [recordType]: { ...current[recordType], owner_id: event.target.value } }))}
        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
        placeholder="Owner / village ID"
      />
      <input
        value={drafts[recordType].status || ''}
        onChange={(event) => setDrafts((current) => ({ ...current, [recordType]: { ...current[recordType], status: event.target.value } }))}
        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
        placeholder="Status"
      />
      <textarea
        value={drafts[recordType].data}
        onChange={(event) => setDrafts((current) => ({ ...current, [recordType]: { ...current[recordType], data: event.target.value } }))}
        rows={4}
        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-mono"
        placeholder='{"title":"Example"}'
      />
      <button
        type="button"
        onClick={() => void saveRecord(recordType)}
        className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white"
      >
        Save {label}
      </button>
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-10">
      <div className="mx-auto max-w-7xl space-y-8">
        <div className="rounded-3xl border border-slate-200 bg-gradient-to-br from-slate-950 via-slate-900 to-emerald-900 p-8 text-white shadow-xl">
          <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-bold uppercase tracking-[0.2em] text-emerald-200">
            <Sparkles size={14} /> Platform studio
          </div>
          <h1 className="mt-4 text-3xl font-black">Operations, trust, people, analytics, AI, and platform tools</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">
            This control surface bundles the missing management features into one place so coordinators, supervisors, and partners can operate the system without switching between hidden admin tools.
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <div className="rounded-2xl bg-white/10 p-4">
              <div className="text-xs uppercase tracking-[0.18em] text-slate-300">Assets</div>
              <div className="mt-1 text-2xl font-extrabold">{sectionCounts.asset || 0}</div>
            </div>
            <div className="rounded-2xl bg-white/10 p-4">
              <div className="text-xs uppercase tracking-[0.18em] text-slate-300">Community</div>
              <div className="mt-1 text-2xl font-extrabold">{(sectionCounts.suggestion || 0) + (sectionCounts.poll || 0) + (sectionCounts.announcement || 0)}</div>
            </div>
            <div className="rounded-2xl bg-white/10 p-4">
              <div className="text-xs uppercase tracking-[0.18em] text-slate-300">AI records</div>
              <div className="mt-1 text-2xl font-extrabold">{sectionCounts.conversation_memory || 0}</div>
            </div>
          </div>
        </div>

        {loading && <div className="rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-500">Loading platform studio...</div>}
        {error && <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{error}</div>}
        {recordError && <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">{recordError}</div>}

        <div className="grid gap-6 lg:grid-cols-2">
          <Card title="Asset lifecycle registry" icon={<Building2 size={18} />}>
            <JsonList items={assetRows} />
            {addRecordInput('asset', 'Asset record')}
          </Card>
          <Card title="Procurement tracker" icon={<ClipboardList size={18} />}>
            <JsonList items={procurementRows} />
            {addRecordInput('procurement', 'Procurement record')}
          </Card>
          <Card title="Trust and verification" icon={<ShieldCheck size={18} />}>
            <JsonList items={spoofRows} />
            {addRecordInput('privacy_setting', 'Privacy setting')}
            <div className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
              <div className="font-semibold text-slate-700">Resident confirmation</div>
              <input value={problemId} onChange={(event) => setProblemId(event.target.value)} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="Problem ID" />
              <textarea value={residentNote} onChange={(event) => setResidentNote(event.target.value)} rows={2} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="Confirmation note" />
              <div className="flex flex-wrap gap-2">
                {(['resolved', 'still_broken', 'needs_more_help'] as const).map((value) => (
                  <button key={value} type="button" onClick={() => setResidentResponse(value)} className={`rounded-full px-3 py-1 text-xs font-semibold ${residentResponse === value ? 'bg-emerald-600 text-white' : 'border border-slate-300 bg-white text-slate-600'}`}>
                    {value}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={async () => setResidentConfirmation(await api.submitResidentConfirmation(problemId, { response: residentResponse, note: residentNote, source: 'public-board' }))}
                  className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white"
                >
                  Submit confirmation
                </button>
              </div>
              <pre className="overflow-x-auto rounded-xl border border-slate-200 bg-white p-3 text-xs text-slate-700">{JSON.stringify(residentConfirmation || {}, null, 2)}</pre>
            </div>
          </Card>
          <Card title="People and staffing" icon={<Users size={18} />}>
            <JsonList items={certificationRows} />
            {addRecordInput('certification', 'Certification')}
            {addRecordInput('shift_plan', 'Shift plan')}
            {addRecordInput('training_module', 'Training module')}
            {addRecordInput('burnout_signal', 'Burnout signal')}
          </Card>
          <Card title="Community signals" icon={<Megaphone size={18} />}>
            <JsonList items={suggestionRows} />
            <JsonList items={pollRows} />
            <JsonList items={announcementRows} />
            <JsonList items={championRows} />
            {addRecordInput('suggestion', 'Suggestion')}
            {addRecordInput('poll', 'Poll')}
            {addRecordInput('announcement', 'Announcement')}
            {addRecordInput('champion', 'Village champion')}
          </Card>
          <Card title="Planning and analytics" icon={<Gauge size={18} />}>
            <JsonList items={anomalyRows} />
            <JsonList items={abRows} />
            <pre className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">{JSON.stringify(impactRows || {}, null, 2)}</pre>
            <pre className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">{JSON.stringify(budgetRows || {}, null, 2)}</pre>
          </Card>
          <Card title="AI control room" icon={<Brain size={18} />}>
            <div className="space-y-2">
              <label className="block text-sm font-medium text-slate-700">Case text autofill</label>
              <textarea value={formText} onChange={(event) => setFormText(event.target.value)} rows={3} className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" placeholder="Describe a problem..." />
              <button type="button" onClick={async () => setAutofill(await api.autofillProblemForm({ text: formText }))} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white">Autofill</button>
              <pre className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">{JSON.stringify(autofill || {}, null, 2)}</pre>
            </div>
            <div className="space-y-2">
              <label className="block text-sm font-medium text-slate-700">Case similarity</label>
              <input value={problemId} onChange={(event) => setProblemId(event.target.value)} className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" placeholder="Problem ID" />
              <div className="flex gap-2">
                <button type="button" onClick={async () => setSimilarity(await api.getCaseSimilarity(problemId))} className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white">Find similar</button>
                <button type="button" onClick={async () => setAuditPack(await api.getAuditPack(problemId))} className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white">Audit pack</button>
              </div>
              <pre className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">{JSON.stringify(similarity || auditPack || {}, null, 2)}</pre>
            </div>
            <div className="space-y-2">
              <label className="block text-sm font-medium text-slate-700">Policy copilot</label>
              <textarea value={policyQuestion} onChange={(event) => setPolicyQuestion(event.target.value)} rows={3} className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" placeholder="Ask about privacy, escalation, or procurement..." />
              <button type="button" onClick={async () => setPolicyAnswer(await api.askPolicyQuestion(policyQuestion))} className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white">Ask policy</button>
              <pre className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">{JSON.stringify(policyAnswer || {}, null, 2)}</pre>
            </div>
          </Card>
          <Card title="Platform admin" icon={<FileSignature size={18} />}>
            {addRecordInput('custom_form', 'Custom form')}
            {addRecordInput('webhook_event', 'Webhook event')}
            {addRecordInput('conversation_memory', 'Conversation memory')}
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={async () => setExportPack(await api.getPlatformExport())} className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white">Build export pack</button>
              <button type="button" onClick={loadOverview} className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700">Refresh</button>
            </div>
            <pre className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">{JSON.stringify(exportPack || {}, null, 2)}</pre>
          </Card>
          <Card title="Control summaries" icon={<BookOpen size={18} />}>
            <JsonList items={workOrderRows} />
            <pre className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">{JSON.stringify(districtRows || {}, null, 2)}</pre>
            <JsonList items={residentRows} />
            <JsonList items={trainingRows} />
            <pre className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">{JSON.stringify(memoryRows || {}, null, 2)}</pre>
          </Card>
        </div>
      </div>
    </div>
  );
}
