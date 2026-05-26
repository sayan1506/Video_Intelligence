"""Quick diagnostic: check if embeddings exist and vector search works."""
import os
os.environ.setdefault("GCP_PROJECT_ID", "video-intelligence-v1")

from google.cloud import firestore
from google.cloud.firestore_v1.vector import Vector
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure

db = firestore.Client(project="video-intelligence-v1")

JOB_ID = "68b1b535-9ca7-4d1b-82e7-340eafb032e3"

# Fix: re-write embeddings as Vector type
print("--- Re-writing embeddings as Vector type ---")
result_doc = db.collection("results").document(JOB_ID).get()
chunk_count = result_doc.to_dict().get("transcriptChunkCount", 0)
print(f"Job has {chunk_count} chunks")

for i in range(chunk_count):
    doc = db.collection("results").document(JOB_ID).collection("transcript_chunks").document(str(i)).get()
    if doc.exists:
        data = doc.to_dict()
        embedding = data.get("embedding")
        if embedding and isinstance(embedding, list):
            # Re-write as Vector type
            db.collection("results").document(JOB_ID).collection("transcript_chunks").document(str(i)).set(
                {"embedding": Vector(embedding)}, merge=True
            )
            print(f"  ✅ Chunk {i}: re-written as Vector ({len(embedding)} dims)")
        else:
            print(f"  ⚠️ Chunk {i}: no embedding or already Vector")

# Now try vector search again
print("\n--- Attempting vector search after fix ---")
collection = db.collection("results").document(JOB_ID).collection("transcript_chunks")
query_vector = [0.01] * 768

try:
    results = collection.find_nearest(
        vector_field="embedding",
        query_vector=Vector(query_vector),
        distance_measure=DistanceMeasure.COSINE,
        limit=4,
    )
    docs = list(results.stream())
    print(f"✅ Vector search returned {len(docs)} results")
    for d in docs:
        data = d.to_dict()
        words = data.get("words", [])
        snippet = " ".join(w["word"] for w in words[:10])
        print(f"   Chunk {data.get('chunkIndex')}: '{snippet}...'")
except Exception as e:
    print(f"❌ Vector search failed: {e}")
