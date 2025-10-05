"""AWS Secrets Manager integration for encryption keys."""

import boto3
import json
import secrets
import base64
from typing import Optional
from botocore.exceptions import ClientError
import logging

from decision_data.backend.config.config import backend_config

logger = logging.getLogger(__name__)


class SecretsManager:
    """Manage encryption keys using AWS Secrets Manager."""

    def __init__(self):
        self.client = boto3.client(
            'secretsmanager',
            region_name=backend_config.REGION_NAME,
            aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY
        )
        self.key_prefix = "panzoto/encryption-keys/"

    def generate_encryption_key(self) -> str:
        """
        Generate a new 256-bit encryption key.

        Returns:
            Base64-encoded encryption key
        """
        # Generate 32 bytes (256 bits) for AES-256
        key_bytes = secrets.token_bytes(32)
        return base64.b64encode(key_bytes).decode('utf-8')

    def store_user_encryption_key(self, user_id: str) -> str:
        """
        Generate and store a new encryption key for a user.

        Args:
            user_id: User's UUID

        Returns:
            The secret ARN/name for reference
        """
        secret_name = f"{self.key_prefix}{user_id}"
        encryption_key = self.generate_encryption_key()

        secret_data = {
            "user_id": user_id,
            "encryption_key": encryption_key,
            "version": "1"
        }

        try:
            # Try to create new secret
            response = self.client.create_secret(
                Name=secret_name,
                Description=f"Encryption key for user {user_id}",
                SecretString=json.dumps(secret_data),
                Tags=[
                    {'Key': 'Application', 'Value': 'Panzoto'},
                    {'Key': 'Purpose', 'Value': 'AudioFileEncryption'},
                    {'Key': 'UserId', 'Value': user_id}
                ]
            )
            logger.info(f"Created new encryption key for user {user_id}")
            return secret_name

        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceExistsException':
                # Secret already exists, update it
                logger.warning(f"Secret already exists for user {user_id}, updating...")
                self.client.update_secret(
                    SecretId=secret_name,
                    SecretString=json.dumps(secret_data)
                )
                return secret_name
            else:
                logger.error(f"Error storing encryption key: {e}")
                raise

    def get_user_encryption_key(self, user_id: str) -> Optional[str]:
        """
        Retrieve a user's encryption key from Secrets Manager.

        Args:
            user_id: User's UUID

        Returns:
            Base64-encoded encryption key, or None if not found
        """
        secret_name = f"{self.key_prefix}{user_id}"

        try:
            response = self.client.get_secret_value(SecretId=secret_name)
            secret_data = json.loads(response['SecretString'])
            return secret_data['encryption_key']

        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                logger.warning(f"Encryption key not found for user {user_id}")
                return None
            else:
                logger.error(f"Error retrieving encryption key: {e}")
                raise

    def delete_user_encryption_key(self, user_id: str):
        """
        Delete a user's encryption key (with recovery window).

        Args:
            user_id: User's UUID
        """
        secret_name = f"{self.key_prefix}{user_id}"

        try:
            self.client.delete_secret(
                SecretId=secret_name,
                RecoveryWindowInDays=30  # Allow 30-day recovery
            )
            logger.info(f"Scheduled deletion of encryption key for user {user_id}")

        except ClientError as e:
            logger.error(f"Error deleting encryption key: {e}")
            raise

    def rotate_user_encryption_key(self, user_id: str) -> str:
        """
        Generate a new encryption key for a user (for key rotation).

        Note: This creates a new key but doesn't re-encrypt existing files.
        You would need to implement a migration process for that.

        Args:
            user_id: User's UUID

        Returns:
            New encryption key
        """
        secret_name = f"{self.key_prefix}{user_id}"
        new_key = self.generate_encryption_key()

        # Get existing secret to preserve metadata
        try:
            response = self.client.get_secret_value(SecretId=secret_name)
            secret_data = json.loads(response['SecretString'])

            # Increment version
            old_version = int(secret_data.get('version', '1'))
            new_version = old_version + 1

            # Store old key in history (optional, for re-encryption)
            secret_data['previous_key'] = secret_data['encryption_key']
            secret_data['encryption_key'] = new_key
            secret_data['version'] = str(new_version)

            self.client.update_secret(
                SecretId=secret_name,
                SecretString=json.dumps(secret_data)
            )

            logger.info(f"Rotated encryption key for user {user_id} to version {new_version}")
            return new_key

        except ClientError as e:
            logger.error(f"Error rotating encryption key: {e}")
            raise


# Singleton instance
secrets_manager = SecretsManager()
