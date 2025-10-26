from dotenv import load_dotenv
load_dotenv()  # Load .env file BEFORE any other imports

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
    TranscriptUser, ProcessingJob, CreateCheckoutSessionRequest,
    CreateCheckoutSessionResponse
)
import stripe
from decision_data.backend.services.user_service import UserService
from decision_data.backend.config.config import backend_config
from decision_data.backend.services.audio_service import AudioFileService
from decision_data.backend.services.preferences_service import UserPreferencesService
from decision_data.backend.services.transcription_service import UserTranscriptionService
from decision_data.backend.services.summary_retrieval_service import SummaryRetrievalService
from decision_data.backend.services.cost_tracking_service import get_cost_tracking_service
from decision_data.backend.services.audio_processor import start_background_processor, stop_background_processor
from decision_data.backend.services.daily_summary_scheduler import start_daily_summary_scheduler, stop_daily_summary_scheduler
from decision_data.backend.utils.auth import generate_jwt_token, get_current_user
import asyncio
import time

# Global background tasks
background_processor_task = None
daily_summary_scheduler_task = None

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Configure logging
logger = logging.getLogger("api")
logger.setLevel(logging.INFO)

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

# Configure Stripe
stripe.api_key = backend_config.STRIPE_SECRET_KEY

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Start background services on app startup"""
    global background_processor_task, daily_summary_scheduler_task
    try:
        logging.info("[START] Starting Decision Data API...")

        # Start background processor for automatic transcription
        background_processor_task = asyncio.create_task(start_background_processor())
        logging.info("[OK] Background processor started successfully")

        # Start daily summary scheduler for automatic scheduled summaries
        daily_summary_scheduler_task = asyncio.create_task(start_daily_summary_scheduler())
        logging.info("[OK] Daily summary scheduler started successfully")

    except Exception as e:
        logging.error(f"[ERROR] Error starting background services: {e}")
        # Don't fail startup if background services fail
        pass

@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown of background services"""
    global background_processor_task, daily_summary_scheduler_task
    try:
        logging.info("[STOP] Shutting down Decision Data API...")

        # Stop background processor gracefully
        if background_processor_task and not background_processor_task.done():
            stop_background_processor()
            background_processor_task.cancel()
            try:
                await background_processor_task
            except asyncio.CancelledError:
                pass

        # Stop daily summary scheduler gracefully
        if daily_summary_scheduler_task and not daily_summary_scheduler_task.done():
            stop_daily_summary_scheduler()
            daily_summary_scheduler_task.cancel()
            try:
                await daily_summary_scheduler_task
            except asyncio.CancelledError:
                pass

        logging.info("[OK] Background services shut down cleanly")

    except Exception as e:
        logging.error(f"[ERROR] Error during shutdown: {e}")

# Note: Background processor now enabled for automatic transcription processing
# Manual transcription triggers still available for immediate processing

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

        # Create default user preferences with automatic transcription enabled
        try:
            preferences_service = UserPreferencesService()
            default_prefs = UserPreferencesCreate(
                notification_email=user_data.email,
                enable_daily_summary=False,  # Off by default (user can enable in settings)
                enable_transcription=True,   # ON by default - automatic transcription
                summary_time_local="08:00",  # 8 AM local time default
                timezone_offset_hours=0      # UTC by default (user can set their timezone)
            )
            preferences_service.create_preferences(user.user_id, default_prefs)
            logging.info(f"Created default preferences for user {user.user_id} with transcription ENABLED")
        except Exception as pref_error:
            # Don't fail registration if preferences creation fails
            logging.error(f"Failed to create default preferences for user {user.user_id}: {pref_error}")

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
    """Create new audio file record and automatically create transcription job"""
    try:
        audio_service = AudioFileService()
        audio_file = audio_service.create_audio_file(current_user_id, file_data)

        if not audio_file:
            raise HTTPException(status_code=500, detail="Failed to create audio file record")

        # Automatically create transcription job for the uploaded audio file
        # Use audio file's recorded_at as job creation time for proper tracking
        from decision_data.backend.services.transcription_service import UserTranscriptionService
        transcription_service = UserTranscriptionService()
        try:
            job_id = transcription_service.create_processing_job(
                user_id=current_user_id,
                job_type="transcription",
                audio_file_id=audio_file.file_id,
                created_at=audio_file.recorded_at  # Use recording start time, not upload time
            )
            logging.info(f"Created transcription job {job_id} for audio file {audio_file.file_id}")
        except Exception as job_error:
            logging.error(f"Failed to create transcription job: {job_error}", exc_info=True)
            # Still return audio file even if job creation fails
            # Job can be created manually later

        return audio_file

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in create_audio_file endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create audio file: {str(e)}")


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


# S3 Presigned URL Endpoint

@app.get("/api/presigned-url")
async def get_presigned_url(key: str = Query(..., description="S3 object key")):
    """Generate presigned URL for S3 upload.

    This endpoint generates a presigned URL that allows direct upload to S3
    without exposing AWS credentials. The Android app uses this to upload
    encrypted audio files directly to S3.

    Args:
        key: S3 object key (e.g., "audio_upload/user-id/filename.3gp_encrypted")

    Returns:
        JSON with presigned URL for PUT request
        Example: {"url": "https://s3.amazonaws.com/...?AWSAccessKeyId=..."}
    """
    try:
        import boto3

        # Create S3 client
        s3_client = boto3.client(
            's3',
            region_name=backend_config.REGION_NAME,
            aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY
        )

        # Generate presigned URL valid for 15 minutes
        presigned_url = s3_client.generate_presigned_url(
            ClientMethod='put_object',
            Params={
                'Bucket': backend_config.AWS_S3_BUCKET_NAME,
                'Key': key,
                'ContentType': 'application/octet-stream'
            },
            ExpiresIn=900  # 15 minutes
        )

        logging.info(f"Generated presigned URL for key: {key}")
        return {"url": presigned_url}

    except Exception as e:
        logging.error(f"Failed to generate presigned URL for key '{key}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate presigned URL: {str(e)}")


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


# Daily Summary Endpoints

@app.get("/api/user/summaries")
async def get_user_summaries(
    current_user_id: str = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100)
):
    """Get all daily summaries for the user (decrypted)"""
    try:
        summary_service = SummaryRetrievalService()
        summaries = summary_service.get_user_summaries(current_user_id, limit=limit)
        return summaries

    except Exception as e:
        logging.error(f"Failed to retrieve summaries for user {current_user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve summaries")


@app.get("/api/user/summaries/{summary_date}")
async def get_summary_by_date(
    summary_date: str,
    current_user_id: str = Depends(get_current_user)
):
    """Get a specific summary for a user by date (YYYY-MM-DD format)"""
    try:
        summary_service = SummaryRetrievalService()
        summary = summary_service.get_summary_by_date(current_user_id, summary_date)

        if not summary:
            raise HTTPException(status_code=404, detail="Summary not found for this date")

        return summary

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Failed to retrieve summary for {current_user_id} on {summary_date}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve summary")


@app.delete("/api/user/summaries/{summary_id}")
async def delete_summary(
    summary_id: str,
    current_user_id: str = Depends(get_current_user)
):
    """Delete a specific summary"""
    try:
        summary_service = SummaryRetrievalService()
        success = summary_service.delete_summary(current_user_id, summary_id)

        if not success:
            raise HTTPException(status_code=404, detail="Summary not found or access denied")

        return {"message": "Summary deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Failed to delete summary {summary_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete summary")


@app.get("/api/user/summaries/export/download")
async def export_summaries(
    current_user_id: str = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=365),
    format: str = Query("json", enum=["json", "csv"])
):
    """Export user's summaries in JSON or CSV format"""
    try:
        summary_service = SummaryRetrievalService()
        exported_data = summary_service.export_summaries(
            current_user_id,
            limit=limit,
            format=format
        )

        if format == "json":
            return {"data": json.loads(exported_data)}
        else:  # CSV
            return {
                "data": exported_data,
                "filename": f"summaries_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
            }

    except Exception as e:
        logging.error(f"Failed to export summaries for user {current_user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to export summaries")


# Helper function for safe transcription processing
async def safe_process_transcription(user_id: str, file_id: str, password: str, job_id: str):
    """Safely process transcription with timeout and error handling."""
    transcription_service = UserTranscriptionService()

    try:
        # Set processing status
        transcription_service.update_job_status(job_id, 'processing')

        # Process with 5-minute timeout to prevent loops
        start_time = time.time()
        result = await asyncio.wait_for(
            asyncio.to_thread(
                transcription_service.process_user_audio_file,
                user_id, file_id
            ),
            timeout=300  # 5 minutes max
        )

        processing_time = time.time() - start_time

        if result:
            logging.info(f"[OK] Transcription completed for {file_id} in {processing_time:.1f}s")
        else:
            logging.warning(f"[WARN] Transcription completed but no result for {file_id}")

    except asyncio.TimeoutError:
        transcription_service.update_job_status(
            job_id, 'failed', 'Processing timeout (5 minutes)'
        )
        logging.error(f"[TIMEOUT] Transcription timeout for {file_id}")
    except Exception as e:
        transcription_service.update_job_status(
            job_id, 'failed', f'Processing error: {str(e)}'
        )
        logging.error(f"[ERROR] Transcription failed for {file_id}: {e}")

# Transcription Endpoints

from pydantic import BaseModel

class TranscriptionRequest(BaseModel):
    password: str

@app.post("/api/transcribe/audio-file/{file_id}")
@limiter.limit(f"{backend_config.TRANSCRIPTION_RATE_LIMIT_PER_MINUTE}/minute")  # Cost safety rate limit
async def transcribe_audio_file(
    request: Request,
    file_id: str,
    transcription_request: TranscriptionRequest,
    background_tasks: BackgroundTasks,
    current_user_id: str = Depends(get_current_user)
):
    """Trigger safe transcription for a specific audio file with user password"""
    try:
        transcription_service = UserTranscriptionService()
        audio_service = AudioFileService()

        # Safety check: Verify audio file exists and belongs to user
        audio_file = audio_service.get_audio_file_by_id(file_id)
        if not audio_file or audio_file.user_id != current_user_id:
            raise HTTPException(status_code=404, detail="Audio file not found")

        # Safety check: File size limit
        file_size_mb = audio_file.file_size / (1024 * 1024)
        max_size = backend_config.TRANSCRIPTION_MAX_FILE_SIZE_MB
        if file_size_mb > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large ({file_size_mb:.1f}MB). Maximum {max_size}MB allowed."
            )

        # Check for existing pending/processing jobs for this file
        existing_jobs = transcription_service.get_processing_jobs(current_user_id, 50)
        existing_job = None
        for job in existing_jobs:
            if (job.audio_file_id == file_id and
                job.job_type == 'transcription'):
                if job.status == 'processing':
                    raise HTTPException(
                        status_code=400,
                        detail="Transcription already in progress for this file"
                    )
                elif job.status == 'pending':
                    existing_job = job
                    break

        # Use existing pending job or create new one
        if existing_job:
            job_id = existing_job.job_id
            print(f"Using existing pending job {job_id} for audio file {file_id}")
        else:
            job_id = transcription_service.create_processing_job(
                current_user_id, 'transcription', file_id
            )
            print(f"Created new transcription job {job_id} for audio file {file_id}")

        # Add to background processing with user password
        background_tasks.add_task(
            safe_process_transcription,
            current_user_id,
            file_id,
            transcription_request.password,
            job_id
        )

        return {
            "message": "Transcription started",
            "job_id": job_id,
            "status": "processing"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to start transcription")


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


@app.get("/api/user/encryption-key")
async def get_user_encryption_key(
    current_user_id: str = Depends(get_current_user)
):
    """
    Get user's encryption key for client-side encryption.

    This endpoint provides the server-managed encryption key to authenticated users
    so they can encrypt audio files before uploading to S3.
    """
    try:
        logging.info(f"[KEY] Encryption key requested by user {current_user_id[:8]}...")
        user_service = UserService()
        encryption_key = user_service.get_user_encryption_key(current_user_id)
        logging.info(f"[KEY] Returning encryption key: {encryption_key[:20] if encryption_key else 'None'}...")

        if not encryption_key:
            raise HTTPException(
                status_code=404,
                detail="Encryption key not found. Please contact support."
            )

        return {
            "encryption_key": encryption_key,
            "user_id": current_user_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve encryption key for user {current_user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve encryption key"
        )


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


# Cost Tracking Endpoints

@app.get("/api/user/cost-summary")
async def get_cost_summary(
    current_user_id: str = Depends(get_current_user)
) -> dict:
    """Get user's cost summary for current month and history"""
    try:
        cost_service = get_cost_tracking_service()

        # Get current month costs
        current_month_costs = cost_service.get_current_month_usage(current_user_id)

        # Get user's credit
        credit_info = cost_service.get_user_credit(current_user_id)
        credit_balance = credit_info["balance"] if credit_info else 0.0

        logger.info(f"[COST] User {current_user_id}: credit_info={credit_info}, credit_balance={credit_balance}")

        # Get cost history for last 12 months
        history = cost_service.get_cost_history(current_user_id, months=12)

        # Format monthly history for response
        monthly_history = []
        for h in history:
            monthly_history.append({
                "month": h["month"],
                "total": float(h["costs"]["total"]),
                "breakdown": {
                    "whisper": float(h["costs"].get("whisper", 0)),
                    "s3": float(h["costs"].get("s3", 0)),
                    "dynamodb": float(h["costs"].get("dynamodb", 0)),
                    "ses": float(h["costs"].get("ses", 0)),
                    "secrets_manager": float(h["costs"].get("secrets_manager", 0)),
                    "openai": float(h["costs"].get("openai", 0)),
                    "other": float(h["costs"].get("other", 0)),
                }
            })

        return {
            "current_month": datetime.utcnow().strftime("%Y-%m"),
            "current_month_cost": float(current_month_costs["total"]),
            "current_month_breakdown": {
                "whisper": float(current_month_costs.get("whisper", 0)),
                "s3": float(current_month_costs.get("s3", 0)),
                "dynamodb": float(current_month_costs.get("dynamodb", 0)),
                "ses": float(current_month_costs.get("ses", 0)),
                "secrets_manager": float(current_month_costs.get("secrets_manager", 0)),
                "openai": float(current_month_costs.get("openai", 0)),
                "other": float(current_month_costs.get("other", 0)),
            },
            "total_usage": {
                "whisper": float(current_month_costs.get("whisper", 0)),
                "s3": float(current_month_costs.get("s3", 0)),
                "dynamodb": float(current_month_costs.get("dynamodb", 0)),
                "ses": float(current_month_costs.get("ses", 0)),
                "secrets_manager": float(current_month_costs.get("secrets_manager", 0)),
                "openai": float(current_month_costs.get("openai", 0)),
                "other": float(current_month_costs.get("other", 0)),
                "total": float(current_month_costs.get("total", 0)),
            },
            "credit_balance": float(credit_balance),
            "monthly_history": monthly_history,
        }

    except Exception as e:
        logger.warning(f"[WARN] Failed to get cost summary: {e}, returning empty response")
        # Return empty/zero cost response when tables don't exist or error occurs
        return {
            "current_month": datetime.utcnow().strftime("%Y-%m"),
            "current_month_cost": 0.0,
            "current_month_breakdown": {
                "whisper": 0.0,
                "s3": 0.0,
                "dynamodb": 0.0,
                "ses": 0.0,
                "secrets_manager": 0.0,
                "openai": 0.0,
                "other": 0.0,
            },
            "total_usage": {
                "whisper": 0.0,
                "s3": 0.0,
                "dynamodb": 0.0,
                "ses": 0.0,
                "secrets_manager": 0.0,
                "openai": 0.0,
                "other": 0.0,
                "total": 0.0,
            },
            "credit_balance": 0.0,
            "monthly_history": [],
        }


@app.get("/api/user/credit")
async def get_user_credit(
    current_user_id: str = Depends(get_current_user)
) -> dict:
    """Get user's credit account details"""
    try:
        cost_service = get_cost_tracking_service()
        credit_info = cost_service.get_user_credit(current_user_id)

        if not credit_info:
            raise HTTPException(status_code=404, detail="No credit account found")

        return {
            "balance": credit_info["balance"],
            "initial_credit": credit_info["initial"],
            "used_credit": credit_info["used"],
            "refunded_credit": credit_info["refunded"],
            "last_updated": credit_info["last_updated"],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR] Failed to get credit info: {e}")
        raise HTTPException(status_code=500, detail="Failed to get credit information")


# Stripe Payment Endpoints

@app.post("/api/create-checkout-session")
async def create_checkout_session(
    request_data: CreateCheckoutSessionRequest,
    current_user: dict = Depends(get_current_user)
) -> CreateCheckoutSessionResponse:
    """Create a Stripe Checkout session for credit purchase

    Args:
        request_data: Amount to purchase ($5, $10, or $20)
        current_user: Authenticated user from JWT token

    Returns:
        Checkout URL and session ID
    """
    user_id = current_user["user_id"]
    amount = request_data.amount

    # Validate amount (only allow predefined credit packages)
    valid_amounts = [5.00, 10.00, 20.00]
    if amount not in valid_amounts:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid amount. Must be one of: {valid_amounts}"
        )

    try:
        logger.info(f"[STRIPE] Creating checkout session for user {user_id}, amount ${amount}")

        # Create Stripe checkout session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'unit_amount': int(amount * 100),  # Convert to cents
                    'product_data': {
                        'name': f'Panzoto Credits - ${amount:.2f}',
                        'description': f'Audio transcription credits (${amount:.2f})',
                    },
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=backend_config.FRONTEND_URL + '/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=backend_config.FRONTEND_URL + '/cancelled',
            client_reference_id=user_id,  # Track which user is paying
            metadata={
                'user_id': user_id,
                'credit_amount': str(amount)
            }
        )

        logger.info(f"[STRIPE] Created session {checkout_session.id} for user {user_id}")

        return CreateCheckoutSessionResponse(
            checkout_url=checkout_session.url,
            session_id=checkout_session.id
        )

    except stripe.error.StripeError as e:
        logger.error(f"[STRIPE] Error creating checkout session: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[STRIPE] Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Payment processing error")


@app.post("/api/stripe-webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events (payment success, failure, etc.)

    This endpoint is called by Stripe when payment events occur.
    It verifies the webhook signature and processes successful payments
    by adding credits to the user's account.
    """
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')

    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, backend_config.STRIPE_WEBHOOK_SECRET
        )
        logger.info(f"[STRIPE] Webhook event received: {event['type']}")

    except ValueError as e:
        logger.error(f"[STRIPE] Invalid payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"[STRIPE] Invalid signature: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle successful payment
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']

        user_id = session['metadata']['user_id']
        credit_amount = float(session['metadata']['credit_amount'])
        payment_intent = session.get('payment_intent')
        amount_paid = session['amount_total'] / 100  # Convert from cents to dollars

        logger.info(
            f"[STRIPE] Payment successful for user {user_id}: "
            f"${amount_paid:.2f} (payment_intent: {payment_intent})"
        )

        # Add credits to user account
        try:
            cost_service = get_cost_tracking_service()
            success = cost_service.add_user_credit(user_id, credit_amount)

            if success:
                logger.info(
                    f"[STRIPE] Successfully added ${credit_amount} credits "
                    f"to user {user_id}"
                )
            else:
                logger.error(
                    f"[STRIPE] Failed to add credits to user {user_id}"
                )

        except Exception as e:
            logger.error(
                f"[STRIPE] Error adding credits to user {user_id}: {e}",
                exc_info=True
            )

    # Handle payment failure
    elif event['type'] == 'checkout.session.expired':
        session = event['data']['object']
        user_id = session['metadata']['user_id']
        logger.warning(f"[STRIPE] Checkout session expired for user {user_id}")

    elif event['type'] == 'payment_intent.payment_failed':
        payment_intent = event['data']['object']
        logger.warning(f"[STRIPE] Payment failed: {payment_intent.get('id')}")

    return {"status": "success"}
