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
    progress: int        # 0–100, overall pipeline progress
    uploadProgress: int = 0   # ← 0–100, GCS upload progress
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