from pydantic import BaseModel
from typing import Optional, List


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
