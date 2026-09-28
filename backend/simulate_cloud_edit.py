import sys
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from app.services.embedding_service import embed

cloud = QdrantClient(host="localhost", port=6335)

point_id = int(sys.argv[1])
version = int(sys.argv[2])
text = sys.argv[3]

existing = cloud.retrieve(collection_name="memories", ids=[point_id], with_payload=True)[0]

cloud.upsert(
    collection_name="memories",
    points=[PointStruct(
        id=point_id,
        vector=embed(text),  # genuinely re-embedded, so similarity scores are real
        payload={**existing.payload, "text": text, "version": version},
    )],
)
print(f"Cloud point {point_id} now version={version}: '{text}'")