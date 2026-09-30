# EdgeMind — Edge Memory Intelligent Platform

An offline-first AI memory system for a community health worker who visits
patients in areas with unreliable connectivity. Notes are captured and
searched by meaning entirely on-device, using the real **Qdrant Edge**
embedded library, with automatic, content-aware decisions about which notes
may ever leave the device.

Built for the "AI-Powered Edge Memory & Intelligence Platform" hackathon
problem statement (Qdrant Edge open-innovation track).

---

## The problem this solves

A health worker in the field needs to:
- keep working with **zero internet connectivity**
- **search past notes by meaning**, not exact keywords
- trust that **patient information never leaves the device** unless it is
  explicitly meant to
- have changes **synchronize automatically** once connectivity returns
- have **conflicting edits** (made by two people while both were offline)
  surfaced for a human to resolve, never silently overwritten

EdgeMind demonstrates all five of these end to end.

---

## Architecture

```
                         ┌─────────────────────┐
                         │   Next.js Dashboard  │
                         │   (EdgeMind UI)       │
                         └──────────┬───────────┘
                                    │ REST (localhost:8000)
                         ┌──────────▼───────────┐
                         │      FastAPI Core     │
                         └───┬─────────────┬─────┘
                             │             │
               ┌─────────────▼──┐   ┌──────▼────────────┐
               │ FastEmbed        │   │ Auto category +   │
               │ (bge-small-en)   │   │ tier classifier    │
               │ on-device model  │   │ (embedding-based)  │
               └─────────────┬──┘   └──────┬────────────┘
                             │             │
                      ┌──────▼─────────────▼──────┐
                      │   Qdrant Edge (EdgeShard)   │
                      │   embedded, in-process,     │
                      │   on-disk, no server         │
                      └──────────┬─────────────────┘
                                 │ mutation
                      ┌──────────▼─────────────────┐
                      │   SQLite sync log            │
                      │   (edge_sync_log table)      │
                      │   dirty_flag / version /     │
                      │   retry_count / error         │
                      └──────────┬─────────────────┘
                                 │ dirty records (tier-filtered)
                      ┌──────────▼─────────────────┐
                      │   Sync engine                 │
                      │   version compare → semantic  │
                      │   similarity tiebreak          │
                      └──────────┬─────────────────┘
                                 │ (only when ONLINE, tier permitting)
                      ┌──────────▼─────────────────┐
                      │   Qdrant Server / Cloud       │
                      │   (Docker, standard Qdrant)    │
                      └────────────────────────────┘
```

### Why two different Qdrant setups
The hackathon requires the real **Qdrant Edge** embedded library
(`qdrant-edge-py`, class `EdgeShard`) for local storage — not a Docker Qdrant
instance running on the device. A regular Qdrant server is exactly right for
the **Cloud** side, so EdgeMind runs both, each in the role it is designed
for:

| Tier | Technology | Why |
|---|---|---|
| Edge (this device) | `qdrant-edge-py` — `EdgeShard`, embedded in the FastAPI process, on-disk, no network | Matches the hackathon's Qdrant Edge requirement; genuinely offline |
| Cloud (server) | Standard `qdrant/qdrant` Docker image | Represents the centralized store notes sync up to |

---

## Data residency — the core idea

Every note is automatically classified into one of three tiers, without the
user picking anything:

| Tier | Meaning | Sync behavior |
|---|---|---|
| `LOCAL_ONLY` | Patient-identifiable information | **Never leaves the device.** Logged with `dirty_flag = 2` ("kept on device") and excluded from the sync queue entirely. |
| `HYBRID` | Clinic operations, general notes | Synced to Cloud when online, not treated as high priority. |
| `CLOUD_RESIDENT` | Aggregate public-health reporting | Synced to Cloud; intended to be centrally visible. |

Classification uses two layers, both fully offline:
1. **Category inference** — the note's text is embedded (same model used for
   search) and compared against example sentences for each category
   (`patient_visit`, `clinic_ops`, `public_health_report`, `general`). The
   closest category wins.
2. **Sensitivity safety net** — a deterministic check for clinical keywords
   (`patient`, `diagnos-`, `prescri-`, `symptom`, ...) and PII-shaped patterns
   (phone numbers, emails, ID-like digit sequences) that forces `LOCAL_ONLY`
   regardless of category, so a misclassification can't leak sensitive data.

This is enforced **twice**: once at write time (`LOCAL_ONLY` notes are never
queued for sync), and again inside the sync worker itself, which re-checks
the tier before ever pushing a record — so a single bug in one layer cannot
by itself leak data to the cloud.

---

## Semantic search

Text is embedded on-device with **FastEmbed** running
**`BAAI/bge-small-en-v1.5`** (384 dimensions, ONNX-based, no PyTorch, fully
offline after the first model download). Search compares the query's
embedding against stored vectors with cosine similarity — so "breathing
problems" correctly surfaces a note that says "difficulty breathing," despite
sharing no exact keywords.

Metadata filters (category, tier) are applied as a hard gate by Qdrant
**before** vector ranking — filtered-out records never enter the similarity
comparison. This is the "effective vector search filter implementation" the
hackathon judging criteria call out explicitly.

---

## Synchronization and conflicts

Every mutation (`INSERT` / `UPDATE`) is logged in a SQLite table
(`edge_sync_log`) alongside a version number. The sync engine:

1. Skips entirely while the app is offline (simulated via a network toggle,
   not a real connectivity check — necessary for a reliable live demo).
2. Fetches every record with `dirty_flag = 1` (pending) — records marked `2`
   (kept on device) are never touched.
3. For each record, compares the Edge version against Cloud's version for
   that same point:

   | Case | Resolution |
   |---|---|
   | Edge version newer | Push Edge → Cloud |
   | Cloud version newer | Pull Cloud → Edge |
   | Same version, similarity > 0.9 | Auto-resolve, Edge wins (content is near-identical) |
   | Same version, similarity ≤ 0.9 | **Flagged for manual review** — never auto-resolved |

The 0.9 threshold was calibrated against real data from this project's own
embedding model, not guessed: near-duplicate phrasing scored 0.944, and two
genuinely unrelated notes scored 0.472.

Manual conflicts are resolved from the dashboard with a "Keep edge" or "Keep
cloud" action, which updates both stores and clears the flag permanently.

**Known limitation:** cosine similarity indicates how much two versions'
*meaning* diverges, not which one is factually correct — it is a triage
signal for deciding what is safe to auto-resolve, not a correctness oracle.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python) |
| Edge vector store | `qdrant-edge-py` (`EdgeShard`) |
| Cloud vector store | Qdrant server (Docker) |
| Embeddings | FastEmbed, `BAAI/bge-small-en-v1.5` |
| Sync bookkeeping | SQLite |
| Frontend | Next.js (App Router), TypeScript, Tailwind CSS |

---

## Project structure

```
edge-memory-platform/
├── backend/
│   ├── app/
│   │   ├── main.py                  FastAPI routes
│   │   ├── models/memory.py         Request/response schemas
│   │   ├── services/
│   │   │   ├── qdrant_service.py    Edge (EdgeShard) + Cloud clients, conflict detection
│   │   │   ├── embedding_service.py FastEmbed wrapper
│   │   │   ├── categorization_service.py  Auto category inference
│   │   │   ├── tiering_service.py   LOCAL_ONLY / HYBRID / CLOUD_RESIDENT rules
│   │   │   ├── sync_worker.py       Sync engine + conflict resolution
│   │   │   ├── sync_log_service.py  SQLite sync log CRUD
│   │   │   └── network_state.py     Simulated online/offline toggle
│   │   └── utils/db.py              SQLite connection + schema
│   ├── requirements.txt
│   ├── seed_demo.py                 Seeds 12 realistic healthcare notes
│   └── data/                        SQLite file + Edge shard (gitignored)
├── frontend/
│   └── app/page.tsx                 Dashboard UI
├── docker-compose.yml               Cloud Qdrant only
└── README.md
```

---

## Running it locally

### 1. Start the Cloud Qdrant server
```bash
docker compose up -d
```

### 2. Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
First run downloads the FastEmbed model (~130MB) — needs internet once, then
works fully offline.

### 3. Seed realistic demo data (optional but recommended)
```bash
python seed_demo.py
```

### 4. Frontend
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000`.

### Resetting to a clean state
Useful before a rehearsal or recording:
```bash
# from the project root, backend stopped
Remove-Item -Recurse -Force data\qdrant_edge_shard
Remove-Item data\edge_sync.db
Invoke-RestMethod -Uri "http://localhost:6335/collections/memories" -Method Delete
```

---

## API reference

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Liveness check |
| `/memory` | POST | Create a note. Body: `{ text, category?, security_tier? }`. Category and tier are auto-inferred if omitted. |
| `/memory` | GET | List all notes on the Edge shard |
| `/memory/{id}` | PUT | Edit a note's text; bumps version, re-classifies |
| `/search` | POST | Semantic search. Body: `{ query, limit?, category?, security_tier? }` |
| `/sync/status` | GET | Pending / synced / kept-on-device / failed counts and full log |
| `/sync/run` | POST | Trigger a sync pass |
| `/sync/resolve` | POST | Resolve a flagged conflict. Body: `{ point_id, choice: "edge" \| "cloud" }` |
| `/cloud/memory` | GET | List notes present on the Cloud server |
| `/network/status` | GET | Current simulated online/offline state |
| `/network/toggle` | POST | `?online=true\|false` — flips the simulated network state |

---

## Demo script (12 steps)

1. Show the dashboard online, Edge and Cloud both reachable.
2. Add a patient note — confirm it's auto-tagged `LOCAL_ONLY`.
3. Add a public-health report — confirm `CLOUD_RESIDENT`.
4. Search "breathing problems" — the matching patient note ranks highest
   despite no shared keywords.
5. Go offline.
6. Add another note — still stored and searchable locally.
7. Run sync while offline — confirm it reports "skipped."
8. Go online.
9. Run sync — pending notes reach Cloud; **patient notes do not**.
10. Simulate or trigger a conflict (two edits to the same note) — confirm it's
    flagged, not silently overwritten.
11. Resolve the conflict from the dashboard.
12. Show the Edge-vs-Cloud comparison: patient notes exist only on the left.

---

## Honest trade-offs (for judges, or your own reference)

| Simplified for the hackathon | Production version would use |
|---|---|
| Second Qdrant "device" simulated via a network toggle | Real device connectivity detection |
| Fixed 0.9 similarity threshold | Threshold tuned per deployment, possibly per category |
| Sync triggered manually via a button | Background scheduler polling on an interval |
| Category/tier example sentences hand-written | Larger, curated or fine-tuned example set |
| A tier upgrade (e.g. HYBRID → LOCAL_ONLY on edit) doesn't retract an already-synced Cloud copy | Delete-on-Cloud when a tier is upgraded |