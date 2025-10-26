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
    recorded_at: Optional[datetime] = None  # When recording actually started (from Android app)


class UserCreate(BaseModel):
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class AudioFileCreate(BaseModel):
    s3_key: str
    file_size: Optional[int] = None
    recorded_at: str  # ISO 8601 timestamp when recording started (from Android app)


class UserPreferences(BaseModel):
    user_id: str
    notification_email: str
    enable_daily_summary: bool = True
    enable_transcription: bool = True
    summary_time_local: str = "09:00"  # Daily summary time in user's local time (HH:MM format)
    timezone_offset_hours: int = 0  # Offset from UTC in hours (e.g., -6 for CST)
    recording_max_duration_minutes: int = 60  # Maximum recording duration in minutes (default 60)
    created_at: datetime
    updated_at: datetime


class UserPreferencesCreate(BaseModel):
    notification_email: str
    enable_daily_summary: Optional[bool] = True
    enable_transcription: Optional[bool] = True
    summary_time_local: Optional[str] = "09:00"  # User's local time
    timezone_offset_hours: Optional[int] = 0  # Offset from UTC
    recording_max_duration_minutes: Optional[int] = 60  # Maximum recording duration in minutes


class UserPreferencesUpdate(BaseModel):
    notification_email: Optional[str] = None
    enable_daily_summary: Optional[bool] = None
    enable_transcription: Optional[bool] = None
    summary_time_local: Optional[str] = None
    timezone_offset_hours: Optional[int] = None
    recording_max_duration_minutes: Optional[int] = None


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


class DailySummaryResponse(BaseModel):
    """Decrypted daily summary response for API"""
    summary_id: str
    summary_date: str
    family_info: List[str]
    business_info: List[str]
    misc_info: List[str]
    created_at: datetime


# Cost Tracking Models

class UsageRecord(BaseModel):
    """Individual API call usage record"""
    usage_id: str
    user_id: str
    service: str  # "whisper", "s3", "dynamodb", "ses", "secrets_manager"
    operation: str  # "transcribe", "upload", "query", "send_email", etc.
    quantity: float  # minutes for whisper, MB for S3, etc.
    unit: str  # "minutes", "MB", "requests", etc.
    cost_usd: float  # Calculated cost in USD
    timestamp: str  # ISO timestamp
    month: str  # YYYY-MM for easy filtering


class CostSummary(BaseModel):
    """Monthly cost summary by service"""
    month: str  # YYYY-MM
    user_id: str
    whisper_cost: float
    s3_cost: float
    dynamodb_cost: float
    ses_cost: float
    other_cost: float
    total_cost: float
    created_at: str


class UserCredit(BaseModel):
    """User credit account"""
    user_id: str
    credit_balance: float  # in USD
    initial_credit: float
    used_credit: float
    refunded_credit: float
    last_updated: str


class CostSummaryResponse(BaseModel):
    """API response for cost summary"""
    current_month: str
    current_month_cost: float
    current_month_breakdown: dict  # service -> cost
    total_usage: dict  # service -> quantity
    credit_balance: float
    monthly_history: List[dict]  # List of past months with costs


# Stripe Payment Models
class CreateCheckoutSessionRequest(BaseModel):
    """Request to create a Stripe checkout session"""
    amount: float  # Amount in USD (e.g., 5.00, 10.00, 20.00)


class CreateCheckoutSessionResponse(BaseModel):
    """Response with Stripe checkout URL"""
    checkout_url: str
    session_id: str
