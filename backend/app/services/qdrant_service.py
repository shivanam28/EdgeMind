from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct, Filter, FieldCondition, MatchValue
from app.services.embedding_service import embed
import numpy as np

client = QdrantClient(host="localhost", port=6333)
cloud_client = QdrantClient(host="localhost", port=6335)

COLLECTION_NAME = "memories"
VECTOR_SIZE = 384  # matches bge-small-en-v1.5 output


def ensure_collection():
    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in collections:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


def ensure_cloud_collection():
    collections = [c.name for c in cloud_client.get_collections().collections]
    if COLLECTION_NAME not in collections:
        cloud_client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


def insert_point(point_id: int, text: str, payload: dict) -> list[float]:
    vector = embed(text)
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[PointStruct(id=point_id, vector=vector, payload=payload)],
    )
    return vector


def search_points(query_text: str, limit: int = 5, category: str = None, security_tier: str = None):
    query_vector = embed(query_text)

    conditions = []
    if category:
        conditions.append(FieldCondition(key="category", match=MatchValue(value=category)))
    if security_tier:
        conditions.append(FieldCondition(key="security_tier", match=MatchValue(value=security_tier)))

    query_filter = Filter(must=conditions) if conditions else None

    results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        query_filter=query_filter,
        limit=limit,
    )
    return [
        {"point_id": r.id, "score": r.score, "payload": r.payload}
        for r in results
    ]

def get_point_from_edge(point_id):
    try:
        points = client.retrieve(
            collection_name=COLLECTION_NAME,
            ids=[point_id],
            with_vectors=True,   # critical: vectors excluded by default
        )
        return points[0] if points else None
    except Exception:
        return None

def push_point_to_cloud(point_id, vector, payload):
    cloud_client.upsert(
        collection_name=COLLECTION_NAME,
        points=[PointStruct(id=point_id, vector=vector, payload=payload)],
    )

def get_cloud_point(point_id):
    try:
        points = cloud_client.retrieve(collection_name=COLLECTION_NAME, ids=[point_id], with_vectors=True)
        return points[0] if points else None
    except Exception:
        return None

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
        return {
            "type": "SAME_VERSION_DIFFERENT_CONTENT",
            "cloud_version": cloud_version,
            "similarity": similarity,
            "cloud_point": cloud_point,
        }

def insert_point(point_id: int, text: str, payload: dict, version: int = 1) -> list[float]:
    vector = embed(text)
    full_payload = {**payload, "version": version}
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[PointStruct(id=point_id, vector=vector, payload=full_payload)],
    )
    return vector

def pull_point_to_edge(point_id, vector, payload):
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[PointStruct(id=point_id, vector=vector, payload=payload)],
    )

def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    a = np.array(vec_a)
    b = np.array(vec_b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

def list_all_points(limit: int = 100):
    results = client.scroll(collection_name=COLLECTION_NAME, limit=limit, with_payload=True, with_vectors=False)
    points = results[0]  # scroll returns (points, next_page_offset)
    return [{"point_id": p.id, "payload": p.payload} for p in points]