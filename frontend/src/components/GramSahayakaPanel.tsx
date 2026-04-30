import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, ChevronRight, MessageSquare, RefreshCw, Sparkles } from 'lucide-react';
import { api, type ChatResponse, type ClusterResponse } from '../services/api';

const EXAMPLES = [
  'Which villages have had the most water-related issues this month?',
  "Show me all volunteers in Nirmalgaon who know masonry but haven't been assigned anything in 2 weeks.",
  'Summarize the major complaints from Sundarpur.',
];

function parseAnswerText(answer: string): string[] {
  return answer
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
}

export default function GramSahayakaPanel() {
  const [query, setQuery] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [chatResponse, setChatResponse] = useState<ChatResponse | null>(null);

  const [clusterLoading, setClusterLoading] = useState(true);
  const [clusterError, setClusterError] = useState<string | null>(null);
  const [clusters, setClusters] = useState<ClusterResponse | null>(null);

  const refreshClusters = useCallback(async () => {
    setClusterLoading(true);
    setClusterError(null);
    try {
      const data = await api.getEpidemicClusters();
      setClusters(data);
    } catch (error) {
      setClusterError(error instanceof Error ? error.message : 'Failed to fetch cluster insights.');
      setClusters(null);
    } finally {
      setClusterLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshClusters();
  }, [refreshClusters]);

  const submitQuery = useCallback(async (value: string) => {
    const trimmed = value.trim();
    if (!trimmed) {
      return;
    }
    setChatLoading(true);
    setChatError(null);
    try {
      const response = await api.chatWithGramSahayaka(trimmed);
      setChatResponse(response);
      setQuery('');
    } catch (error) {
      setChatError(error instanceof Error ? error.message : 'Chat request failed.');
    } finally {
      setChatLoading(false);
    }
  }, []);

  return (
    <section className="mb-8 grid gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
      <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <div className="mb-2 flex items-center gap-2">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-100 text-emerald-700">
                <MessageSquare size={18} />
              </div>
              <div>
                <h2 className="text-lg font-bold text-gray-900">Gram-Sahayaka</h2>
                <p className="text-sm text-gray-500">Ask the dashboard for trends, outliers, or volunteer filters.</p>
              </div>
            </div>
            <p className="text-sm text-gray-600">
              Use plain language. The assistant analyzes current problems and volunteer records before replying.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void submitQuery(query)}
            disabled={chatLoading}
            className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {chatLoading ? <RefreshCw size={16} className="animate-spin" /> : <Sparkles size={16} />}
            Ask
          </button>
        </div>

        <div className="mb-4 rounded-xl border border-gray-200 bg-gray-50 p-3">
          <label htmlFor="gram-sahayaka-query" className="mb-2 block text-xs font-bold uppercase tracking-wide text-gray-500">
            Ask a question
          </label>
          <textarea
            id="gram-sahayaka-query"
            rows={3}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
                event.preventDefault();
                void submitQuery(query);
              }
            }}
            placeholder="Ask about villages, volunteer skills, recurring complaints, or assignment gaps."
            className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100"
          />
          <div className="mt-3 flex flex-wrap gap-2">
            {EXAMPLES.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => void submitQuery(example)}
                className="inline-flex items-center gap-1 rounded-full border border-emerald-100 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-100"
              >
                {example}
                <ChevronRight size={12} />
              </button>
            ))}
          </div>
        </div>

        {chatError && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {chatError}
          </div>
        )}

        {chatResponse ? (
          <div className="rounded-xl border border-emerald-100 bg-emerald-50/60 p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-emerald-800">
              <Sparkles size={16} />
              Answer
            </div>
            <div className="space-y-2 text-sm leading-6 text-gray-800">
              {parseAnswerText(chatResponse.answer).map((line, index) => (
                <p key={`${line}-${index}`}>{line}</p>
              ))}
            </div>
            {chatResponse.analysis && (
              <div className="mt-4 rounded-lg bg-white p-3 text-xs text-gray-500">
                <span className="font-semibold text-gray-700">Analyzed</span> {chatResponse.analysis.problem_count} problems and {chatResponse.analysis.volunteer_count} volunteers.
              </div>
            )}
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-4 text-sm text-gray-500">
            Ask a question to get a data-backed answer from the current dashboard state.
          </div>
        )}
      </div>

      <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <div className="mb-2 flex items-center gap-2">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-100 text-amber-700">
                <AlertTriangle size={18} />
              </div>
              <div>
                <h2 className="text-lg font-bold text-gray-900">Predictive Cluster Alerts</h2>
                <p className="text-sm text-gray-500">Semantic and geographic clusters pulled from recent problems.</p>
              </div>
            </div>
            <p className="text-sm text-gray-600">
              Health risks and recurring infrastructure failures are surfaced before they become isolated tickets.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void refreshClusters()}
            disabled={clusterLoading}
            className="inline-flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {clusterLoading ? <RefreshCw size={16} className="animate-spin" /> : <RefreshCw size={16} />}
            Refresh
          </button>
        </div>

        {clusterError && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {clusterError}
          </div>
        )}

        {clusters ? (
          <div className="space-y-4">
            <div className="rounded-xl border border-gray-200 bg-gray-50 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wide ${
                  clusters.risk_level === 'HIGH'
                    ? 'bg-red-100 text-red-700'
                    : clusters.risk_level === 'MODERATE'
                      ? 'bg-amber-100 text-amber-700'
                      : 'bg-emerald-100 text-emerald-700'
                }`}>
                  {clusters.risk_level} risk
                </span>
                <span className="text-xs font-medium text-gray-500">
                  {clusters.total_problems} open problems analyzed
                </span>
              </div>
              <p className="mt-3 text-sm leading-6 text-gray-700 whitespace-pre-line">{clusters.summary}</p>
            </div>

            {clusters.clusters.length > 0 ? (
              <div className="space-y-3">
                {clusters.clusters.map((cluster) => (
                  <div key={cluster.id} className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="text-sm font-bold text-gray-900">{cluster.name}</h3>
                          <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${
                            cluster.severity === 'HIGH'
                              ? 'bg-red-100 text-red-700'
                              : 'bg-amber-100 text-amber-700'
                          }`}>
                            {cluster.severity}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-gray-500">
                          {cluster.problem_count} problems across {cluster.village_count} villages
                        </p>
                      </div>
                      <span className="rounded-full bg-gray-100 px-2 py-1 text-[11px] font-semibold text-gray-600">
                        {(cluster.confidence * 100).toFixed(0)}% confidence
                      </span>
                    </div>

                    <p className="mt-3 text-sm leading-6 text-gray-700">{cluster.recommendation}</p>

                    <div className="mt-3 flex flex-wrap gap-2">
                      {cluster.villages.slice(0, 4).map((village) => (
                        <span key={village} className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
                          {village}
                        </span>
                      ))}
                      {cluster.categories?.slice(0, 3).map((category) => (
                        <span key={category} className="rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700">
                          {category}
                        </span>
                      ))}
                    </div>

                    {cluster.sample_titles?.length ? (
                      <div className="mt-3 text-xs text-gray-500">
                        Examples: {cluster.sample_titles.join(' · ')}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-4 text-sm text-gray-500">
                No strong clusters were detected in the current open problem set.
              </div>
            )}
          </div>
        ) : clusterLoading ? (
          <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-4 text-sm text-gray-500">
            Loading cluster insights...
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-4 text-sm text-gray-500">
            Cluster insights will appear here after refresh.
          </div>
        )}
      </div>
    </section>
  );
}
