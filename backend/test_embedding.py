from app.services.embedding_service import embed

vec = embed("machine overheating in bay 3")
print("Vector length:", len(vec))
print("First 5 values:", vec[:5])