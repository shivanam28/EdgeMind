"use client";

import { useEffect, useState } from "react";

const API_BASE = "http://localhost:8000";

type Memory = {
  point_id: number;
  payload: { text: string; category: string; security_tier: string };
};

type SearchResult = {
  point_id: number;
  score: number;
  payload: { text: string; category: string; security_tier: string };
};

type SyncRecord = {
  id: number;
  point_id: string;
  mutation_type: string;
  dirty_flag: number;
  retry_count: number;
  error_message: string | null;
};

type SyncStatus = {
  total_records: number;
  pending_count: number;
  synced_count: number;
  local_only_count: number;
  failed_count: number;
  records: SyncRecord[];
};

type Tab = "notes" | "search" | "sync" | "conflicts";

const NAV: { id: Tab; label: string }[] = [
  { id: "notes", label: "Notes" },
  { id: "search", label: "Search" },
  { id: "sync", label: "Sync" },
  { id: "conflicts", label: "Conflicts" },
];

export default function Dashboard() {
  const [tab, setTab] = useState<Tab>("notes");
  const [isOnline, setIsOnline] = useState<boolean | null>(null);
  const [toggling, setToggling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [memories, setMemories] = useState<Memory[]>([]);
  const [cloudMemories, setCloudMemories] = useState<Memory[]>([]);
  const [cloudReachable, setCloudReachable] = useState(true);
  const [newText, setNewText] = useState("");
  const [adding, setAdding] = useState(false);
  const [lastFiled, setLastFiled] = useState<{ category: string; tier: string } | null>(null);

  const [query, setQuery] = useState("");
  const [filterTier, setFilterTier] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchRan, setSearchRan] = useState(false);

  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [lastSyncResult, setLastSyncResult] = useState<string | null>(null);
  const [resolving, setResolving] = useState<number | null>(null);

  async function api<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    });
    if (!res.ok) throw new Error(`Request failed (${res.status})`);
    return res.json();
  }

  async function refreshAll() {
    try {
      const [net, mem, sync, cloud] = await Promise.all([
        api<{ is_online: boolean }>("/network/status"),
        api<{ memories: Memory[] }>("/memory"),
        api<SyncStatus>("/sync/status"),
        api<{ memories: Memory[]; reachable: boolean }>("/cloud/memory"),
      ]);
      setIsOnline(net.is_online);
      setMemories(mem.memories);
      setSyncStatus(sync);
      setCloudReachable(cloud.reachable);
      setCloudMemories(cloud.memories);
      setError(null);
    } catch {
      setError("Backend not reachable. Start the API on port 8000.");
    }
  }

  useEffect(() => {
    refreshAll();
  }, []);

  async function toggleNetwork() {
    setToggling(true);
    try {
      const next = !isOnline;
      await api(`/network/toggle?online=${next}`, { method: "POST" });
      await refreshAll();
    } catch {
      setError("Could not change network state.");
    } finally {
      setToggling(false);
    }
  }

  async function addNote() {
    if (!newText.trim()) return;
    setAdding(true);
    try {
      const result = await api<{ payload: { category: string; security_tier: string } }>("/memory", {
        method: "POST",
        body: JSON.stringify({ text: newText }),
      });
      setLastFiled({ category: result.payload.category, tier: result.payload.security_tier });
      setNewText("");
      await refreshAll();
    } catch {
      setError("Could not save the note.");
    } finally {
      setAdding(false);
    }
  }

  async function runSearch() {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const body: Record<string, unknown> = { query, limit: 8 };
      if (filterTier) body.security_tier = filterTier;
      const result = await api<{ results: SearchResult[] }>("/search", {
        method: "POST",
        body: JSON.stringify(body),
      });
      setResults(result.results);
      setSearchRan(true);
    } catch {
      setError("Search could not be completed.");
    } finally {
      setSearching(false);
    }
  }

  async function runSync() {
    setSyncing(true);
    try {
      const result = await api<{ status: string; synced: number; failed: number; conflicts: number }>(
        "/sync/run",
        { method: "POST" }
      );
      setLastSyncResult(
        result.status === "skipped"
          ? "Skipped, offline"
          : `Synced ${result.synced} · Conflicts ${result.conflicts} · Failed ${result.failed}`
      );
      await refreshAll();
    } catch {
      setError("Sync could not be completed.");
    } finally {
      setSyncing(false);
    }
  }

  async function resolve(pointId: number, choice: "edge" | "cloud") {
    setResolving(pointId);
    try {
      await api("/sync/resolve", { method: "POST", body: JSON.stringify({ point_id: pointId, choice }) });
      await refreshAll();
    } catch {
      setError("Could not resolve the conflict.");
    } finally {
      setResolving(null);
    }
  }

  function tierClass(tier: string) {
    if (tier === "LOCAL_ONLY") return "bg-red-100 text-red-700";
    if (tier === "CLOUD_RESIDENT") return "bg-blue-100 text-blue-700";
    return "bg-amber-100 text-amber-700";
  }

  const cloudIds = new Set(cloudMemories.map((m) => m.point_id));
  const conflicts = (syncStatus?.records || []).filter((r) => r.error_message?.includes("CONFLICT"));
  const pending = (syncStatus?.records || []).filter((r) => r.dirty_flag === 1);

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900 flex">
      {/* Sidebar */}
      <aside className="w-48 shrink-0 border-r border-gray-200 bg-white p-4 flex flex-col gap-1">
        <div className="flex items-center gap-2 mb-6">
          <img src="/logo.png" alt="EdgeMind" className="h-7 w-7 rounded" />
          <span className="font-semibold">EdgeMind</span>
        </div>
        {NAV.map((item) => (
          <button
            key={item.id}
            onClick={() => setTab(item.id)}
            className={`text-left px-3 py-2 rounded text-sm ${
              tab === item.id ? "bg-gray-100 font-medium" : "text-gray-500 hover:bg-gray-50"
            }`}
          >
            {item.label}
            {item.id === "conflicts" && conflicts.length > 0 && (
              <span className="ml-2 text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded-full">
                {conflicts.length}
              </span>
            )}
          </button>
        ))}
      </aside>

      {/* Main */}
      <main className="flex-1 p-6 max-w-4xl">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-lg font-semibold capitalize">{tab}</h1>
          <button
            onClick={toggleNetwork}
            disabled={toggling}
            className={`text-sm px-3 py-1.5 rounded font-medium disabled:opacity-50 ${
              isOnline ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
            }`}
          >
            {toggling ? "..." : isOnline ? "Online" : "Offline"}
          </button>
        </div>

        {error && (
          <div className="mb-4 text-sm bg-red-50 border border-red-200 text-red-700 rounded px-3 py-2">
            {error}
          </div>
        )}
        {isOnline === false && (
          <div className="mb-4 text-sm bg-amber-50 border border-amber-200 text-amber-700 rounded px-3 py-2">
            Offline mode: notes and search keep working locally. Sync is paused.
          </div>
        )}

        {tab === "notes" && (
          <div>
            <div className="flex gap-2 mb-3">
              <input
                value={newText}
                onChange={(e) => setNewText(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addNote()}
                placeholder="Write a note..."
                className="flex-1 bg-white border border-gray-300 rounded px-3 py-2 text-sm outline-none focus:border-teal-600"
              />
              <button
                onClick={addNote}
                disabled={adding}
                className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded text-sm disabled:opacity-50"
              >
                {adding ? "Saving..." : "Save"}
              </button>
            </div>
            {lastFiled && (
              <p className="text-xs text-gray-500 mb-4">
                Filed as {lastFiled.category} ·{" "}
                <span className={`px-1.5 py-0.5 rounded ${tierClass(lastFiled.tier)}`}>{lastFiled.tier}</span>
              </p>
            )}
            <p className="text-xs text-gray-400 mb-2">{memories.length} notes on this device</p>
            <div className="flex flex-col gap-2">
              {[...memories].reverse().map((m) => (
                <div key={m.point_id} className="bg-white border border-gray-200 rounded p-3">
                  <p className="text-sm mb-2">{m.payload.text}</p>
                  <div className="flex gap-2">
                    <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                      {m.payload.category}
                    </span>
                    <span className={`text-xs px-2 py-0.5 rounded ${tierClass(m.payload.security_tier)}`}>
                      {m.payload.security_tier}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === "search" && (
          <div>
            <div className="flex gap-2 mb-2">
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && runSearch()}
                placeholder="e.g. breathing problems"
                className="flex-1 bg-white border border-gray-300 rounded px-3 py-2 text-sm outline-none focus:border-teal-600"
              />
              <select
                value={filterTier}
                onChange={(e) => setFilterTier(e.target.value)}
                className="bg-white border border-gray-300 rounded px-2 text-sm"
              >
                <option value="">Any tier</option>
                <option value="LOCAL_ONLY">Local only</option>
                <option value="HYBRID">Hybrid</option>
                <option value="CLOUD_RESIDENT">Cloud resident</option>
              </select>
              <button
                onClick={runSearch}
                disabled={searching}
                className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded text-sm disabled:opacity-50"
              >
                {searching ? "..." : "Search"}
              </button>
            </div>
            <p className="text-xs text-gray-400 mb-4">
              The tier filter excludes records first; results are then ranked by meaning.
            </p>
            {searchRan && results.length === 0 && (
              <p className="text-sm text-gray-500">No matching notes.</p>
            )}
            <div className="flex flex-col gap-2">
              {results.map((r) => (
                <div key={r.point_id} className="bg-white border border-gray-200 rounded p-3">
                  <div className="flex justify-between mb-2">
                    <p className="text-sm">{r.payload.text}</p>
                    <span className="text-xs text-teal-700 ml-3 whitespace-nowrap">
                      {(r.score * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="flex gap-2">
                    <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                      {r.payload.category}
                    </span>
                    <span className={`text-xs px-2 py-0.5 rounded ${tierClass(r.payload.security_tier)}`}>
                      {r.payload.security_tier}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === "sync" && (
          <div>
            <div className="grid grid-cols-4 gap-3 mb-4">
              <div className="bg-white border border-gray-200 rounded p-3 text-center">
                <p className="text-xl font-semibold text-amber-600">{syncStatus?.pending_count ?? 0}</p>
                <p className="text-xs text-gray-500">Pending</p>
              </div>
              <div className="bg-white border border-gray-200 rounded p-3 text-center">
                <p className="text-xl font-semibold text-green-600">{syncStatus?.synced_count ?? 0}</p>
                <p className="text-xs text-gray-500">Synced</p>
              </div>
              <div className="bg-white border border-gray-200 rounded p-3 text-center">
                <p className="text-xl font-semibold text-red-500">{syncStatus?.local_only_count ?? 0}</p>
                <p className="text-xs text-gray-500">On device</p>
              </div>
              <div className="bg-white border border-gray-200 rounded p-3 text-center">
                <p className="text-xl font-semibold text-red-600">{syncStatus?.failed_count ?? 0}</p>
                <p className="text-xs text-gray-500">Failed</p>
              </div>
            </div>
            <button
              onClick={runSync}
              disabled={syncing}
              className="w-full py-2 bg-teal-600 hover:bg-teal-700 text-white rounded text-sm mb-3 disabled:opacity-50"
            >
              {syncing ? "Syncing..." : "Run sync"}
            </button>
            {lastSyncResult && <p className="text-sm text-gray-500 mb-4">{lastSyncResult}</p>}

            <p className="text-xs text-gray-400 mb-2">Pending records</p>
            <div className="flex flex-col gap-1 mb-6">
              {pending.length === 0 && <p className="text-sm text-gray-400">Nothing waiting to sync.</p>}
              {pending.map((r) => (
                <div key={r.id} className="bg-white border border-gray-200 rounded px-3 py-2 text-xs flex justify-between">
                  <span>{r.mutation_type} · Point {r.point_id}</span>
                  <span className="text-gray-400">{r.retry_count} retries</span>
                </div>
              ))}
            </div>

            <p className="text-xs text-gray-400 mb-2">
              Edge (this device) vs cloud — {cloudReachable ? `${cloudMemories.length} on cloud` : "cloud unreachable"}
            </p>
            <div className="flex flex-col gap-1">
              {memories.map((m) => {
                const isLocal = m.payload.security_tier === "LOCAL_ONLY";
                const inCloud = cloudIds.has(m.point_id);
                return (
                  <div key={m.point_id} className="bg-white border border-gray-200 rounded px-3 py-2 text-xs flex justify-between">
                    <span className="truncate mr-3">{m.payload.text}</span>
                    <span className="text-gray-400 whitespace-nowrap">
                      {isLocal ? "stays on device" : inCloud ? "in cloud" : "not yet synced"}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {tab === "conflicts" && (
          <div className="flex flex-col gap-3">
            {conflicts.length === 0 && <p className="text-sm text-gray-500">No active conflicts.</p>}
            {conflicts.map((r) => (
              <div key={r.id} className="bg-red-50 border border-red-200 rounded p-3">
                <p className="text-sm mb-1">Point {r.point_id}</p>
                <p className="text-xs text-red-700 mb-3">{r.error_message}</p>
                <div className="flex gap-2">
                  <button
                    onClick={() => resolve(Number(r.point_id), "edge")}
                    disabled={resolving !== null}
                    className="text-xs px-3 py-1.5 bg-white border border-gray-300 hover:bg-gray-50 rounded disabled:opacity-50"
                  >
                    Keep edge
                  </button>
                  <button
                    onClick={() => resolve(Number(r.point_id), "cloud")}
                    disabled={resolving !== null}
                    className="text-xs px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded disabled:opacity-50"
                  >
                    Keep cloud
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}