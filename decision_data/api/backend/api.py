from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Depends, Request
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging
from datetime import datetime
import json

from decision_data.backend.data.reddit import RedditScraper
from decision_data.data_structure.models import (
    Story, User, UserCreate, UserLogin, AudioFile, AudioFileCreate,
    UserPreferences, UserPreferencesCreate, UserPreferencesUpdate,
    TranscriptUser, ProcessingJob
)
from decision_data.backend.data.save_reddit_posts import (
    save_reddit_story_to_mongo,
)
from decision_data.backend.services.user_service import UserService
from decision_data.backend.services.audio_service import AudioFileService
from decision_data.backend.services.preferences_service import UserPreferencesService
from decision_data.backend.services.transcription_service import UserTranscriptionService
from decision_data.backend.utils.auth import generate_jwt_token, get_current_user

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Configure security logging
security_logger = logging.getLogger("security")
security_logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    '%(asctime)s - SECURITY - %(levelname)s - %(message)s'
))
security_logger.addHandler(handler)

app = FastAPI(title="Decision Stories API")

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    # Log security events
    if request.method in ["POST", "PUT", "DELETE"]:
        await log_security_event(
            "api_request",
            request.client.host,
            {
                "method": request.method,
                "path": request.url.path,
                "user_agent": request.headers.get("user-agent", "unknown")
            }
        )

    response = await call_next(request)

    # Add security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

    return response

# Enhanced CORS with security
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://panzoto.com",
        "https://www.panzoto.com",
        "http://api8000.panzoto.com:8000"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Security audit logging function
async def log_security_event(event_type: str, client_ip: str, details: dict):
    """Log security events for audit purposes"""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "client_ip": client_ip,
        "details": details
    }
    security_logger.info(json.dumps(log_entry))


@app.get("/api/stories", response_model=List[Story])
async def get_stories(
    source: str = Query("reddit", enum=["reddit"]),
    limit: Optional[int] = Query(None, ge=1, le=1000),
    subreddit: Optional[str] = None,
):
    """
    Retrieve stories from a specified data source.

    This endpoint fetches the latest stories from Reddit based on the provided
    subreddit and limit parameters. The stories are returned in JSON format.

    Args:
        source (str, optional): The data source to fetch stories from.
            Currently, only "reddit" is supported. Defaults to "reddit".
        limit (int, optional): The maximum number of stories to retrieve.
            Must be between 1 and 1000. Defaults to None.
        subreddit (str, optional): The name of the subreddit to fetch stories
            from. If not provided, defaults to "decision".

    Returns:
        List[Story]: A list of Story objects containing the fetched stories.

    Raises:
        HTTPException: If the provided source is not supported, a 400 error
            is raised with an appropriate message.

    Example:
        ```python
        import requests

        response = requests.get(
            "http://localhost:8000/api/stories",
            params={"source": "reddit", "limit": 5, "subreddit": "Python"}
        )
        stories = response.json()
        for story in stories:
            print(story['title'], story['url'])
        ```
    """
    if source == "reddit":
        if not subreddit:
            subreddit = "decision"
        scraper = RedditScraper()

        # Ensure 'limit' is an int. If 'limit' is None, use the default value
        # 10.
        actual_limit = limit if limit is not None else 10

        stories = scraper.fetch_stories(
            subreddit_name=subreddit,
            limit=actual_limit,
        )
        return stories
    else:
        raise HTTPException(status_code=400, detail="Source not supported")


@app.post("/api/save_stories")
async def save_stories_endpoint(
    background_tasks: BackgroundTasks,
    num_posts: int = Query(10, ge=1, le=1000),
):
    """
    Initiate background task to save Reddit stories to MongoDB.

    This endpoint triggers a background task that fetches a specified number
    of Reddit posts and saves them to a MongoDB database. The operation is
    performed asynchronously to ensure that the API remains responsive.

    Args:
        background_tasks (BackgroundTasks): A FastAPI BackgroundTasks instance
            used to manage background operations.
        num_posts (int, optional): The number of Reddit posts to fetch and
            save. Must be between 1 and 1000. Defaults to 10.

    Returns:
        dict: A confirmation message indicating that the saving process has
            been initiated.

    Example:
        ```python
        import requests

        response = requests.post(
            "http://127.0.0.1:8000/api/save_stories",
            params={"num_posts": 50}
        )
        print(response.json())  # Output: {"message": "Saving stories in the
        background."}
        ```
    """
    background_tasks.add_task(save_reddit_story_to_mongo, num_posts)
    return {"message": "Saving stories in the background."}


# User Management Endpoints

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "decision-data-backend", "database": "dynamodb"}


@app.post("/api/register")
@limiter.limit("5/minute")  # Limit registration attempts
async def register(request: Request, user_data: UserCreate):
    """Register new user with email and password"""
    try:
        # Validation
        if len(user_data.password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

        user_service = UserService()
        user = user_service.create_user(user_data)

        if not user:
            raise HTTPException(status_code=409, detail="User already exists")

        # Generate JWT token
        token = generate_jwt_token(user.user_id)

        return {
            "token": token,
            "user_id": user.user_id,
            "key_salt": user.key_salt,  # Send salt for key derivation
            "user": {
                "user_id": user.user_id,
                "email": user.email,
                "created_at": user.created_at.isoformat()
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Registration failed")


@app.post("/api/login")
@limiter.limit("10/minute")  # Limit login attempts
async def login(request: Request, login_data: UserLogin):
    """Authenticate user with email and password"""
    try:
        user_service = UserService()
        user = user_service.authenticate_user(login_data)

        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Generate JWT token
        token = generate_jwt_token(user.user_id)

        return {
            "token": token,
            "user_id": user.user_id,
            "key_salt": user.key_salt,
            "user": {
                "user_id": user.user_id,
                "email": user.email,
                "created_at": user.created_at.isoformat()
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Login failed")


@app.get("/api/user/audio-files", response_model=List[AudioFile])
async def get_user_audio_files(
    current_user_id: str = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100)
):
    """Get list of user's audio files"""
    try:
        audio_service = AudioFileService()
        audio_files = audio_service.get_user_audio_files(current_user_id, limit=limit)
        return audio_files

    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve audio files")


@app.post("/api/audio-file", response_model=AudioFile)
@limiter.limit("30/minute")  # Limit audio file uploads
async def create_audio_file(
    request: Request,
    file_data: AudioFileCreate,
    current_user_id: str = Depends(get_current_user)
):
    """Create new audio file record"""
    try:
        audio_service = AudioFileService()
        audio_file = audio_service.create_audio_file(current_user_id, file_data)

        if not audio_file:
            raise HTTPException(status_code=500, detail="Failed to create audio file record")

        return audio_file

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create audio file")


@app.get("/api/audio-file/{file_id}", response_model=AudioFile)
async def get_audio_file(
    file_id: str,
    current_user_id: str = Depends(get_current_user)
):
    """Get audio file by ID (only if owned by user)"""
    try:
        audio_service = AudioFileService()
        audio_file = audio_service.get_audio_file_by_id(file_id)

        if not audio_file:
            raise HTTPException(status_code=404, detail="Audio file not found")

        if audio_file.user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        return audio_file

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve audio file")


@app.delete("/api/audio-file/{file_id}")
async def delete_audio_file(
    file_id: str,
    current_user_id: str = Depends(get_current_user)
):
    """Delete audio file record"""
    try:
        audio_service = AudioFileService()
        success = audio_service.delete_audio_file(file_id, current_user_id)

        if not success:
            raise HTTPException(status_code=404, detail="Audio file not found")

        return {"message": "Audio file deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to delete audio file")


# User Preferences Endpoints

@app.post("/api/user/preferences", response_model=UserPreferences)
async def create_user_preferences(
    preferences_data: UserPreferencesCreate,
    current_user_id: str = Depends(get_current_user)
):
    """Create user preferences"""
    try:
        preferences_service = UserPreferencesService()
        preferences = preferences_service.create_preferences(current_user_id, preferences_data)

        if not preferences:
            raise HTTPException(status_code=409, detail="Preferences already exist")

        return preferences

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create preferences")


@app.get("/api/user/preferences", response_model=UserPreferences)
async def get_user_preferences(
    current_user_id: str = Depends(get_current_user)
):
    """Get user preferences"""
    try:
        preferences_service = UserPreferencesService()
        preferences = preferences_service.get_preferences(current_user_id)

        if not preferences:
            raise HTTPException(status_code=404, detail="Preferences not found")

        return preferences

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve preferences")


@app.put("/api/user/preferences", response_model=UserPreferences)
async def update_user_preferences(
    update_data: UserPreferencesUpdate,
    current_user_id: str = Depends(get_current_user)
):
    """Update user preferences"""
    try:
        preferences_service = UserPreferencesService()
        preferences = preferences_service.update_preferences(current_user_id, update_data)

        if not preferences:
            raise HTTPException(status_code=404, detail="Preferences not found")

        return preferences

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to update preferences")


@app.delete("/api/user/preferences")
async def delete_user_preferences(
    current_user_id: str = Depends(get_current_user)
):
    """Delete user preferences"""
    try:
        preferences_service = UserPreferencesService()
        success = preferences_service.delete_preferences(current_user_id)

        if not success:
            raise HTTPException(status_code=404, detail="Preferences not found")

        return {"message": "Preferences deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to delete preferences")


# Transcription Endpoints

@app.post("/api/transcribe/audio-file/{file_id}")
@limiter.limit("10/minute")  # Limit transcription requests
async def transcribe_audio_file(
    request: Request,
    file_id: str,
    current_user_id: str = Depends(get_current_user)
):
    """Trigger transcription for a specific audio file"""
    try:
        # Note: This endpoint would need user password for decryption
        # For now, we'll return a job ID and process asynchronously
        transcription_service = UserTranscriptionService()
        job_id = transcription_service.create_processing_job(
            current_user_id, 'transcription', file_id
        )

        return {
            "message": "Transcription job created",
            "job_id": job_id,
            "status": "pending"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create transcription job")


@app.get("/api/user/transcripts", response_model=List[TranscriptUser])
async def get_user_transcripts(
    current_user_id: str = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100)
):
    """Get user's transcripts"""
    try:
        transcription_service = UserTranscriptionService()
        transcripts = transcription_service.get_user_transcripts(current_user_id, limit)
        return transcripts

    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve transcripts")


@app.get("/api/user/processing-jobs", response_model=List[ProcessingJob])
async def get_user_processing_jobs(
    current_user_id: str = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=50)
):
    """Get user's processing jobs"""
    try:
        transcription_service = UserTranscriptionService()
        jobs = transcription_service.get_processing_jobs(current_user_id, limit)
        return jobs

    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve processing jobs")


@app.post("/api/user/request-daily-summary")
@limiter.limit("3/hour")  # Limit daily summary requests
async def request_daily_summary(
    request: Request,
    current_user_id: str = Depends(get_current_user)
):
    """Request daily summary generation for user"""
    try:
        transcription_service = UserTranscriptionService()
        job_id = transcription_service.create_processing_job(
            current_user_id, 'daily_summary'
        )

        return {
            "message": "Daily summary job created",
            "job_id": job_id,
            "status": "pending"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create daily summary job")
