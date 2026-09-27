from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from fastembed import TextEmbedding
import sys

cloud_client = QdrantClient(host="localhost", port=6335)
edge_client = QdrantClient(host="localhost", port=6333)
model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

point_id = int(sys.argv[1])
new_version = int(sys.argv[2])
new_text = sys.argv[3] if len(sys.argv) > 3 else "CLOUD-SIDE EDIT (simulated)"

existing = edge_client.retrieve(collection_name="memories", ids=[point_id], with_vectors=True)[0]

new_vector = list(model.embed([new_text]))[0].tolist()

cloud_client.upsert(
    collection_name="memories",
    points=[PointStruct(
        id=point_id,
        vector=new_vector,   # now genuinely re-embedded from the new text
        payload={**existing.payload, "text": new_text, "version": new_version},
    )],
)
print(f"Point {point_id} pushed to Cloud with version={new_version}, text='{new_text}'")