"""User-specific transcription service that handles encrypted audio files."""

import uuid
import boto3
from pathlib import Path
from datetime import datetime
from typing import Optional
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Hash import SHA256
import io
import tempfile
import base64
from botocore.exceptions import ClientError

from decision_data.backend.config.config import backend_config
from decision_data.backend.transcribe.whisper import transcribe_from_local, get_audio_duration
from decision_data.backend.services.audio_service import AudioFileService
from decision_data.backend.services.user_service import UserService
from decision_data.backend.utils.secrets_manager import secrets_manager
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
        import logging
        logging.info(f"[DECRYPT] Starting decryption for s3_key={s3_key}, user_id={user_id}")

        try:
            # Get user's encryption key from Secrets Manager
            encryption_key = secrets_manager.get_user_encryption_key(user_id)
            logging.info(f"[KEY] Got encryption key for user {user_id}: {encryption_key[:20] if encryption_key else 'None'}...")
            if not encryption_key:
                logging.error(f"[ERROR] Encryption key not found for user {user_id}")
                print(f"Encryption key not found for user {user_id}")
                return None

            # Download encrypted file from S3
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            encrypted_data = response['Body'].read()

            # Decrypt the data
            decrypted_data = self.decrypt_audio_file(encrypted_data, encryption_key)

            # Save decrypted data to temporary file
            temp_dir = Path("data/processing_audio")
            temp_dir.mkdir(parents=True, exist_ok=True)

            # Create temporary file with .3gp extension
            temp_file = temp_dir / f"decrypted_{uuid.uuid4().hex}.3gp"
            with open(temp_file, 'wb') as f:
                f.write(decrypted_data)

            return temp_file

        except Exception as e:
            import logging
            logging.error(f"[ERROR] Error downloading and decrypting audio: {e}", exc_info=True)
            print(f"Error downloading and decrypting audio: {e}")
            return None

    def create_processing_job(self, user_id: str, job_type: str, audio_file_id: Optional[str] = None) -> str:
        """Create a processing job record."""
        job_id = str(uuid.uuid4())
        now = datetime.utcnow()

        item = {
            'job_id': job_id,
            'user_id': user_id,
            'job_type': job_type,
            'status': 'pending',
            'created_at': now.isoformat(),
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
        """Save transcript to DynamoDB."""
        transcript_id = str(uuid.uuid4())
        now = datetime.utcnow()

        item = {
            'transcript_id': transcript_id,
            'user_id': user_id,
            'audio_file_id': audio_file_id,
            'transcript': transcript,
            'length_in_seconds': duration,
            's3_key': s3_key,
            'created_at': now.isoformat()
        }

        self.transcripts_table.put_item(Item=item)
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
            self.update_job_status(job_id, 'processing')

            # Get audio file metadata
            audio_service = AudioFileService()
            audio_file = audio_service.get_audio_file_by_id(audio_file_id)

            if not audio_file or audio_file.user_id != user_id:
                self.update_job_status(job_id, 'failed', 'Audio file not found or access denied')
                return None

            # Download and decrypt audio file (now uses server-managed key)
            decrypted_file = self.download_and_decrypt_audio(
                audio_file.s3_key,
                user_id
            )

            if not decrypted_file:
                self.update_job_status(job_id, 'failed', 'Failed to decrypt audio file')
                return None

            try:
                # Check duration
                duration = get_audio_duration(decrypted_file)
                if duration < backend_config.TRANSCRIPTION_MIN_DURATION_SECONDS or duration > backend_config.TRANSCRIPTION_MAX_DURATION_SECONDS:
                    self.update_job_status(job_id, 'failed', f'Audio duration {duration}s outside valid range')
                    return None

                # Transcribe audio
                transcript = transcribe_from_local(decrypted_file)

                if not transcript or len(transcript.strip()) < 10:
                    self.update_job_status(job_id, 'failed', 'Transcription failed or too short')
                    return None

                # Save transcript to database
                transcript_id = self.save_transcript_to_db(
                    user_id, audio_file_id, transcript, duration, audio_file.s3_key
                )

                self.update_job_status(job_id, 'completed')
                return transcript_id

            finally:
                # Clean up decrypted file
                if decrypted_file.exists():
                    decrypted_file.unlink()

        except Exception as e:
            self.update_job_status(job_id, 'failed', str(e))
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
        """Get user's transcripts."""
        try:
            response = self.transcripts_table.query(
                IndexName='user-transcripts-index',
                KeyConditionExpression='user_id = :user_id',
                ExpressionAttributeValues={':user_id': user_id},
                Limit=limit,
                ScanIndexForward=False  # Latest first
            )

            transcripts = []
            for item in response['Items']:
                transcript = TranscriptUser(
                    transcript_id=item['transcript_id'],
                    user_id=item['user_id'],
                    audio_file_id=item['audio_file_id'],
                    transcript=item['transcript'],
                    length_in_seconds=float(item['length_in_seconds']),
                    s3_key=item['s3_key'],
                    created_at=datetime.fromisoformat(item['created_at'])
                )
                transcripts.append(transcript)

            return transcripts

        except Exception as e:
            print(f"Error getting user transcripts: {e}")
            return []

    def get_processing_jobs(self, user_id: str, limit: int = 20) -> list[ProcessingJob]:
        """Get user's processing jobs."""
        try:
            response = self.jobs_table.query(
                IndexName='user-jobs-index',
                KeyConditionExpression='user_id = :user_id',
                ExpressionAttributeValues={':user_id': user_id},
                Limit=limit,
                ScanIndexForward=False  # Latest first
            )

            jobs = []
            for item in response['Items']:
                completed_at = None
                if 'completed_at' in item:
                    completed_at = datetime.fromisoformat(item['completed_at'])

                job = ProcessingJob(
                    job_id=item['job_id'],
                    user_id=item['user_id'],
                    job_type=item['job_type'],
                    audio_file_id=item.get('audio_file_id'),
                    status=item['status'],
                    created_at=datetime.fromisoformat(item['created_at']),
                    completed_at=completed_at,
                    error_message=item.get('error_message')
                )
                jobs.append(job)

            return jobs

        except Exception as e:
            print(f"Error getting processing jobs: {e}")
            return []