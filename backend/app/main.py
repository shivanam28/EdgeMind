import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.models.memory import MemoryCreate, SearchQuery
from app.utils.db import init_db
from app.services.qdrant_service import (
    ensure_collection,
    ensure_cloud_collection,
    insert_point,
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

    tier = memory.security_tier if memory.security_tier is not None else classify_data(memory.text, memory.category)

    payload = {
        "text": memory.text,
        "category": memory.category,
        "security_tier": tier,
    }
    vector = insert_point(point_id, memory.text, payload, version=1)
    log_mutation(point_id=str(point_id), mutation_type="INSERT", payload=payload, vector=vector)
    return {"point_id": point_id, "status": "stored", "payload": payload}


@app.get("/memory")
def list_memory():
    return {"memories": list_all_points()}


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