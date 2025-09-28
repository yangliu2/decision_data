from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class Story(BaseModel):
    id: str
    title: str
    content: str
    url: str
    score: int
    comments: int
    created_utc: float
    author: Optional[str]


class Transcript(BaseModel):
    transcript: str
    length_in_seconds: float
    original_audio_path: str
    created_utc: str


class DailySummary(BaseModel):
    family_info: List[str]
    business_info: List[str]
    misc_info: List[str]


class User(BaseModel):
    user_id: str
    email: str
    password_hash: Optional[str] = None  # Don't include in API responses
    key_salt: Optional[str] = None  # Don't include in API responses
    created_at: datetime

    class Config:
        # Exclude sensitive fields from serialization by default
        fields = {
            'password_hash': {'write_only': True},
            'key_salt': {'write_only': True}
        }


class AudioFile(BaseModel):
    file_id: str
    user_id: str
    s3_key: str
    file_size: Optional[int] = None
    uploaded_at: datetime


class UserCreate(BaseModel):
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class AudioFileCreate(BaseModel):
    s3_key: str
    file_size: Optional[int] = None


class UserPreferences(BaseModel):
    user_id: str
    notification_email: str
    enable_daily_summary: bool = True
    enable_transcription: bool = True
    summary_time_utc: str = "09:00"  # Daily summary time in UTC (HH:MM format)
    created_at: datetime
    updated_at: datetime


class UserPreferencesCreate(BaseModel):
    notification_email: str
    enable_daily_summary: Optional[bool] = True
    enable_transcription: Optional[bool] = True
    summary_time_utc: Optional[str] = "09:00"


class UserPreferencesUpdate(BaseModel):
    notification_email: Optional[str] = None
    enable_daily_summary: Optional[bool] = None
    enable_transcription: Optional[bool] = None
    summary_time_utc: Optional[str] = None


class ProcessingJob(BaseModel):
    job_id: str
    user_id: str
    job_type: str  # "transcription", "daily_summary"
    audio_file_id: Optional[str] = None  # For transcription jobs
    status: str  # "pending", "processing", "completed", "failed"
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class TranscriptUser(BaseModel):
    transcript_id: str
    user_id: str
    audio_file_id: str
    transcript: str
    length_in_seconds: float
    s3_key: str
    created_at: datetime
