from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class UploadResponse(BaseModel):
    jobId: str
    status: str
    message: str



class StatusResponse(BaseModel):
    jobId: str
    status: str
    progress: int
    stage: str = "Queued"      
    uploadProgress: int = 0
    videoUrl: Optional[str] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None


class WordTimestamp(BaseModel):
    word: str
    startTime: float
    endTime: float
    speaker: int

class Scene(BaseModel):
    startTime: float
    endTime: float
    labels: List[str]

class Chapter(BaseModel):
    title: str
    startTime: int
    endTime: int

class Highlight(BaseModel):
    timestamp: float
    description: str




class ResultResponse(BaseModel):
    jobId: str
    status: str
    videoUrl: Optional[str] = None
    transcript: Optional[List[WordTimestamp]] = None
    scenes: Optional[List[Scene]] = None
    summary: Optional[str] = None
    chapters: Optional[List[Chapter]] = None
    highlights: Optional[List[Highlight]] = None
    sentiment: Optional[str] = None
    processingTime: Optional[int] = None          
    processingStartedAt: Optional[datetime] = None   
    processingCompletedAt: Optional[datetime] = None 




class JobMessage(BaseModel):
    """
    Pub/Sub message payload published by the backend after a successful upload.
    Consumed and validated by the worker subscriber in Week 3.

    All fields are required — the worker depends on all of them.
    """
    jobId: str
    gcsPath: str               # e.g. raw-videos/{jobId}/{filename}
    gcsBucket: str             # e.g. video-intelligence-raw
    gcsUri: str                # e.g. gs://video-intelligence-raw/raw-videos/{jobId}/{filename}
    filename: str
    fileSizeMb: float          # Rounded to 2 decimal places
    contentType: str           # e.g. video/mp4
    uploadedAt: str            # ISO 8601 string — datetime not JSON serialisable by default
    schemaVersion: str = "1"   # Allows the worker to handle future schema changes gracefully


PROGRESS_STAGES = {
    0:   "Queued",
    10:  "Uploading video...",
    25:  "Queued for processing",
    50:  "Transcribing audio...",
    75:  "Detecting scenes...",
    90:  "Generating summary...",
    100: "Completed",
}

STAGE_FAILED = "Processing failed"


def progress_to_stage(progress: int, status: str = "pending") -> str:
    """
    Map a progress integer + status to a human-readable stage label.

    Uses the closest stage that is <= the current progress value.
    This means progress=60 maps to "Transcribing audio..." (stage 50),
    not "Detecting scenes..." (stage 75) — always shows the last
    completed stage, not the next one.

    Args:
        progress: Integer 0–100.
        status: Job status string — "failed" overrides the stage label.

    Returns:
        Human-readable stage string.
    """
    if status == "failed":
        return STAGE_FAILED

    if status == "completed" or progress >= 100:
        return PROGRESS_STAGES[100]

    # Find the highest stage key that is <= current progress
    applicable = [k for k in PROGRESS_STAGES if k <= progress]
    if not applicable:
        return PROGRESS_STAGES[0]

    return PROGRESS_STAGES[max(applicable)]