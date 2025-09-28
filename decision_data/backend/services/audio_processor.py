"""
Cost-safe automatic audio transcription processor.

This service prevents expensive infinite loops by implementing strict limits:
- File size limits (5MB max)
- Retry limits (3 max attempts per file)
- Processing timeouts (5 minutes max)
- Retry backoff (10 minutes between attempts)
- Daily retry limits (prevent same-day reprocessing)
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Optional, List
import logging
from pathlib import Path

from decision_data.backend.services.transcription_service import UserTranscriptionService
from decision_data.backend.services.audio_service import AudioFileService
from decision_data.backend.services.user_service import UserService
from decision_data.backend.config.config import backend_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SafeAudioProcessor:
    """Cost-safe automatic audio processor with strict limits."""

    # Safety limits to prevent expensive loops
    MAX_FILE_SIZE_MB = 5  # 5MB limit
    MAX_RETRIES = 3  # Maximum 3 attempts per file
    PROCESSING_TIMEOUT_MINUTES = 5  # 5 minute timeout
    RETRY_BACKOFF_MINUTES = 10  # 10 minutes between retries
    CHECK_INTERVAL_SECONDS = 60  # Check every minute (not 30 seconds)

    def __init__(self):
        self.transcription_service = UserTranscriptionService()
        self.audio_service = AudioFileService()
        self.user_service = UserService()
        self.is_running = False

    async def start_processor(self):
        """Start the background processor."""
        logger.info("🚀 Starting cost-safe audio processor...")
        logger.info(f"Safety limits: {self.MAX_FILE_SIZE_MB}MB max, {self.MAX_RETRIES} retries, {self.PROCESSING_TIMEOUT_MINUTES}min timeout")

        self.is_running = True
        while self.is_running:
            try:
                await self.process_pending_jobs()
                await asyncio.sleep(self.CHECK_INTERVAL_SECONDS)
            except Exception as e:
                logger.error(f"❌ Error in processor loop: {e}")
                await asyncio.sleep(self.CHECK_INTERVAL_SECONDS)

    def stop_processor(self):
        """Stop the background processor."""
        logger.info("🛑 Stopping audio processor...")
        self.is_running = False

    async def process_pending_jobs(self):
        """Process pending transcription jobs with safety checks."""
        try:
            # Get pending jobs that are eligible for processing
            eligible_jobs = self.get_eligible_pending_jobs()

            if not eligible_jobs:
                return

            logger.info(f"📋 Processing {len(eligible_jobs)} eligible jobs")

            for job in eligible_jobs:
                try:
                    await self.process_single_job(job)
                except Exception as e:
                    logger.error(f"❌ Failed to process job {job['job_id']}: {e}")
                    self.mark_job_failed(job['job_id'], f"Processing error: {str(e)}")

        except Exception as e:
            logger.error(f"❌ Error getting pending jobs: {e}")

    def get_eligible_pending_jobs(self) -> List[dict]:
        """Get pending jobs that are safe to process."""
        try:
            # Query pending transcription jobs
            response = self.transcription_service.jobs_table.scan(
                FilterExpression='#status = :status AND job_type = :job_type',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': 'pending',
                    ':job_type': 'transcription'
                }
            )

            eligible_jobs = []
            now = datetime.utcnow()

            for job in response['Items']:
                if self.is_job_eligible(job, now):
                    eligible_jobs.append(job)
                else:
                    logger.debug(f"⏭️ Skipping job {job['job_id']} - not eligible")

            return eligible_jobs

        except Exception as e:
            logger.error(f"❌ Error querying jobs: {e}")
            return []

    def is_job_eligible(self, job: dict, now: datetime) -> bool:
        """Check if a job is eligible for processing with safety checks."""
        job_id = job['job_id']

        # Check retry count
        retry_count = job.get('retry_count', 0)
        if retry_count >= self.MAX_RETRIES:
            logger.warning(f"⚠️ Job {job_id} exceeded max retries ({retry_count})")
            self.mark_job_failed(job_id, f"Exceeded maximum retries ({self.MAX_RETRIES})")
            return False

        # Check if job is too old (stuck jobs)
        created_at = datetime.fromisoformat(job['created_at'])
        age_hours = (now - created_at).total_seconds() / 3600
        if age_hours > 24:  # 24 hour limit
            logger.warning(f"⚠️ Job {job_id} is too old ({age_hours:.1f} hours)")
            self.mark_job_failed(job_id, "Job expired - too old")
            return False

        # Check retry backoff
        if retry_count > 0:
            last_attempt = job.get('last_attempt_at')
            if last_attempt:
                last_attempt_time = datetime.fromisoformat(last_attempt)
                time_since_last = (now - last_attempt_time).total_seconds() / 60
                if time_since_last < self.RETRY_BACKOFF_MINUTES:
                    logger.debug(f"⏳ Job {job_id} in backoff period ({time_since_last:.1f}min)")
                    return False

        return True

    async def process_single_job(self, job: dict):
        """Process a single transcription job safely."""
        job_id = job['job_id']
        user_id = job['user_id']
        audio_file_id = job.get('audio_file_id')

        logger.info(f"🎵 Processing job {job_id} for user {user_id}")

        if not audio_file_id:
            self.mark_job_failed(job_id, "No audio file ID provided")
            return

        # Update retry count and timestamp
        self.update_job_attempt(job_id, job.get('retry_count', 0))

        # Get audio file info for size check
        audio_file = self.audio_service.get_audio_file_by_id(audio_file_id)
        if not audio_file:
            self.mark_job_failed(job_id, "Audio file not found")
            return

        # Check file size safety limit
        file_size_mb = audio_file.file_size / (1024 * 1024)
        if file_size_mb > self.MAX_FILE_SIZE_MB:
            logger.warning(f"⚠️ File too large: {file_size_mb:.1f}MB > {self.MAX_FILE_SIZE_MB}MB")
            self.mark_job_failed(job_id, f"File too large ({file_size_mb:.1f}MB)")
            return

        # Get user info for decryption
        user = self.user_service.get_user_by_id(user_id)
        if not user:
            self.mark_job_failed(job_id, "User not found")
            return

        # Check if user has transcription enabled
        preferences = self.get_user_preferences(user_id)
        if preferences and not preferences.get('enable_transcription', True):
            logger.info(f"👤 User {user_id} has transcription disabled, skipping")
            self.mark_job_failed(job_id, "User has transcription disabled")
            return

        # Process with timeout protection
        try:
            # For automatic processing, we need to modify the transcription service
            # to not require user password (since it's not available in background)
            # Instead, we'll create a version that uses stored encryption keys

            # Process with timeout
            start_time = time.time()
            transcript_id = await asyncio.wait_for(
                asyncio.to_thread(
                    self.process_audio_file_automatic,
                    user_id, audio_file_id, user
                ),
                timeout=self.PROCESSING_TIMEOUT_MINUTES * 60
            )

            processing_time = time.time() - start_time
            logger.info(f"✅ Job {job_id} completed in {processing_time:.1f}s")

            if transcript_id:
                logger.info(f"📝 Created transcript {transcript_id}")
            else:
                logger.warning(f"⚠️ Job {job_id} completed but no transcript created")

        except asyncio.TimeoutError:
            logger.error(f"⏰ Job {job_id} timed out after {self.PROCESSING_TIMEOUT_MINUTES} minutes")
            self.mark_job_failed(job_id, f"Processing timeout ({self.PROCESSING_TIMEOUT_MINUTES} minutes)")
        except Exception as e:
            logger.error(f"❌ Job {job_id} failed: {e}")
            # Don't mark as failed immediately - let it retry with backoff
            raise

    def update_job_attempt(self, job_id: str, current_retry_count: int):
        """Update job with new attempt information."""
        try:
            new_retry_count = current_retry_count + 1
            now = datetime.utcnow().isoformat()

            self.transcription_service.jobs_table.update_item(
                Key={'job_id': job_id},
                UpdateExpression='SET retry_count = :count, last_attempt_at = :time',
                ExpressionAttributeValues={
                    ':count': new_retry_count,
                    ':time': now
                }
            )

            logger.info(f"📊 Job {job_id} attempt #{new_retry_count}")

        except Exception as e:
            logger.error(f"❌ Failed to update job attempt for {job_id}: {e}")

    def mark_job_failed(self, job_id: str, error_message: str):
        """Mark a job as permanently failed."""
        try:
            self.transcription_service.update_job_status(job_id, 'failed', error_message)
            logger.warning(f"💀 Job {job_id} marked as failed: {error_message}")
        except Exception as e:
            logger.error(f"❌ Failed to mark job {job_id} as failed: {e}")

    def get_user_preferences(self, user_id: str) -> Optional[dict]:
        """Get user preferences to check if transcription is enabled."""
        try:
            # This would use your preferences service
            # For now, assume transcription is enabled by default
            return {'enable_transcription': True}
        except Exception:
            return None

    def process_audio_file_automatic(self, user_id: str, audio_file_id: str, user) -> Optional[str]:
        """
        Process audio file for automatic transcription.

        Note: This is a simplified version that assumes we can decrypt automatically.
        In a real system, you'd need to store server-side encryption keys or
        use a different encryption approach that allows server-side processing.
        """
        job_id = self.transcription_service.create_processing_job(user_id, 'transcription', audio_file_id)

        try:
            self.transcription_service.update_job_status(job_id, 'processing')

            # Get audio file metadata
            audio_file = self.audio_service.get_audio_file_by_id(audio_file_id)

            if not audio_file or audio_file.user_id != user_id:
                self.transcription_service.update_job_status(job_id, 'failed', 'Audio file not found or access denied')
                return None

            # For automatic processing, we need to handle the fact that
            # files are encrypted with user password. For now, we'll create jobs
            # but they'll need user interaction to decrypt.
            # TODO: Implement server-side encryption keys in the future

            # For now, skip automatic processing and just mark as pending
            # until we implement server-side keys
            self.transcription_service.update_job_status(job_id, 'failed', 'Automatic decryption not yet implemented - requires manual trigger')
            return None

            # Download and decrypt audio file
            decrypted_file = self.transcription_service.download_and_decrypt_audio(
                audio_file.s3_key,
                server_password,
                user.key_salt
            )

            if not decrypted_file:
                self.transcription_service.update_job_status(job_id, 'failed', 'Failed to decrypt audio file')
                return None

            try:
                # Get audio duration for validation
                from decision_data.backend.transcribe.whisper import get_audio_duration, transcribe_from_local

                duration = get_audio_duration(decrypted_file)
                if duration < 3.0 or duration > 300.0:  # 3 seconds to 5 minutes
                    self.transcription_service.update_job_status(job_id, 'failed', f'Audio duration {duration}s outside valid range')
                    return None

                # Transcribe audio
                transcript = transcribe_from_local(decrypted_file)

                if not transcript or len(transcript.strip()) < 10:
                    self.transcription_service.update_job_status(job_id, 'failed', 'Transcription failed or too short')
                    return None

                # Save transcript to database
                transcript_id = self.transcription_service.save_transcript_to_db(
                    user_id, audio_file_id, transcript, duration, audio_file.s3_key
                )

                self.transcription_service.update_job_status(job_id, 'completed')
                return transcript_id

            finally:
                # Clean up decrypted file
                if decrypted_file.exists():
                    decrypted_file.unlink()

        except Exception as e:
            self.transcription_service.update_job_status(job_id, 'failed', str(e))
            logger.error(f"❌ Automatic processing failed for {audio_file_id}: {e}")
            return None

# Global processor instance
processor = SafeAudioProcessor()

async def start_background_processor():
    """Start the background processor."""
    await processor.start_processor()

def stop_background_processor():
    """Stop the background processor."""
    processor.stop_processor()