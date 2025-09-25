"""Audio file management service using DynamoDB"""

import boto3
import uuid
from datetime import datetime
from typing import Optional, List
from botocore.exceptions import ClientError
from loguru import logger

from decision_data.backend.config.config import backend_config
from decision_data.data_structure.models import AudioFile, AudioFileCreate


class AudioFileService:
    def __init__(self):
        self.dynamodb = boto3.resource(
            'dynamodb',
            region_name=backend_config.REGION_NAME,
            aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY
        )
        self.audio_files_table = self.dynamodb.Table(backend_config.AUDIO_FILES_TABLE)

    def create_audio_file(self, user_id: str, file_data: AudioFileCreate) -> Optional[AudioFile]:
        """Create new audio file record"""
        try:
            file_id = str(uuid.uuid4())
            uploaded_at = datetime.utcnow()

            self.audio_files_table.put_item(
                Item={
                    'file_id': file_id,
                    'user_id': user_id,
                    's3_key': file_data.s3_key,
                    'file_size': file_data.file_size,
                    'uploaded_at': int(uploaded_at.timestamp()),
                    'uploaded_at_iso': uploaded_at.isoformat()
                }
            )

            return AudioFile(
                file_id=file_id,
                user_id=user_id,
                s3_key=file_data.s3_key,
                file_size=file_data.file_size,
                uploaded_at=uploaded_at
            )

        except ClientError as e:
            logger.error(f"Error creating audio file: {e}")
            return None

    def get_audio_file_by_id(self, file_id: str) -> Optional[AudioFile]:
        """Get audio file by ID"""
        try:
            response = self.audio_files_table.get_item(Key={'file_id': file_id})
            if 'Item' in response:
                return self._from_dynamodb_item(response['Item'])
            return None
        except ClientError as e:
            logger.error(f"Error getting audio file by ID: {e}")
            return None

    def get_user_audio_files(self, user_id: str, limit: int = 50) -> List[AudioFile]:
        """Get audio files for a user, ordered by upload time (newest first)"""
        try:
            response = self.audio_files_table.query(
                IndexName='user-files-index',
                KeyConditionExpression='user_id = :user_id',
                ExpressionAttributeValues={':user_id': user_id},
                ScanIndexForward=False,  # Sort descending (newest first)
                Limit=limit
            )
            return [self._from_dynamodb_item(item) for item in response['Items']]
        except ClientError as e:
            logger.error(f"Error getting audio files for user: {e}")
            return []

    def get_audio_file_by_s3_key(self, s3_key: str, user_id: str) -> Optional[AudioFile]:
        """Get audio file by S3 key and user ID"""
        try:
            # Since we can't query by s3_key directly, we need to scan (expensive for large datasets)
            # In production, consider adding another GSI if this query is frequent
            response = self.audio_files_table.scan(
                FilterExpression='s3_key = :s3_key AND user_id = :user_id',
                ExpressionAttributeValues={
                    ':s3_key': s3_key,
                    ':user_id': user_id
                },
                Limit=1
            )
            if response['Items']:
                return self._from_dynamodb_item(response['Items'][0])
            return None
        except ClientError as e:
            logger.error(f"Error getting audio file by S3 key: {e}")
            return None

    def delete_audio_file(self, file_id: str, user_id: str) -> bool:
        """Delete audio file record (only if owned by user)"""
        try:
            # First verify the file belongs to the user
            audio_file = self.get_audio_file_by_id(file_id)
            if not audio_file or audio_file.user_id != user_id:
                return False

            self.audio_files_table.delete_item(Key={'file_id': file_id})
            return True

        except ClientError as e:
            logger.error(f"Error deleting audio file: {e}")
            return False

    def _from_dynamodb_item(self, item: dict) -> AudioFile:
        """Convert DynamoDB item to AudioFile object"""
        # Handle Decimal objects from DynamoDB
        uploaded_at_timestamp = float(item.get('uploaded_at', 0))
        uploaded_at = datetime.fromtimestamp(uploaded_at_timestamp)

        return AudioFile(
            file_id=item['file_id'],
            user_id=item['user_id'],
            s3_key=item['s3_key'],
            file_size=item.get('file_size'),
            uploaded_at=uploaded_at
        )