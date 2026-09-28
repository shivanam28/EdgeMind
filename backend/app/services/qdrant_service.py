from pathlib import Path
from types import SimpleNamespace

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance as CloudDistance, PointStruct

from qdrant_edge import (
    Distance,
    EdgeConfig,
    EdgeShard,
    EdgeVectorParams,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    Point,
    Query,
    QueryRequest,
    ScrollRequest,
    UpdateOperation,
)

from app.services.embedding_service import embed

COLLECTION_NAME = "memories"   # Cloud (server) collection name
VECTOR_SIZE = 384              # bge-small-en-v1.5
VECTOR_NAME = "embedding"      # named vector inside the Edge shard
SHARD_DIR = Path(__file__).resolve().parents[3] / "data" / "qdrant_edge_shard"

# CLOUD tier: a real Qdrant server (Docker). Edge tier is the embedded EdgeShard below.
cloud_client = QdrantClient(host="localhost", port=6335)

_shard = None


# ---------------------------------------------------------------- EDGE (embedded)

def get_shard() -> EdgeShard:
    """Open the embedded Qdrant Edge shard once per process (create if new, load if existing)."""
    global _shard
    if _shard is None:
        SHARD_DIR.mkdir(parents=True, exist_ok=True)
        if any(SHARD_DIR.iterdir()):
            _shard = EdgeShard.load(str(SHARD_DIR))
        else:
            config = EdgeConfig(
                vectors={VECTOR_NAME: EdgeVectorParams(size=VECTOR_SIZE, distance=Distance.Cosine)}
            )
            _shard = EdgeShard.create(str(SHARD_DIR), config)
    return _shard


def ensure_collection():
    """Init the Edge shard and create payload indexes used for filtered search."""
    shard = get_shard()
    for field in ("category", "security_tier"):
        try:
            shard.update(UpdateOperation.create_field_index(field, PayloadSchemaType.Keyword))
        except Exception:
            pass  # index already exists


def _to_simple(record):
    """Adapter: Edge returns named vectors as a dict; the rest of the app expects a plain list."""
    vec = record.vector
    if isinstance(vec, dict):
        vec = vec.get(VECTOR_NAME)
    return SimpleNamespace(id=record.id, vector=vec, payload=record.payload)


def insert_point(point_id: int, text: str, payload: dict, version: int = 1) -> list[float]:
    vector = embed(text)
    full_payload = {**payload, "version": version}
    shard = get_shard()
    shard.update(
        UpdateOperation.upsert_points(
            [Point(id=point_id, vector={VECTOR_NAME: vector}, payload=full_payload)]
        )
    )
    try:
        shard.flush()
    except Exception:
        pass
    return vector


def get_point_from_edge(point_id):
    try:
        records = get_shard().retrieve(point_ids=[point_id], with_payload=True, with_vector=True)
        return _to_simple(records[0]) if records else None
    except Exception as e:
        print(f"DEBUG get_point_from_edge({point_id}) failed: {e}")
        return None


def pull_point_to_edge(point_id, vector, payload):
    shard = get_shard()
    shard.update(
        UpdateOperation.upsert_points(
            [Point(id=point_id, vector={VECTOR_NAME: list(vector)}, payload=payload)]
        )
    )
    try:
        shard.flush()
    except Exception:
        pass


def search_points(query_text: str, limit: int = 5, category: str = None, security_tier: str = None):
    query_vector = embed(query_text)

    conditions = []
    if category:
        conditions.append(FieldCondition(key="category", match=MatchValue(value=category)))
    if security_tier:
        conditions.append(FieldCondition(key="security_tier", match=MatchValue(value=security_tier)))

    request_args = dict(
        query=Query.Nearest(query_vector, using=VECTOR_NAME),
        limit=limit,
        with_vector=False,
        with_payload=True,
    )
    if conditions:
        request_args["filter"] = Filter(must=conditions)

    results = get_shard().query(QueryRequest(**request_args))
    return [{"point_id": r.id, "score": r.score, "payload": r.payload} for r in results]


def list_all_points(limit: int = 100):
    records, _next_offset = get_shard().scroll(
        ScrollRequest(limit=limit, with_payload=True, with_vector=False)
    )
    return [{"point_id": r.id, "payload": r.payload} for r in records]


# ---------------------------------------------------------------- CLOUD (server)

def ensure_cloud_collection():
    collections = [c.name for c in cloud_client.get_collections().collections]
    if COLLECTION_NAME not in collections:
        cloud_client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=CloudDistance.COSINE),
        )


def push_point_to_cloud(point_id, vector, payload):
    cloud_client.upsert(
        collection_name=COLLECTION_NAME,
        points=[PointStruct(id=point_id, vector=list(vector), payload=payload)],
    )


def get_cloud_point(point_id):
    try:
        points = cloud_client.retrieve(
            collection_name=COLLECTION_NAME, ids=[point_id], with_vectors=True
        )
        return points[0] if points else None
    except Exception:
        return None

def list_cloud_points(limit: int = 100):
    points, _ = cloud_client.scroll(
        collection_name=COLLECTION_NAME, limit=limit, with_payload=True, with_vectors=False
    )
    return [{"point_id": p.id, "payload": p.payload} for p in points]


# ---------------------------------------------------------------- CONFLICTS

def cosine_similarity(vec_a, vec_b) -> float:
    a = np.array(vec_a)
    b = np.array(vec_b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def detect_conflict(point_id, edge_version, edge_vector):
    cloud_point = get_cloud_point(point_id)
    if cloud_point is None:
        return None

    cloud_version = cloud_point.payload.get("version", 1)

    if edge_version > cloud_version:
        return {"type": "EDGE_NEWER", "cloud_version": cloud_version}
    elif cloud_version > edge_version:
        return {"type": "CLOUD_NEWER", "cloud_version": cloud_version, "cloud_point": cloud_point}
    else:
        
        similarity = cosine_similarity(edge_vector, cloud_point.vector)
        if similarity > 0.9999:
            return None  # identical content, nothing to resolve
        return {
            "type": "SAME_VERSION_DIFFERENT_CONTENT",
            "cloud_version": cloud_version,
            "similarity": similarity,
            "cloud_point": cloud_point,
        }