"""User-specific transcription service that handles encrypted audio files."""

import uuid
import boto3
from pathlib import Path
from datetime import datetime
from typing import Optional
from decimal import Decimal
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Hash import SHA256
import io
import tempfile
import base64
from botocore.exceptions import ClientError
from loguru import logger

from decision_data.backend.config.config import backend_config
from decision_data.backend.transcribe.whisper import transcribe_from_local, get_audio_duration
from decision_data.backend.services.audio_service import AudioFileService
from decision_data.backend.services.user_service import UserService
from decision_data.backend.services.cost_tracking_service import get_cost_tracking_service
from decision_data.backend.utils.secrets_manager import secrets_manager
from decision_data.backend.utils.aes_encryption import aes_encryption
from decision_data.data_structure.models import (
    TranscriptUser,
    ProcessingJob,
    UserPreferences
)


class UserTranscriptionService:
    """Service for handling user-specific audio transcription with encryption."""

    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            region_name=backend_config.REGION_NAME,
            aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY
        )
        self.dynamodb = boto3.resource(
            'dynamodb',
            region_name=backend_config.REGION_NAME,
            aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY
        )
        self.bucket_name = backend_config.AWS_S3_BUCKET_NAME
        self.transcripts_table = self.dynamodb.Table('panzoto-transcripts')
        self.jobs_table = self.dynamodb.Table('panzoto-processing-jobs')

    def decrypt_audio_file(self, encrypted_data: bytes, encryption_key_b64: str) -> bytes:
        """
        Decrypt audio file using server-managed encryption key.

        Args:
            encrypted_data: Encrypted audio data (IV + ciphertext + tag)
            encryption_key_b64: Base64-encoded 256-bit encryption key

        Returns:
            Decrypted audio data
        """
        try:
            # Decode the encryption key from base64
            key = base64.b64decode(encryption_key_b64)

            # Extract IV from the first 16 bytes
            iv = encrypted_data[:16]
            encrypted_content = encrypted_data[16:-16]  # Remove IV and tag
            tag = encrypted_data[-16:]  # Last 16 bytes are the tag

            # Decrypt using AES-GCM
            cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
            decrypted_data = cipher.decrypt_and_verify(encrypted_content, tag)

            return decrypted_data

        except Exception as e:
            import logging
            logging.error(f"[ERROR] Error decrypting audio file: {e}", exc_info=True)
            print(f"Error decrypting audio file: {e}")
            raise

    def download_and_decrypt_audio(self, s3_key: str, user_id: str) -> Optional[Path]:
        """
        Download encrypted audio from S3 and decrypt it using server-managed key.

        Args:
            s3_key: S3 object key for the encrypted audio file
            user_id: User UUID to retrieve encryption key

        Returns:
            Path to decrypted temporary file, or None on failure
        """
        try:
            logger.info(f"[DOWNLOAD] Starting S3 download and decryption for {s3_key}")

            # Get user's encryption key from Secrets Manager
            logger.info(f"[KEY] Fetching encryption key from Secrets Manager for user {user_id}")
            try:
                encryption_key = secrets_manager.get_user_encryption_key(user_id)
            except Exception as key_error:
                error_msg = f"Failed to fetch encryption key: {str(key_error)}"
                logger.error(f"[KEY ERROR] {error_msg}", exc_info=True)
                return None

            if not encryption_key:
                error_msg = f"Encryption key not found in Secrets Manager for user {user_id}"
                logger.error(f"[KEY ERROR] {error_msg}")
                return None

            logger.info(f"[KEY] Encryption key found (length: {len(encryption_key)} chars)")

            # Download encrypted file from S3
            logger.info(f"[S3] Downloading encrypted file from S3: {s3_key}")
            try:
                response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
                encrypted_data = response['Body'].read()
                logger.info(f"[S3] Downloaded {len(encrypted_data)} bytes from S3")
            except Exception as s3_error:
                error_msg = f"Failed to download from S3: {str(s3_error)}"
                logger.error(f"[S3 ERROR] {error_msg}", exc_info=True)
                return None

            # Decrypt the data
            logger.info(f"[DECRYPT] Decrypting {len(encrypted_data)} bytes with AES-256-GCM")
            try:
                decrypted_data = self.decrypt_audio_file(encrypted_data, encryption_key)
                logger.info(f"[DECRYPT] Successfully decrypted to {len(decrypted_data)} bytes")
            except Exception as decrypt_error:
                error_msg = f"Decryption failed: {str(decrypt_error)}"
                logger.error(f"[DECRYPT ERROR] {error_msg}", exc_info=True)
                return None

            # Save decrypted data to temporary file
            temp_dir = Path("data/processing_audio")
            temp_dir.mkdir(parents=True, exist_ok=True)

            # Create temporary file with .3gp extension
            temp_file = temp_dir / f"decrypted_{uuid.uuid4().hex}.3gp"
            with open(temp_file, 'wb') as f:
                f.write(decrypted_data)

            logger.info(f"[TEMP] Saved decrypted file to {temp_file}")
            return temp_file

        except Exception as e:
            logger.error(f"[CRITICAL ERROR] Unexpected error during download/decrypt: {str(e)}", exc_info=True)
            return None

    def create_processing_job(self, user_id: str, job_type: str, audio_file_id: Optional[str] = None, created_at: Optional[datetime] = None) -> str:
        """Create a processing job record.

        Args:
            user_id: User's UUID
            job_type: Type of job (e.g., 'transcription', 'daily_summary')
            audio_file_id: Associated audio file ID (for transcription jobs)
            created_at: Optional creation timestamp (defaults to now). For transcription jobs,
                       should be set to the audio file's recorded_at time for proper tracking.
        """
        job_id = str(uuid.uuid4())

        # Use provided created_at or default to now
        if created_at is None:
            created_at = datetime.utcnow()

        item = {
            'job_id': job_id,
            'user_id': user_id,
            'job_type': job_type,
            'status': 'pending',
            'created_at': created_at.isoformat(),
            'retry_count': 0
        }

        if audio_file_id:
            item['audio_file_id'] = audio_file_id

        self.jobs_table.put_item(Item=item)
        return job_id

    def update_job_status(self, job_id: str, status: str, error_message: Optional[str] = None):
        """Update processing job status."""
        update_expr = "SET #status = :status"
        expr_values = {":status": status}
        expr_names = {"#status": "status"}

        if status in ['completed', 'failed']:
            update_expr += ", completed_at = :completed_at"
            expr_values[":completed_at"] = datetime.utcnow().isoformat()

        if error_message:
            update_expr += ", error_message = :error_message"
            expr_values[":error_message"] = error_message

        self.jobs_table.update_item(
            Key={'job_id': job_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
            ExpressionAttributeNames=expr_names
        )

    def save_transcript_to_db(self, user_id: str, audio_file_id: str, transcript: str,
                             duration: float, s3_key: str) -> str:
        """Save transcript to DynamoDB with encryption."""
        transcript_id = str(uuid.uuid4())
        now = datetime.utcnow()

        # Get user's encryption key and encrypt transcript
        try:
            encryption_key = secrets_manager.get_user_encryption_key(user_id)
            if not encryption_key:
                error_msg = f"Encryption key not found for user {user_id}"
                logger.error(f"[ENCRYPT ERROR] {error_msg}")
                raise Exception(error_msg)

            # Encrypt transcript using AES-256-GCM
            encrypted_transcript_b64 = aes_encryption.encrypt_text(transcript, encryption_key)
            logger.info(f"[ENCRYPT] Transcript encrypted ({len(transcript)} bytes plaintext)")

        except Exception as e:
            logger.error(f"[ERROR] Failed to encrypt transcript: {e}", exc_info=True)
            raise

        item = {
            'transcript_id': transcript_id,
            'user_id': user_id,
            'audio_file_id': audio_file_id,
            'transcript': encrypted_transcript_b64,  # Store encrypted (base64)
            'length_in_seconds': Decimal(str(duration)),  # Convert float to Decimal for DynamoDB
            's3_key': s3_key,
            'created_at': now.isoformat()
        }

        self.transcripts_table.put_item(Item=item)
        logger.info(f"[SAVE] Encrypted transcript saved to DynamoDB: {transcript_id}")
        return transcript_id

    def process_audio_for_existing_job(self, job_id: str, user_id: str, audio_file_id: str) -> Optional[str]:
        """
        Process audio file using an EXISTING job (no duplicate job creation).
        Used by background processor.

        Args:
            job_id: Existing job ID to update
            user_id: User's UUID
            audio_file_id: Audio file UUID to process

        Returns:
            Transcript ID if successful, None otherwise
        """
        try:
            logger.info(f"[PROCESS] Job {job_id} starting for audio {audio_file_id}")
            self.update_job_status(job_id, 'processing')

            # Get audio file metadata
            logger.info(f"[FETCH] Retrieving audio file metadata")
            audio_service = AudioFileService()
            audio_file = audio_service.get_audio_file_by_id(audio_file_id)

            if not audio_file or audio_file.user_id != user_id:
                error_msg = 'Audio file not found or access denied'
                logger.error(f"[ERROR] {error_msg} - audio_id={audio_file_id}, user={user_id}")
                self.update_job_status(job_id, 'failed', error_msg)
                return None

            logger.info(f"[S3] Downloading from: {audio_file.s3_key}")

            # Download and decrypt audio file (now uses server-managed key)
            try:
                decrypted_file = self.download_and_decrypt_audio(
                    audio_file.s3_key,
                    user_id
                )
            except Exception as decrypt_error:
                error_msg = f"Decryption failed: {str(decrypt_error)}"
                logger.error(f"[DECRYPT ERROR] {error_msg}", exc_info=True)
                self.update_job_status(job_id, 'failed', error_msg)
                return None

            if not decrypted_file:
                error_msg = 'Failed to decrypt audio file'
                logger.error(f"[ERROR] {error_msg}")
                self.update_job_status(job_id, 'failed', error_msg)
                return None

            logger.info(f"[DECRYPT] Successfully decrypted to {decrypted_file}")

            try:
                # Check duration
                logger.info(f"[DURATION] Checking audio duration")
                duration = get_audio_duration(decrypted_file)
                logger.info(f"[DURATION] Audio duration: {duration}s (valid range: {backend_config.TRANSCRIPTION_MIN_DURATION_SECONDS}-{backend_config.TRANSCRIPTION_MAX_DURATION_SECONDS}s)")

                if duration < backend_config.TRANSCRIPTION_MIN_DURATION_SECONDS or duration > backend_config.TRANSCRIPTION_MAX_DURATION_SECONDS:
                    error_msg = f'Audio duration {duration}s outside valid range ({backend_config.TRANSCRIPTION_MIN_DURATION_SECONDS}-{backend_config.TRANSCRIPTION_MAX_DURATION_SECONDS}s)'
                    logger.error(f"[ERROR] {error_msg}")
                    self.update_job_status(job_id, 'failed', error_msg)
                    return None

                # Transcribe audio
                logger.info(f"[TRANSCRIBE] Sending to OpenAI Whisper...")
                transcript = transcribe_from_local(decrypted_file)
                logger.info(f"[TRANSCRIBE] Received transcript ({len(transcript) if transcript else 0} chars)")

                if not transcript or len(transcript.strip()) < 10:
                    logger.info(f"[SKIP] Audio too short or empty transcription - silently completing job")
                    # Mark as completed without error - short audio is expected and OK
                    self.update_job_status(job_id, 'completed')
                    return None

                # Save transcript to database
                logger.info(f"[SAVE] Saving transcript to database")
                transcript_id = self.save_transcript_to_db(
                    user_id, audio_file_id, transcript, duration, audio_file.s3_key
                )
                logger.info(f"[SAVE] Saved transcript {transcript_id}")

                # Record Whisper usage for cost tracking
                try:
                    duration_minutes = duration / 60.0
                    cost_service = get_cost_tracking_service()
                    success = cost_service.record_whisper_usage(user_id, duration_minutes)
                    if success:
                        logger.info(f"[COST] Recorded Whisper usage: {duration_minutes:.2f} minutes (${duration_minutes * 0.006:.4f})")
                    else:
                        logger.warning(f"[COST] Failed to record Whisper usage for user {user_id}")
                except Exception as cost_error:
                    logger.error(f"[COST ERROR] Failed to record cost: {str(cost_error)}", exc_info=True)

                self.update_job_status(job_id, 'completed')
                logger.info(f"[SUCCESS] Job {job_id} completed with transcript {transcript_id}")
                return transcript_id

            except Exception as processing_error:
                error_msg = f"Processing error: {str(processing_error)}"
                logger.error(f"[PROCESSING ERROR] {error_msg}", exc_info=True)
                self.update_job_status(job_id, 'failed', error_msg)
                return None

            finally:
                # Clean up decrypted file
                logger.info(f"[CLEANUP] Removing temporary decrypted file")
                if decrypted_file.exists():
                    decrypted_file.unlink()
                    logger.info(f"[CLEANUP] Temporary file removed")

        except Exception as e:
            error_msg = f"Job processing failed: {str(e)}"
            logger.error(f"[CRITICAL ERROR] {error_msg}", exc_info=True)
            self.update_job_status(job_id, 'failed', error_msg)
            return None

    def process_user_audio_file(self, user_id: str, audio_file_id: str) -> Optional[str]:
        """
        Process a single audio file for transcription.
        Creates a NEW job (for manual triggering).

        Args:
            user_id: User's UUID
            audio_file_id: Audio file UUID to process

        Returns:
            Transcript ID if successful, None otherwise
        """
        job_id = self.create_processing_job(user_id, 'transcription', audio_file_id)
        return self.process_audio_for_existing_job(job_id, user_id, audio_file_id)

    def get_user_transcripts(self, user_id: str, limit: int = 50) -> list[TranscriptUser]:
        """Get user's transcripts (decrypted)."""
        try:
            # Get user's encryption key for decryption
            encryption_key = secrets_manager.get_user_encryption_key(user_id)
            if not encryption_key:
                logger.error(f"[ERROR] Encryption key not found for user {user_id}")
                return []

            # Fetch MORE than limit to ensure we can sort and get the latest ones
            # This accounts for the fact that GSI sorts by transcript_id, not created_at
            fetch_limit = min(limit * 2, 100)  # Fetch 2x but cap at 100

            response = self.transcripts_table.query(
                IndexName='user-transcripts-index',
                KeyConditionExpression='user_id = :user_id',
                ExpressionAttributeValues={':user_id': user_id},
                Limit=fetch_limit,
                ScanIndexForward=False
            )

            transcripts = []
            for item in response['Items']:
                try:
                    # Decrypt transcript using user's encryption key
                    encrypted_transcript_b64 = item['transcript']
                    decrypted_transcript = aes_encryption.decrypt_text(encrypted_transcript_b64, encryption_key)
                    logger.info(f"[DECRYPT] Transcript decrypted for user {user_id}")

                    transcript = TranscriptUser(
                        transcript_id=item['transcript_id'],
                        user_id=item['user_id'],
                        audio_file_id=item['audio_file_id'],
                        transcript=decrypted_transcript,
                        length_in_seconds=float(item['length_in_seconds']),
                        s3_key=item['s3_key'],
                        created_at=datetime.fromisoformat(item['created_at'])
                    )
                    transcripts.append(transcript)

                except Exception as decrypt_error:
                    logger.error(f"[ERROR] Failed to decrypt transcript {item['transcript_id']}: {decrypt_error}", exc_info=True)
                    # Skip this transcript if decryption fails
                    continue

            # Sort by created_at descending (newest first) and limit
            transcripts_sorted = sorted(transcripts, key=lambda x: x.created_at, reverse=True)
            return transcripts_sorted[:limit]

        except Exception as e:
            logger.error(f"[ERROR] Error getting user transcripts: {e}", exc_info=True)
            return []

    def get_processing_jobs(self, user_id: str, limit: int = 20) -> list[ProcessingJob]:
        """Get user's processing jobs sorted by created_at (newest first)."""
        try:
            # Use GSI with created_at as sort key for efficient querying
            # This GSI allows DynamoDB to return results already sorted by timestamp
            response = self.jobs_table.query(
                IndexName='user-jobs-by-created-at',  # GSI with created_at sort key
                KeyConditionExpression='user_id = :user_id',
                ExpressionAttributeValues={':user_id': user_id},
                Limit=limit,  # Only fetch what we need
                ScanIndexForward=False  # Latest first (by created_at)
            )

            jobs = []
            for item in response['Items']:
                # Skip daily_summary jobs - they're managed automatically and not shown to users
                if item.get('job_type') == 'daily_summary':
                    continue

                # Parse created_at from ISO string
                # Handle both with and without 'Z' suffix for Java compatibility
                created_at_str = item['created_at']
                if not created_at_str.endswith(('Z', '+00:00')):
                    created_at_str += 'Z'  # Add 'Z' for UTC timezone awareness
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))

                # Parse completed_at (optional)
                completed_at = None
                if 'completed_at' in item:
                    completed_at_str = item['completed_at']
                    if not completed_at_str.endswith(('Z', '+00:00')):
                        completed_at_str += 'Z'  # Add 'Z' for UTC timezone awareness
                    completed_at = datetime.fromisoformat(completed_at_str.replace('Z', '+00:00'))

                job = ProcessingJob(
                    job_id=item['job_id'],
                    user_id=item['user_id'],
                    job_type=item['job_type'],
                    audio_file_id=item.get('audio_file_id'),
                    status=item['status'],
                    created_at=created_at,
                    completed_at=completed_at,
                    error_message=item.get('error_message')
                )
                jobs.append(job)

            # Results are already sorted by created_at (newest first) from DynamoDB GSI
            return jobs

        except Exception as e:
            print(f"Error getting processing jobs: {e}")
            return []