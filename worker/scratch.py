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














# import asyncio
# import os
# import time
# from collections import Counter
# from dotenv import load_dotenv
# load_dotenv()

# from pipeline.video_intelligence import (
#     analyse_video,
#     LABEL_CONFIDENCE_THRESHOLD,
#     MAX_LABELS_PER_SCENE,
# )

# # Replace with a real job ID from a Week 2/3 upload
# # The video must exist at gs://video-intelligence-raw/raw-videos/{jobId}/video.mp4
# TEST_JOB_ID = "scratch-w3d2-videointel"
# TEST_GCS_URI = f"gs://{os.getenv('GCP_BUCKET_NAME', 'video-intelligence-raw')}/raw-videos/5ad8cb9f-4503-4bb8-a02f-4b76c52506c4/test.mp4"

# print("=" * 60)
# print("Week 3 Day 2 — Video Intelligence pipeline test")
# print("=" * 60)
# print(f"URI:                 {TEST_GCS_URI}")
# print(f"Confidence threshold: {LABEL_CONFIDENCE_THRESHOLD}")
# print(f"Max labels/scene:    {MAX_LABELS_PER_SCENE}")
# print()
# print("Submitting to Video Intelligence API...")
# print("Expected: 30–90 seconds for a 3-minute video")
# print()

# start = time.time()
# scenes = asyncio.run(analyse_video(TEST_GCS_URI, job_id=TEST_JOB_ID))
# elapsed = time.time() - start

# print(f"Completed in {elapsed:.1f}s — {len(scenes)} scenes detected")
# print()

# # Print first 5 scenes
# print("First 5 scenes:")
# for i, scene in enumerate(scenes[:5], 1):
#     labels_str = ", ".join(scene["labels"][:5]) or "(no labels above threshold)"
#     print(f"  Scene {i}: {scene['startTime']:.2f}s – {scene['endTime']:.2f}s")
#     print(f"    Labels: {labels_str}")
# print()

# # Assertions
# print("Running assertions...")

# assert len(scenes) > 0, "Expected at least 1 scene — got 0"
# print(f"  Scene count > 0: PASS ({len(scenes)})")

# assert all("startTime" in s and "endTime" in s and "labels" in s for s in scenes), \
#     "All scenes must have startTime, endTime, labels"
# print("  All scenes have required fields: PASS")

# assert all(s["startTime"] < s["endTime"] for s in scenes), \
#     "startTime must be < endTime"
# print("  startTime < endTime: PASS")

# if len(scenes) > 1:
#     # Small float tolerance for rounding at shot boundaries
#     assert all(
#         scenes[i]["startTime"] >= scenes[i-1]["endTime"] - 0.05
#         for i in range(1, len(scenes))
#     ), "Scenes should not significantly overlap"
#     print("  No scene overlap: PASS")

# assert all(isinstance(lbl, str) for s in scenes for lbl in s["labels"]), \
#     "All labels must be strings"
# print("  Labels are strings: PASS")

# # Check raw GCS output was written
# from google.cloud import storage as gcs_lib
# gcs_client = gcs_lib.Client()
# bucket = gcs_client.bucket(os.getenv("GCP_BUCKET_NAME", "video-intelligence-raw"))
# raw_blob = bucket.blob(f"processed/{TEST_JOB_ID}/video_intelligence.json")
# assert raw_blob.exists(), "video_intelligence.json not found in GCS"
# print("  Raw output in GCS: PASS")

# print()
# print("All assertions passed.")

# # Label frequency
# print()
# print("Top 10 labels across all scenes:")
# all_labels = [lbl for s in scenes for lbl in s["labels"]]
# for label, count in Counter(all_labels).most_common(10):
#     bar = "█" * min(count, 20)
#     print(f"  {label:<30} {bar} ({count})")














# worker/scratch.py — Week 3 Day 5 failure test (corrected)

# worker/scratch.py — Week 3 Day 5 failure test

# import asyncio
# from dotenv import load_dotenv
# load_dotenv()

# from pipeline.orchestrator import run_pipeline
# from models.schemas import JobMessage
# from services.firestore import get_db

# print("Testing failed pipeline (bad GCS URI)...")

# JOB_ID = "scratch-w3d5-failure-test"

# db = get_db()
# db.collection("jobs").document(JOB_ID).set({
#     "jobId": JOB_ID,
#     "status": "queued",
#     "progress": 0,
#     "filename": "nonexistent.mp4",
#     "createdAt": None,
# })
# print(f"Job document seeded: {JOB_ID}")

# bad_message = JobMessage(
#     jobId=JOB_ID,
#     gcsPath="raw-videos/nonexistent/video.mp4",
#     gcsBucket="video-intelligence-raw",
#     gcsUri="gs://video-intelligence-raw/raw-videos/nonexistent/video.mp4",
#     filename="nonexistent.mp4",
#     fileSizeMb=0.0,
#     contentType="video/mp4",
#     uploadedAt="2024-01-01T00:00:00Z",
#     schemaVersion="1",
# )

# result = asyncio.run(run_pipeline(bad_message))
# print(f"run_pipeline returned: {result}")
# print("Expected: False (both pipelines failed)")

# doc = db.collection("jobs").document(JOB_ID).get()
# job = doc.to_dict() if doc.exists else None

# if job:
#     print(f"Firestore status: {job['status']}")
#     print(f"Firestore errorMessage: {job.get('errorMessage', '(empty)')}")
#     assert job["status"] == "failed", f"Expected status=failed, got {job['status']}"
#     assert job.get("errorMessage"), "Expected non-empty errorMessage"
#     print("Failure path assertions: PASS")
# else:
#     print("Job document not found")













# import os
# from dotenv import load_dotenv
# load_dotenv()

# from pipeline.gemini import get_gemini_client, GENERATION_CONFIG, MODEL_NAME
# from google.genai import types
# import json, time

# print("=" * 60)
# print("Week 4 Day 1 — Vertex AI / Gemini API connectivity test")
# print("=" * 60)
# print(f"Project: {os.getenv('GCP_PROJECT_ID')}")
# print(f"Location: us-central1")
# print(f"Model: {MODEL_NAME}")
# print()

# client = get_gemini_client()

# # Test 1 — Basic call
# print("Test 1 — Basic API call...")
# start = time.time()
# response = client.models.generate_content(
#     model=MODEL_NAME,
#     contents="Say hello in exactly one word.",
# )
# elapsed = time.time() - start
# print(f"  Response: '{response.text.strip()}'")
# print(f"  Latency: {elapsed:.2f}s")
# print(f"  Finish reason: {response.candidates[0].finish_reason}")
# print()

# # Test 2 — JSON mode
# print("Test 2 — JSON mode call...")
# start = time.time()
# json_response = client.models.generate_content(
#     model=MODEL_NAME,
#     contents='Return ONLY this JSON object, no markdown: {"message": "hello world", "number": 42, "success": true}',
#     config=GENERATION_CONFIG,
# )
# elapsed = time.time() - start
# raw_text = json_response.text.strip()
# print(f"  Raw response: {raw_text}")
# print(f"  Latency: {elapsed:.2f}s")
# try:
#     parsed = json.loads(raw_text)
#     print(f"  json.loads() success: PASS")
#     print(f"  Fields present: {list(parsed.keys())}")
# except json.JSONDecodeError as e:
#     print(f"  json.loads() FAILED: {e}")
# print()

# # Test 3 — Token usage
# print("Test 3 — Token usage metadata...")
# usage = json_response.usage_metadata
# print(f"  Input tokens:  {usage.prompt_token_count}")
# print(f"  Output tokens: {usage.candidates_token_count}")
# print(f"  Total tokens:  {usage.total_token_count}")
# print()

# # Test 4 — Finish reason
# print("Test 4 — Finish reason check...")
# finish_reason = str(json_response.candidates[0].finish_reason)
# print(f"  Finish reason: {finish_reason}")
# print("  Normal completion: PASS" if "STOP" in finish_reason else f"  Unexpected: {finish_reason}")

# print()
# print("=" * 60)
# print("All Day 1 Vertex AI tests complete.")
# print("=" * 60)














import os
from dotenv import load_dotenv
load_dotenv()

from google.cloud import firestore

PROJECT_ID = os.getenv("GCP_PROJECT_ID")

def load_job_data(job_id: str) -> dict:
    """
    Load transcript and scenes from Firestore for a completed job.
    Use this for prompt testing — real data surfaces real edge cases.
    """
    db = firestore.Client(project=PROJECT_ID)

    results_doc = db.collection("results").document(job_id).get()
    if not results_doc.exists:
        raise ValueError(f"No results document found for job {job_id}")

    data = results_doc.to_dict()
    transcript = data.get("transcript", [])
    scenes = data.get("scenes", [])

    jobs_doc = db.collection("jobs").document(job_id).get()
    processing_time = jobs_doc.to_dict().get("processingTime", 0) if jobs_doc.exists else 0

    print(f"Loaded job {job_id}:")
    print(f"  Transcript words: {len(transcript)}")
    print(f"  Scenes: {len(scenes)}")
    print(f"  Processing time: {processing_time}s")

    return {
        "transcript": transcript,
        "scenes": scenes,
        "duration_seconds": processing_time,
    }

REAL_JOB_ID = "5ad8cb9f-4503-4bb8-a02f-4b76c52506c4"
job_data = load_job_data(REAL_JOB_ID)


import json
import time
from pipeline.gemini import (
    get_gemini_model,
    GENERATION_CONFIG,
    MODEL_NAME,
    build_transcript_text,
    build_scene_summary,
    build_prompt,
)

print("=" * 60)
print("Week 4 Day 2 — Prompt engineering test")
print("=" * 60)
print()

transcript_text = build_transcript_text(job_data["transcript"])
scene_text = build_scene_summary(job_data["scenes"])
duration = job_data["duration_seconds"]

prompt = build_prompt(transcript_text, scene_text, duration)

print(f"Prompt stats:")
print(f"  Transcript words: {len(job_data['transcript'])}")
print(f"  Scenes: {len(job_data['scenes'])}")
print(f"  Duration: {duration}s")
print(f"  Prompt length: {len(prompt)} chars")
print()
print("Sending to Gemini...")
print()

client = get_gemini_model()

start = time.time()
response = client.models.generate_content(
    model=MODEL_NAME,
    contents=prompt,
    config=GENERATION_CONFIG,
)
elapsed = time.time() - start

print(f"Response received in {elapsed:.2f}s")
print()

finish_reason = response.candidates[0].finish_reason.name
print(f"Finish reason: {finish_reason}")

if finish_reason == "SAFETY":
    print("SAFETY BLOCK — response was filtered. Review prompt content.")
    exit(1)

if finish_reason == "MAX_TOKENS":
    print("MAX_TOKENS — response was cut off. Increase max_output_tokens or shorten prompt.")

usage = response.usage_metadata
print(f"Tokens — input: {usage.prompt_token_count}, output: {usage.candidates_token_count}")
print()

raw = response.text.strip()
print("Raw response:")
print("-" * 40)
print(raw)
print("-" * 40)
print()

print("Parsing response...")
try:
    parsed = json.loads(raw)
    print("json.loads(): PASS")
except json.JSONDecodeError as e:
    print(f"json.loads() FAILED: {e}")
    print("The prompt needs adjustment to produce clean JSON.")
    exit(1)

required_fields = ["summary", "chapters", "highlights", "sentiment", "actionItems"]
for field in required_fields:
    present = field in parsed
    print(f"  '{field}' present: {'PASS' if present else 'FAIL'}")

print()

print("Content quality review:")
print(f"  Summary ({len(parsed.get('summary', '').split())} words):")
print(f"    {parsed.get('summary', '(missing)')[:200]}")
print()

chapters = parsed.get("chapters", [])
print(f"  Chapters ({len(chapters)}):")
for ch in chapters:
    print(f"    [{ch.get('startTime', '?')}s–{ch.get('endTime', '?')}s] {ch.get('title', '(no title)')}")
print()

highlights = parsed.get("highlights", [])
print(f"  Highlights ({len(highlights)}):")
for hl in highlights:
    print(f"    @{hl.get('timestamp', '?')}s — {hl.get('description', '(no description)')}")
print()

print(f"  Sentiment: {parsed.get('sentiment', '(missing)')}")
action_items = parsed.get("actionItems", [])
print(f"  Action items ({len(action_items)}):")
for item in action_items:
    print(f"    - {item}")

print()
print("=" * 60)
print("Prompt test complete. Review the content quality above.")
print("If chapters are generic or highlights are weak, iterate the prompt in Step 5.")
print("=" * 60)