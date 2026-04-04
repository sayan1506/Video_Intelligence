# import asyncio
# import os
# from dotenv import load_dotenv

# load_dotenv()

# from pipeline.speech_to_text import transcribe

# # Replace with a real GCS URI from a video uploaded during Week 2
# # Format: gs://video-intelligence-raw/raw-videos/{jobId}/{filename}
# TEST_GCS_URI = "gs://video-intelligence-raw/raw-videos/5ad8cb9f-4503-4bb8-a02f-4b76c52506c4/test.mp4"

# # Get a real job ID from the GCS console or from a Week 2 upload response
# TEST_JOB_ID = "scratch-w3d1-stt"


# async def test_speech_to_text():
#     print(f"Testing Speech-to-Text pipeline...")
#     print(f"  GCS URI: {TEST_GCS_URI}")
#     print(f"  This will take 30–90 seconds for a typical video...")
#     print()

#     try:
#         words = await transcribe(TEST_GCS_URI, job_id=TEST_JOB_ID)

#         if not words:
#             print("  WARNING: No words returned — video may have no speech")
#             return

#         print(f"  Total words transcribed: {len(words)}")
#         print()
#         print("  First 10 words with timestamps:")
#         for w in words[:10]:
#             print(
#                 f"    [{w['startTime']:.2f}s → {w['endTime']:.2f}s] "
#                 f"speaker={w['speaker']} | '{w['word']}'"
#             )

#         # Verify speaker diarization worked
#         speakers = set(w["speaker"] for w in words)
#         print()
#         print(f"  Speakers detected: {sorted(speakers)}")

#         # Verify timestamps are ordered
#         for i in range(1, len(words)):
#             assert words[i]["startTime"] >= words[i-1]["startTime"], \
#                 f"Words out of order at index {i}"
#         print("  Timestamp ordering: PASS")

#         # Check raw output was written to GCS
#         print()
#         print(f"  Check GCS bucket for: processed/{TEST_JOB_ID}/transcript.json")
#         print("  (Open GCS console to verify the file exists)")

#     except Exception as e:
#         print(f"  FAILED: {e}")
#         print()
#         print("  Common causes:")
#         print("  - Wrong GCS URI (check bucket and job ID)")
#         print("  - Video has no audio track")
#         print("  - Speech-to-Text API not enabled")
#         print("  - Service account missing Speech-to-Text Editor role")
#         raise


# if __name__ == "__main__":
#     asyncio.run(test_speech_to_text())














import asyncio
import os
import time
from collections import Counter
from dotenv import load_dotenv
load_dotenv()

from pipeline.video_intelligence import (
    analyse_video,
    LABEL_CONFIDENCE_THRESHOLD,
    MAX_LABELS_PER_SCENE,
)

# Replace with a real job ID from a Week 2/3 upload
# The video must exist at gs://video-intelligence-raw/raw-videos/{jobId}/video.mp4
TEST_JOB_ID = "scratch-w3d2-videointel"
TEST_GCS_URI = f"gs://{os.getenv('GCP_BUCKET_NAME', 'video-intelligence-raw')}/raw-videos/5ad8cb9f-4503-4bb8-a02f-4b76c52506c4/test.mp4"

print("=" * 60)
print("Week 3 Day 2 — Video Intelligence pipeline test")
print("=" * 60)
print(f"URI:                 {TEST_GCS_URI}")
print(f"Confidence threshold: {LABEL_CONFIDENCE_THRESHOLD}")
print(f"Max labels/scene:    {MAX_LABELS_PER_SCENE}")
print()
print("Submitting to Video Intelligence API...")
print("Expected: 30–90 seconds for a 3-minute video")
print()

start = time.time()
scenes = asyncio.run(analyse_video(TEST_GCS_URI, job_id=TEST_JOB_ID))
elapsed = time.time() - start

print(f"Completed in {elapsed:.1f}s — {len(scenes)} scenes detected")
print()

# Print first 5 scenes
print("First 5 scenes:")
for i, scene in enumerate(scenes[:5], 1):
    labels_str = ", ".join(scene["labels"][:5]) or "(no labels above threshold)"
    print(f"  Scene {i}: {scene['startTime']:.2f}s – {scene['endTime']:.2f}s")
    print(f"    Labels: {labels_str}")
print()

# Assertions
print("Running assertions...")

assert len(scenes) > 0, "Expected at least 1 scene — got 0"
print(f"  Scene count > 0: PASS ({len(scenes)})")

assert all("startTime" in s and "endTime" in s and "labels" in s for s in scenes), \
    "All scenes must have startTime, endTime, labels"
print("  All scenes have required fields: PASS")

assert all(s["startTime"] < s["endTime"] for s in scenes), \
    "startTime must be < endTime"
print("  startTime < endTime: PASS")

if len(scenes) > 1:
    # Small float tolerance for rounding at shot boundaries
    assert all(
        scenes[i]["startTime"] >= scenes[i-1]["endTime"] - 0.05
        for i in range(1, len(scenes))
    ), "Scenes should not significantly overlap"
    print("  No scene overlap: PASS")

assert all(isinstance(lbl, str) for s in scenes for lbl in s["labels"]), \
    "All labels must be strings"
print("  Labels are strings: PASS")

# Check raw GCS output was written
from google.cloud import storage as gcs_lib
gcs_client = gcs_lib.Client()
bucket = gcs_client.bucket(os.getenv("GCP_BUCKET_NAME", "video-intelligence-raw"))
raw_blob = bucket.blob(f"processed/{TEST_JOB_ID}/video_intelligence.json")
assert raw_blob.exists(), "video_intelligence.json not found in GCS"
print("  Raw output in GCS: PASS")

print()
print("All assertions passed.")

# Label frequency
print()
print("Top 10 labels across all scenes:")
all_labels = [lbl for s in scenes for lbl in s["labels"]]
for label, count in Counter(all_labels).most_common(10):
    bar = "█" * min(count, 20)
    print(f"  {label:<30} {bar} ({count})")