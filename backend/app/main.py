import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException

from app.models.memory import MemoryCreate, SearchQuery
from app.utils.db import init_db
from app.services.qdrant_service import (
    ensure_collection,
    ensure_cloud_collection,
    insert_point,
    list_cloud_points,
    search_points,
    list_all_points,
    get_point_from_edge,
    get_cloud_point,
    push_point_to_cloud,
    pull_point_to_edge,
)
from app.services.sync_log_service import log_mutation, get_sync_status, get_connection
from app.services.sync_worker import run_sync
from app.services.tiering_service import classify_data
from app.services.network_state import set_online, is_online
from app.services.categorization_service import auto_categorize

app = FastAPI(title="Edge Memory Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)




@app.on_event("startup")
def startup():
    init_db()
    ensure_collection()
    ensure_cloud_collection()


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "edge-memory-backend"}


# ---------- Memory ----------

@app.post("/memory")
def create_memory(memory: MemoryCreate):
    point_id = int(time.time() * 1000)

    category = memory.category if memory.category is not None else auto_categorize(memory.text)
    tier = memory.security_tier if memory.security_tier is not None else classify_data(memory.text, category)

    payload = {
        "text": memory.text,
        "category": category,
        "security_tier": tier,
    }
    vector = insert_point(point_id, memory.text, payload, version=1)
    log_mutation(point_id=str(point_id), mutation_type="INSERT", payload=payload, vector=vector,
             dirty_flag=2 if tier == "LOCAL_ONLY" else 1)
    return {"point_id": point_id, "status": "stored", "payload": payload}

@app.get("/memory")
def list_memory():
    return {"memories": list_all_points()}

@app.get("/cloud/memory")
def list_cloud_memory():
    # While the network is simulated offline, the cloud is unreachable, as it would be for real
    if not is_online():
        return {"memories": [], "reachable": False}
    try:
        return {"memories": list_cloud_points(), "reachable": True}
    except Exception:
        return {"memories": [], "reachable": False}

# ---------- Search ----------

@app.post("/search")
def search_memory(search: SearchQuery):
    results = search_points(search.query, search.limit, search.category, search.security_tier)
    return {"query": search.query, "results": results}


# ---------- Sync ----------

@app.get("/sync/status")
def sync_status():
    return get_sync_status()


@app.post("/sync/run")
def trigger_sync():
    return run_sync()


class ConflictResolution(BaseModel):
    point_id: int
    choice: str  # "edge" or "cloud"


@app.post("/sync/resolve")
def resolve_conflict(resolution: ConflictResolution):
    if resolution.choice == "edge":
        point = get_point_from_edge(resolution.point_id)
        push_point_to_cloud(resolution.point_id, point.vector, point.payload)
    elif resolution.choice == "cloud":
        cloud_point = get_cloud_point(resolution.point_id)
        pull_point_to_edge(resolution.point_id, cloud_point.vector, cloud_point.payload)
    else:
        return {"error": "choice must be 'edge' or 'cloud'"}

    conn = get_connection()
    conn.execute(
        "UPDATE edge_sync_log SET dirty_flag = 0, error_message = NULL WHERE point_id = ?",
        (str(resolution.point_id),),
    )
    conn.commit()
    conn.close()
    return {"status": "resolved", "choice": resolution.choice}


# ---------- Network simulation ----------

@app.post("/network/toggle")
def toggle_network(online: bool):
    set_online(online)
    return {"is_online": is_online()}


@app.get("/network/status")
def network_status():
    return {"is_online": is_online()}

class MemoryUpdate(BaseModel):
    text: str


@app.put("/memory/{point_id}")
def update_memory(point_id: int, update: MemoryUpdate):
    existing = get_point_from_edge(point_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Memory not found")

    new_version = existing.payload.get("version", 1) + 1
    category = auto_categorize(update.text)
    tier = classify_data(update.text, category)

    payload = {**existing.payload, "text": update.text, "category": category, "security_tier": tier}
    vector = insert_point(point_id, update.text, payload, version=new_version)
    log_mutation(point_id=str(point_id), mutation_type="UPDATE", payload=payload, vector=vector,
             version=new_version, dirty_flag=2 if tier == "LOCAL_ONLY" else 1)
    return {"point_id": point_id, "status": "updated", "version": new_version,
            "category": category, "security_tier": tier}