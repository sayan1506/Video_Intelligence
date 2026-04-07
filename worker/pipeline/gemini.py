# worker/pipeline/gemini.py

import json
import logging
import os
from typing import List, Dict, Any, Optional

from google import genai
from google.genai import types
import time as time_module
from google.api_core.exceptions import ServiceUnavailable, ResourceExhausted

logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
LOCATION = "us-central1"
MODEL_NAME = "gemini-2.5-flash"

GENERATION_CONFIG = types.GenerateContentConfig(
    temperature=0.2,
    max_output_tokens=8192,
    response_mime_type="application/json",
)

_client: genai.Client | None = None


def get_gemini_client() -> genai.Client:
    """
    Return an initialised Gemini client using Vertex AI backend.
    Lazy init — ADC handles auth automatically.
    """
    global _client
    if _client is None:
        _client = genai.Client(
            vertexai=True,
            project=PROJECT_ID,
            location=LOCATION,
        )
        logger.info(f"Gemini client initialised — project: {PROJECT_ID}, location: {LOCATION}, model: {MODEL_NAME}")
    return _client


async def generate_summary(
    transcript: list,
    scenes: list,
    duration_seconds: int,
    job_id: str = "unknown",
) -> dict:
    """
    Generate AI summary, chapters, highlights, sentiment, and action items
    from video transcript and scene data using Vertex AI Gemini 1.5 Pro.

    Args:
        transcript: List of WordTimestamp dicts from STT pipeline.
        scenes: List of Scene dicts from Video Intelligence pipeline.
        duration_seconds: Total video duration in seconds.
        job_id: For logging.

    Returns:
        Dict with keys: summary, chapters, highlights, sentiment, actionItems.
        Never raises — returns safe defaults on any failure.
    """
    logger.info(
        f"[{job_id}] Gemini pipeline started — "
        f"words: {len(transcript)}, scenes: {len(scenes)}, duration: {duration_seconds}s"
    )

    # Build input text from structured data
    transcript_text = build_transcript_text(transcript)
    scene_text = build_scene_summary(scenes)
    prompt = build_prompt(transcript_text, scene_text, duration_seconds)

    logger.info(f"[{job_id}] Prompt built — {len(prompt)} chars")

    # Call Gemini with retry logic
    raw_response = _call_gemini_with_retry(prompt, job_id=job_id)

    if raw_response is None:
        logger.error(
            f"[{job_id}] Gemini call failed or was blocked — returning fallback summary"
        )
        return _FALLBACK_SUMMARY.copy()

    # Parse and validate the response
    result = parse_gemini_response(raw_response, job_id=job_id)

    logger.info(
        f"[{job_id}] Gemini pipeline complete — "
        f"summary: {len(result['summary'])} chars, "
        f"chapters: {len(result['chapters'])}, "
        f"highlights: {len(result['highlights'])}, "
        f"sentiment: {result['sentiment']}"
    )

    return result


# Maximum words to include in the transcript section of the prompt.
# A 10-min video at 150 wpm = ~1,500 words — well under this cap.
# The cap protects against abnormally long transcripts and keeps cost predictable.
MAX_TRANSCRIPT_WORDS = 8000

# Maximum scenes to describe in the prompt.
# Beyond ~30 scenes the scene summary becomes noise rather than signal.
MAX_SCENES_IN_PROMPT = 30


def build_transcript_text(transcript: list) -> str:
    """
    Flatten a list of WordTimestamp dicts into a single readable string.

    Gemini receives plain prose, not structured word objects. Speaker
    boundaries are preserved as paragraph breaks — this helps Gemini
    identify when speakers change topic and place chapter boundaries correctly.

    Args:
        transcript: List of WordTimestamp dicts with 'word', 'startTime',
                    'endTime', 'speaker' keys.

    Returns:
        Plain text transcript string, truncated to MAX_TRANSCRIPT_WORDS.
    """
    if not transcript:
        return "(No speech detected in this video.)"

    words = [w["word"] for w in transcript[:MAX_TRANSCRIPT_WORDS]]
    text = " ".join(words)

    truncated = len(transcript) > MAX_TRANSCRIPT_WORDS
    if truncated:
        text += f" [...transcript truncated at {MAX_TRANSCRIPT_WORDS} words...]"

    return text


def build_scene_summary(scenes: list) -> str:
    """
    Convert a list of Scene dicts into a readable description for Gemini.

    Provides temporal structure — Gemini uses scene timestamps to anchor
    chapter boundaries and highlights to specific moments in the video.

    Args:
        scenes: List of Scene dicts with 'startTime', 'endTime', 'labels' keys.

    Returns:
        Multi-line string describing each scene, capped at MAX_SCENES_IN_PROMPT.
    """
    if not scenes:
        return "(No scene data available.)"

    lines = []
    for i, scene in enumerate(scenes[:MAX_SCENES_IN_PROMPT], 1):
        start = scene.get("startTime", 0)
        end = scene.get("endTime", 0)
        labels = scene.get("labels", [])
        label_str = ", ".join(labels[:6]) if labels else "no labels detected"
        lines.append(f"Scene {i} ({start:.0f}s–{end:.0f}s): {label_str}")

    if len(scenes) > MAX_SCENES_IN_PROMPT:
        lines.append(f"[...{len(scenes) - MAX_SCENES_IN_PROMPT} more scenes not shown...]")

    return "\n".join(lines)





def build_prompt(
    transcript_text: str,
    scene_summary: str,
    duration_seconds: int,
) -> str:
    """
    Build the complete prompt for Gemini summary generation.

    Designed to produce strict JSON output matching the ResultResponse schema.
    Includes the full output schema definition and a concrete example to
    anchor Gemini's output format.

    Args:
        transcript_text: Plain text transcript from build_transcript_text().
        scene_summary: Scene description string from build_scene_summary().
        duration_seconds: Total video duration — used to calibrate chapters.

    Returns:
        Complete prompt string ready for model.generate_content().
    """
    duration_minutes = round(duration_seconds / 60, 1) if duration_seconds > 0 else "unknown"

    prompt = f"""You are an AI video analyst. Analyse the video transcript and scene data below, then return a JSON summary object.

VIDEO METADATA:
- Duration: {duration_minutes} minutes ({duration_seconds} seconds)

VIDEO TRANSCRIPT:
{transcript_text}

DETECTED SCENES:
{scene_summary}

INSTRUCTIONS:
1. Return ONLY a valid JSON object. No explanation, no markdown, no code fences.
2. The JSON must contain exactly these fields: summary, chapters, highlights, sentiment, actionItems.
3. Base all timestamps on the scene data and transcript content — do not invent timestamps.
4. Chapter titles must be descriptive and specific to the actual content — never use generic titles like "Introduction" or "Part 1".
5. Highlights must reference specific moments that are genuinely notable or informative.
6. sentiment must be exactly one of: "positive", "neutral", "negative".

OUTPUT SCHEMA:
{{
  "summary": "A 3 to 5 sentence executive overview of the video. What is it about? Who is the intended audience? What are the key points covered? What is the conclusion or takeaway?",
  "chapters": [
    {{
      "title": "Descriptive title based on actual content (e.g. 'Setting up the Python virtual environment')",
      "startTime": <integer seconds>,
      "endTime": <integer seconds>
    }}
  ],
  "highlights": [
    {{
      "timestamp": <float seconds — must match a scene boundary>,
      "description": "One sentence describing what happens at this moment"
    }}
  ],
  "sentiment": "positive | neutral | negative",
  "actionItems": [
    "Specific task or action mentioned in the video (e.g. 'Install Python 3.11 before proceeding')"
  ]
}}

CONSTRAINTS:
- summary: 3–5 sentences, 50–150 words.
- chapters: 2–8 chapters depending on video length. Each chapter must span at least 10 seconds.
- highlights: 2–5 highlights. Only include genuinely noteworthy moments.
- actionItems: Empty array [] if no specific actions are mentioned. Only include concrete tasks, not general advice.
- All startTime and endTime values must be integers between 0 and {duration_seconds}.

Return the JSON object now:"""

    return prompt



ALLOWED_SENTIMENTS = {"positive", "neutral", "negative"}

# Safe fallback returned when the response is unparseable or structurally invalid.
# Keeps the job completing even if Gemini fails — transcript and scenes are still useful.
_FALLBACK_SUMMARY = {
    "summary": "Summary generation encountered an issue. The transcript and scene analysis are still available.",
    "chapters": [],
    "highlights": [],
    "sentiment": "neutral",
    "actionItems": [],
}


def parse_gemini_response(raw_text: str, job_id: str = "unknown") -> dict:
    """
    Parse and validate the raw Gemini response text into a clean summary dict.

    Handles all four failure modes without raising:
      1. JSON parse failure  → returns fallback
      2. Missing fields      → fills in safe defaults per field
      3. Wrong types         → coerces to expected types
      4. Invalid enum values → normalises to nearest valid value

    Args:
        raw_text: The raw string from response.text — may or may not be valid JSON.
        job_id: For logging — helps trace parse issues to specific jobs.

    Returns:
        Dict with keys: summary, chapters, highlights, sentiment, actionItems.
        Never raises — always returns a usable dict.
    """

    # --- Step 1: JSON parse ---
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        logger.error(
            f"[{job_id}] JSON parse failed: {e} | "
            f"Raw text preview: {raw_text[:200]}"
        )
        return _FALLBACK_SUMMARY.copy()

    if not isinstance(data, dict):
        logger.error(f"[{job_id}] Response is valid JSON but not a dict — type: {type(data)}")
        return _FALLBACK_SUMMARY.copy()

    # --- Step 2: Parse each field with individual fallbacks ---
    return {
        "summary": _parse_summary(data.get("summary"), job_id),
        "chapters": _parse_chapters(data.get("chapters"), job_id),
        "highlights": _parse_highlights(data.get("highlights"), job_id),
        "sentiment": _parse_sentiment(data.get("sentiment"), job_id),
        "actionItems": _parse_action_items(data.get("actionItems"), job_id),
    }


def _parse_summary(value, job_id: str) -> str:
    """Parse and validate the summary field."""
    if not value:
        logger.warning(f"[{job_id}] Missing 'summary' field — using fallback")
        return _FALLBACK_SUMMARY["summary"]

    if not isinstance(value, str):
        logger.warning(f"[{job_id}] 'summary' is not a string — coercing from {type(value)}")
        value = str(value)

    value = value.strip()
    if len(value) < 10:
        logger.warning(f"[{job_id}] 'summary' is suspiciously short ({len(value)} chars)")
        return _FALLBACK_SUMMARY["summary"]

    return value


def _parse_chapters(value, job_id: str) -> list:
    """Parse and validate the chapters array."""
    if not value or not isinstance(value, list):
        logger.warning(f"[{job_id}] Missing or invalid 'chapters' — returning empty list")
        return []

    chapters = []
    for i, ch in enumerate(value):
        if not isinstance(ch, dict):
            logger.warning(f"[{job_id}] Chapter {i} is not a dict — skipping")
            continue

        title = ch.get("title", f"Chapter {i + 1}")
        if not isinstance(title, str) or not title.strip():
            title = f"Chapter {i + 1}"

        # Coerce startTime and endTime to int — Gemini sometimes returns floats or strings
        try:
            start_time = int(float(ch.get("startTime", 0)))
        except (TypeError, ValueError):
            logger.warning(f"[{job_id}] Chapter {i} has invalid startTime — defaulting to 0")
            start_time = 0

        try:
            end_time = int(float(ch.get("endTime", 0)))
        except (TypeError, ValueError):
            logger.warning(f"[{job_id}] Chapter {i} has invalid endTime — defaulting to 0")
            end_time = 0

        # Skip degenerate chapters
        if start_time >= end_time:
            logger.warning(
                f"[{job_id}] Chapter '{title}' has startTime >= endTime "
                f"({start_time} >= {end_time}) — skipping"
            )
            continue

        chapters.append({
            "title": title.strip(),
            "startTime": start_time,
            "endTime": end_time,
        })

    return chapters


def _parse_highlights(value, job_id: str) -> list:
    """Parse and validate the highlights array."""
    if not value or not isinstance(value, list):
        logger.warning(f"[{job_id}] Missing or invalid 'highlights' — returning empty list")
        return []

    highlights = []
    for i, hl in enumerate(value):
        if not isinstance(hl, dict):
            logger.warning(f"[{job_id}] Highlight {i} is not a dict — skipping")
            continue

        description = hl.get("description", "")
        if not isinstance(description, str) or not description.strip():
            logger.warning(f"[{job_id}] Highlight {i} has no description — skipping")
            continue

        # Coerce timestamp to float — Gemini may return int or string
        try:
            timestamp = float(hl.get("timestamp", 0))
        except (TypeError, ValueError):
            logger.warning(f"[{job_id}] Highlight {i} has invalid timestamp — defaulting to 0.0")
            timestamp = 0.0

        highlights.append({
            "timestamp": round(timestamp, 1),
            "description": description.strip(),
        })

    return highlights


def _parse_sentiment(value, job_id: str) -> str:
    """
    Parse and normalise the sentiment field.

    Handles capitalisation variations (Positive, POSITIVE) and
    maps near-matches to the closest allowed value.
    """
    if not value:
        logger.warning(f"[{job_id}] Missing 'sentiment' — defaulting to 'neutral'")
        return "neutral"

    normalised = str(value).lower().strip()

    if normalised in ALLOWED_SENTIMENTS:
        return normalised

    # Map common near-matches
    sentiment_map = {
        "mixed": "neutral",
        "balanced": "neutral",
        "informational": "neutral",
        "optimistic": "positive",
        "enthusiastic": "positive",
        "encouraging": "positive",
        "critical": "negative",
        "frustrated": "negative",
        "concerning": "negative",
    }

    if normalised in sentiment_map:
        mapped = sentiment_map[normalised]
        logger.warning(
            f"[{job_id}] Sentiment '{value}' not in allowed set — mapped to '{mapped}'"
        )
        return mapped

    logger.warning(
        f"[{job_id}] Unrecognised sentiment '{value}' — defaulting to 'neutral'"
    )
    return "neutral"


def _parse_action_items(value, job_id: str) -> list:
    """Parse and validate the actionItems array."""
    if value is None:
        return []

    if not isinstance(value, list):
        logger.warning(f"[{job_id}] 'actionItems' is not a list — returning empty")
        return []

    items = []
    for item in value:
        if isinstance(item, str) and item.strip():
            items.append(item.strip())
        else:
            logger.warning(f"[{job_id}] Skipping non-string actionItem: {item}")

    return items




# Retry config for transient Gemini API errors
GEMINI_MAX_RETRIES = 2
GEMINI_RETRY_BACKOFF = 5   # seconds


def _call_gemini_with_retry(
    prompt: str,
    job_id: str = "unknown",
) -> Optional[str]:
    """
    Call Gemini with retry logic for transient errors.

    Handles:
    - ServiceUnavailable / ResourceExhausted → retry with backoff
    - SAFETY finish reason → return None immediately (no point retrying)
    - MAX_TOKENS finish reason → return partial response with warning
    - STOP finish reason → normal return

    Args:
        prompt: Complete prompt string from build_prompt().
        job_id: For logging.

    Returns:
        Raw response text string, or None if the call failed after all retries
        or was blocked by safety filters.
    """
    client = get_gemini_client()
    last_exception = None

    for attempt in range(1, GEMINI_MAX_RETRIES + 2):  # +2: initial attempt + retries
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=GENERATION_CONFIG,
            )

            # Check finish reason before returning
            if not response.candidates:
                logger.error(f"[{job_id}] Gemini returned no candidates — attempt {attempt}")
                last_exception = RuntimeError("No candidates in response")
                time_module.sleep(GEMINI_RETRY_BACKOFF * attempt)
                continue

            finish_reason = response.candidates[0].finish_reason.name

            if finish_reason == "SAFETY":
                logger.error(
                    f"[{job_id}] Gemini response blocked by safety filters — not retrying"
                )
                return None  # Safety blocks don't resolve on retry

            if finish_reason == "MAX_TOKENS":
                logger.warning(
                    f"[{job_id}] Gemini response truncated (MAX_TOKENS) — "
                    f"partial response may not parse correctly"
                )
                # Return the partial response — parser will handle gracefully
                return response.text

            # Log token usage on every successful call
            usage = response.usage_metadata
            logger.info(
                f"[{job_id}] Gemini call OK (attempt {attempt}) — "
                f"input tokens: {usage.prompt_token_count}, "
                f"output tokens: {usage.candidates_token_count}"
            )

            return response.text

        except (ServiceUnavailable, ResourceExhausted) as e:
            last_exception = e
            if attempt <= GEMINI_MAX_RETRIES:
                backoff = GEMINI_RETRY_BACKOFF * attempt
                logger.warning(
                    f"[{job_id}] Gemini transient error (attempt {attempt}): {e}. "
                    f"Retrying in {backoff}s..."
                )
                time_module.sleep(backoff)
            else:
                logger.error(
                    f"[{job_id}] Gemini failed after {GEMINI_MAX_RETRIES} retries: {e}"
                )

        except Exception as e:
            # Non-retryable error — fail immediately
            logger.error(f"[{job_id}] Gemini non-retryable error: {e}")
            return None

    logger.error(f"[{job_id}] All Gemini retries exhausted. Last error: {last_exception}")
    return None



