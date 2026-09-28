"use client";

import { useState, useEffect } from "react";
import Image from "next/image";

const API_BASE = "http://localhost:8000";

type Memory = {
  point_id: number;
  payload: {
    text: string;
    category: string;
    security_tier: string;
  };
};

type SearchResult = {
  point_id: number;
  score: number;
  payload: {
    text: string;
    category: string;
    security_tier: string;
  };
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

export default function Dashboard() {
  // --- System Status ---
  const [isOnline, setIsOnline] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);

  // --- Memory ---
  const [memories, setMemories] = useState<Memory[]>([]);
  const [newText, setNewText] = useState("");
  const [adding, setAdding] = useState(false);

  // --- Cloud view ---
  const [cloudMemories, setCloudMemories] = useState<Memory[]>([]);
  const [cloudReachable, setCloudReachable] = useState(true);

  // --- Search ---
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [filterCategory, setFilterCategory] = useState("");
  const [filterTier, setFilterTier] = useState("");

  // --- Sync ---
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [lastSyncResult, setLastSyncResult] = useState<string | null>(null);

  const fetchStatus = async () => {
    const res = await fetch(`${API_BASE}/network/status`);
    const data = await res.json();
    setIsOnline(data.is_online);
  };

  const fetchMemories = async () => {
    const res = await fetch(`${API_BASE}/memory`);
    const data = await res.json();
    setMemories(data.memories);
  };

  const fetchCloud = async () => {
    const res = await fetch(`${API_BASE}/cloud/memory`);
    const data = await res.json();
    setCloudMemories(data.memories);
    setCloudReachable(data.reachable);
  };

  const fetchSyncStatus = async () => {
    const res = await fetch(`${API_BASE}/sync/status`);
    const data = await res.json();
    setSyncStatus(data);
  };

  const toggleNetwork = async () => {
    setLoading(true);
    const newState = !isOnline;
    await fetch(`${API_BASE}/network/toggle?online=${newState}`, { method: "POST" });
    await fetchStatus();
    await fetchCloud();
    setLoading(false);
  };

  const addMemory = async () => {
    if (!newText.trim()) return;
    setAdding(true);
    await fetch(`${API_BASE}/memory`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: newText }),
    });
    setNewText("");
    await fetchMemories();
    await fetchSyncStatus();
    setAdding(false);
  };

  const runSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    const body: Record<string, unknown> = { query, limit: 5 };
    if (filterCategory) body.category = filterCategory;
    if (filterTier) body.security_tier = filterTier;
    const res = await fetch(`${API_BASE}/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    setResults(data.results);
    setSearching(false);
  };

  const runSync = async () => {
    setSyncing(true);
    setLastSyncResult(null);
    const res = await fetch(`${API_BASE}/sync/run`, { method: "POST" });
    const data = await res.json();
    if (data.status === "skipped") {
      setLastSyncResult(`Skipped — offline`);
    } else {
      setLastSyncResult(
        `Synced: ${data.synced}, Conflicts: ${data.conflicts ?? 0}, Failed: ${data.failed}`
      );
    }
    await fetchSyncStatus();
    await fetchMemories();
    await fetchCloud();
    setSyncing(false);
  };

  const resolveConflict = async (pointId: string, choice: "edge" | "cloud") => {
    await fetch(`${API_BASE}/sync/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ point_id: parseInt(pointId), choice }),
    });
    await fetchSyncStatus();
    await fetchMemories();
    await fetchCloud();
  };

  useEffect(() => {
    fetchStatus();
    fetchMemories();
    fetchCloud();
    fetchSyncStatus();
  }, []);

  const tierColor = (tier: string) => {
    if (tier === "LOCAL_ONLY") return "bg-red-900 text-red-300";
    if (tier === "CLOUD_RESIDENT") return "bg-blue-900 text-blue-300";
    return "bg-yellow-900 text-yellow-300"; // HYBRID
  };

  const cloudIds = new Set(cloudMemories.map((c) => c.point_id));

  return (
    <main className="min-h-screen bg-gray-950 text-white p-8 space-y-6">
      {/* Header / Branding */}
      <div className="flex items-center gap-4 mb-2">
        <Image src="/logo.png" alt="EdgeMind logo" width={48} height={48} />
        <div>
          <h1 className="text-2xl font-bold">EdgeMind</h1>
          <p className="text-sm text-gray-400">Edge Memory Intelligent Platform</p>
        </div>
      </div>

      {/* System Status */}
      <div className="bg-gray-900 rounded-lg p-6 max-w-2xl">
        <h2 className="text-lg font-semibold mb-4">System Status</h2>
        {isOnline === null ? (
          <p className="text-gray-400">Loading...</p>
        ) : (
          <div className="flex items-center gap-3">
            <span className={`w-3 h-3 rounded-full ${isOnline ? "bg-green-500" : "bg-red-500"}`} />
            <span className="text-lg">{isOnline ? "ONLINE" : "OFFLINE"}</span>
          </div>
        )}
        <button
          onClick={toggleNetwork}
          disabled={loading}
          className="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded disabled:opacity-50"
        >
          {loading ? "Toggling..." : isOnline ? "Go Offline" : "Go Online"}
        </button>
      </div>

      {/* Memory */}
      <div className="bg-gray-900 rounded-lg p-6 max-w-2xl">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold">Memory ({memories.length})</h2>
          <button
            onClick={fetchMemories}
            className="text-sm px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded"
          >
            Refresh
          </button>
        </div>

        <div className="flex gap-2 mb-4">
          <input
            type="text"
            value={newText}
            onChange={(e) => setNewText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addMemory()}
            placeholder="New memory text..."
            className="flex-1 bg-gray-800 rounded px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-600"
          />
          <button
            onClick={addMemory}
            disabled={adding}
            className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded disabled:opacity-50"
          >
            {adding ? "Adding..." : "Add"}
          </button>
        </div>

        <div className="space-y-2 max-h-96 overflow-y-auto">
          {memories.map((m) => (
            <div key={m.point_id} className="bg-gray-800 rounded p-3">
              <p className="text-sm">{m.payload.text}</p>
              <div className="flex gap-2 mt-2">
                <span className="text-xs px-2 py-0.5 bg-gray-700 rounded">{m.payload.category}</span>
                <span className={`text-xs px-2 py-0.5 rounded ${tierColor(m.payload.security_tier)}`}>
                  {m.payload.security_tier}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Search */}
      <div className="bg-gray-900 rounded-lg p-6 max-w-2xl">
        <h2 className="text-lg font-semibold mb-4">Search</h2>
        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && runSearch()}
            placeholder="e.g. breathing problems"
            className="flex-1 bg-gray-800 rounded px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-600"
          />
          <button
            onClick={runSearch}
            disabled={searching}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded disabled:opacity-50"
          >
            {searching ? "Searching..." : "Search"}
          </button>
        </div>

        <div className="flex gap-2 mt-3">
          <select
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value)}
            className="bg-gray-800 rounded px-2 py-1 text-xs"
          >
            <option value="">Any category</option>
            <option value="patient_visit">patient_visit</option>
            <option value="clinic_ops">clinic_ops</option>
            <option value="public_health_report">public_health_report</option>
            <option value="general">general</option>
          </select>
          <select
            value={filterTier}
            onChange={(e) => setFilterTier(e.target.value)}
            className="bg-gray-800 rounded px-2 py-1 text-xs"
          >
            <option value="">Any tier</option>
            <option value="LOCAL_ONLY">LOCAL_ONLY</option>
            <option value="HYBRID">HYBRID</option>
            <option value="CLOUD_RESIDENT">CLOUD_RESIDENT</option>
          </select>
        </div>

        <div className="space-y-2 mt-4">
          {results.map((r) => (
            <div key={r.point_id} className="bg-gray-800 rounded p-3">
              <div className="flex justify-between items-start">
                <p className="text-sm">{r.payload.text}</p>
                <span className="text-xs text-green-400 ml-3 whitespace-nowrap">
                  {(r.score * 100).toFixed(1)}%
                </span>
              </div>
              <div className="flex gap-2 mt-2">
                <span className="text-xs px-2 py-0.5 bg-gray-700 rounded">{r.payload.category}</span>
                <span className={`text-xs px-2 py-0.5 rounded ${tierColor(r.payload.security_tier)}`}>
                  {r.payload.security_tier}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Sync */}
      <div className="bg-gray-900 rounded-lg p-6 max-w-2xl">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold">Synchronization</h2>
          <button
            onClick={fetchSyncStatus}
            className="text-sm px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded"
          >
            Refresh
          </button>
        </div>

        {syncStatus && (
          <div className="grid grid-cols-4 gap-3 mb-4">
            <div className="bg-gray-800 rounded p-3 text-center">
              <p className="text-2xl font-bold text-yellow-400">{syncStatus.pending_count}</p>
              <p className="text-xs text-gray-400">Pending</p>
            </div>
            <div className="bg-gray-800 rounded p-3 text-center">
              <p className="text-2xl font-bold text-green-400">{syncStatus.synced_count}</p>
              <p className="text-xs text-gray-400">Synced</p>
            </div>
            <div className="bg-gray-800 rounded p-3 text-center">
              <p className="text-2xl font-bold text-red-300">{syncStatus.local_only_count}</p>
              <p className="text-xs text-gray-400">Kept on device</p>
            </div>
            <div className="bg-gray-800 rounded p-3 text-center">
              <p className="text-2xl font-bold text-red-400">{syncStatus.failed_count}</p>
              <p className="text-xs text-gray-400">Failed</p>
            </div>
          </div>
        )}

        <button
          onClick={runSync}
          disabled={syncing}
          className="w-full px-4 py-2 bg-green-600 hover:bg-green-700 rounded disabled:opacity-50 mb-3"
        >
          {syncing ? "Syncing..." : "Run Sync"}
        </button>

        {lastSyncResult && (
          <p className="text-sm text-gray-300 mb-3">{lastSyncResult}</p>
        )}

        <div className="space-y-1 max-h-48 overflow-y-auto">
          {syncStatus?.records
            .filter((r) => r.dirty_flag === 1)
            .map((r) => (
              <div key={r.id} className="bg-gray-800 rounded p-2 text-xs">
                <span className="text-gray-400">Point {r.point_id}</span>
                {r.error_message && (
                  <p className="text-red-400 mt-1">{r.error_message}</p>
                )}
              </div>
            ))}
        </div>
      </div>

      {/* Edge vs Cloud */}
      <div className="bg-gray-900 rounded-lg p-6 max-w-4xl">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold">Edge vs Cloud</h2>
          <button
            onClick={() => {
              fetchMemories();
              fetchCloud();
            }}
            className="text-sm px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded"
          >
            Refresh
          </button>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm text-gray-400 mb-2">Edge (this device) — {memories.length}</p>
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {memories.map((m) => {
                const inCloud = cloudIds.has(m.point_id);
                const isLocal = m.payload.security_tier === "LOCAL_ONLY";
                return (
                  <div key={m.point_id} className="bg-gray-800 rounded p-2">
                    <p className="text-xs">{m.payload.text}</p>
                    <div className="flex gap-2 mt-1">
                      <span className={`text-xs px-2 py-0.5 rounded ${tierColor(m.payload.security_tier)}`}>
                        {m.payload.security_tier}
                      </span>
                      <span className="text-xs text-gray-400">
                        {isLocal ? "🔒 stays on device" : inCloud ? "☁️ in cloud" : "⏳ not yet synced"}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div>
            <p className="text-sm text-gray-400 mb-2">
              Cloud (server) — {cloudReachable ? cloudMemories.length : "unreachable"}
            </p>
            {!cloudReachable ? (
              <p className="text-xs text-red-400">Cloud unreachable — working offline.</p>
            ) : (
              <div className="space-y-2 max-h-80 overflow-y-auto">
                {cloudMemories.map((m) => (
                  <div key={m.point_id} className="bg-gray-800 rounded p-2">
                    <p className="text-xs">{m.payload.text}</p>
                    <span className={`inline-block mt-1 text-xs px-2 py-0.5 rounded ${tierColor(m.payload.security_tier)}`}>
                      {m.payload.security_tier}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Conflicts */}
      <div className="bg-gray-900 rounded-lg p-6 max-w-2xl">
        <h2 className="text-lg font-semibold mb-4">Conflicts</h2>
        <div className="space-y-2">
          {syncStatus?.records
            .filter((r) => r.error_message?.includes("CONFLICT"))
            .map((r) => (
              <div key={r.id} className="bg-red-950 border border-red-800 rounded p-3">
                <p className="text-sm text-red-300">Point {r.point_id}</p>
                <p className="text-xs text-red-400 mt-1">{r.error_message}</p>
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={() => resolveConflict(r.point_id, "edge")}
                    className="text-xs px-2 py-1 bg-blue-700 hover:bg-blue-600 rounded"
                  >
                    Keep Edge
                  </button>
                  <button
                    onClick={() => resolveConflict(r.point_id, "cloud")}
                    className="text-xs px-2 py-1 bg-purple-700 hover:bg-purple-600 rounded"
                  >
                    Keep Cloud
                  </button>
                </div>
              </div>
            ))}
          {syncStatus?.records.filter((r) => r.error_message?.includes("CONFLICT")).length === 0 && (
            <p className="text-sm text-gray-500">No active conflicts.</p>
          )}
        </div>
      </div>

      {/* Activity Timeline */}
      <div className="bg-gray-900 rounded-lg p-6 max-w-2xl">
        <h2 className="text-lg font-semibold mb-4">Activity Timeline</h2>
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {syncStatus?.records
            .slice()
            .sort((a, b) => (a.id < b.id ? 1 : -1))
            .map((r) => (
              <div key={r.id} className="text-xs text-gray-400 border-l-2 border-gray-700 pl-3 py-1">
                <span className="text-gray-200">
                  {r.mutation_type} — Point {r.point_id}
                </span>
                <span className="ml-2">
                  {r.dirty_flag === 0
                    ? "✅ synced"
                    : r.dirty_flag === 2
                    ? "🔒 kept on device"
                    : r.error_message?.includes("CONFLICT")
                    ? "⚠️ conflict"
                    : "⏳ pending"}
                </span>
              </div>
            ))}
        </div>
      </div>
    </main>
  );
}