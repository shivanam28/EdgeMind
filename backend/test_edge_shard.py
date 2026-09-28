from pathlib import Path
from qdrant_edge import Distance, EdgeConfig, EdgeShard, EdgeVectorParams, Point, UpdateOperation

SHARD_DIR = "./data/qdrant_edge_shard"
VECTOR_NAME = "embedding"
VECTOR_DIM = 384

Path(SHARD_DIR).mkdir(parents=True, exist_ok=True)

config = EdgeConfig(
    vectors={
        VECTOR_NAME: EdgeVectorParams(size=VECTOR_DIM, distance=Distance.Cosine)
    }
)

# Create if new, otherwise this script is only meant to run once for the test
shard = EdgeShard.create(SHARD_DIR, config)

# Insert a test point (fake small vector padded to 384 dims for this test)
test_vector = [0.1] * VECTOR_DIM
point = Point(id=1, vector={VECTOR_NAME: test_vector}, payload={"text": "test memory"})
shard.update(UpdateOperation.upsert_points([point]))

# Retrieve it back
records = shard.retrieve(point_ids=[1], with_payload=True, with_vector=True)
print("Retrieved:", records)

shard.close()
print("Shard closed and persisted to disk.")