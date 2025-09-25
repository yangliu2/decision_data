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
