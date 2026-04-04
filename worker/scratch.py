import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from pipeline.speech_to_text import transcribe

# Replace with a real GCS URI from a video uploaded during Week 2
# Format: gs://video-intelligence-raw/raw-videos/{jobId}/{filename}
TEST_GCS_URI = "gs://video-intelligence-raw/raw-videos/5ad8cb9f-4503-4bb8-a02f-4b76c52506c4/test.mp4"

# Get a real job ID from the GCS console or from a Week 2 upload response
TEST_JOB_ID = "scratch-w3d1-stt"


async def test_speech_to_text():
    print(f"Testing Speech-to-Text pipeline...")
    print(f"  GCS URI: {TEST_GCS_URI}")
    print(f"  This will take 30–90 seconds for a typical video...")
    print()

    try:
        words = await transcribe(TEST_GCS_URI, job_id=TEST_JOB_ID)

        if not words:
            print("  WARNING: No words returned — video may have no speech")
            return

        print(f"  Total words transcribed: {len(words)}")
        print()
        print("  First 10 words with timestamps:")
        for w in words[:10]:
            print(
                f"    [{w['startTime']:.2f}s → {w['endTime']:.2f}s] "
                f"speaker={w['speaker']} | '{w['word']}'"
            )

        # Verify speaker diarization worked
        speakers = set(w["speaker"] for w in words)
        print()
        print(f"  Speakers detected: {sorted(speakers)}")

        # Verify timestamps are ordered
        for i in range(1, len(words)):
            assert words[i]["startTime"] >= words[i-1]["startTime"], \
                f"Words out of order at index {i}"
        print("  Timestamp ordering: PASS")

        # Check raw output was written to GCS
        print()
        print(f"  Check GCS bucket for: processed/{TEST_JOB_ID}/transcript.json")
        print("  (Open GCS console to verify the file exists)")

    except Exception as e:
        print(f"  FAILED: {e}")
        print()
        print("  Common causes:")
        print("  - Wrong GCS URI (check bucket and job ID)")
        print("  - Video has no audio track")
        print("  - Speech-to-Text API not enabled")
        print("  - Service account missing Speech-to-Text Editor role")
        raise


if __name__ == "__main__":
    asyncio.run(test_speech_to_text())