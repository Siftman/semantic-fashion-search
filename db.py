from qdrant_client import QdrantClient, models

qdrant_port = 6333
qdrant_url = "http://localhost"
client = QdrantClient(qdrant_url, port=qdrant_port, timeout=100.0)

client.create_collection(
    collection_name="your_company_name",
    vectors_config=models.VectorParams(size=512, distance=models.Distance.COSINE),
)