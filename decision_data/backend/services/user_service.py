"""User management service using DynamoDB"""

import boto3
import uuid
import base64
from datetime import datetime
from typing import Optional
from botocore.exceptions import ClientError
from loguru import logger

from decision_data.backend.config.config import backend_config
from decision_data.data_structure.models import User, UserCreate, UserLogin
from decision_data.backend.utils.auth import hash_password, verify_password, generate_key_salt
from decision_data.backend.utils.secrets_manager import secrets_manager


class UserService:
    def __init__(self):
        self.dynamodb = boto3.resource(
            'dynamodb',
            region_name=backend_config.REGION_NAME,
            aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY
        )
        self.users_table = self.dynamodb.Table(backend_config.USERS_TABLE)

    def create_user(self, user_data: UserCreate) -> Optional[User]:
        """Create new user"""
        try:
            # Check if user already exists
            existing_user = self.get_user_by_email(user_data.email)
            if existing_user:
                return None

            # Create new user
            user_id = str(uuid.uuid4())
            password_hash = hash_password(user_data.password)
            key_salt = generate_key_salt()
            created_at = datetime.utcnow()

            # Convert bytes to base64 string for DynamoDB storage
            key_salt_b64 = base64.b64encode(key_salt).decode('utf-8')

            # Generate and store encryption key in AWS Secrets Manager
            try:
                secrets_manager.store_user_encryption_key(user_id)
                logger.info(f"Created encryption key for user {user_id}")
            except Exception as e:
                logger.error(f"Failed to create encryption key for user {user_id}: {e}")
                # Don't fail user creation if key storage fails
                # User can still be created, but won't be able to encrypt files yet

            self.users_table.put_item(
                Item={
                    'user_id': user_id,
                    'email': user_data.email.lower().strip(),
                    'password_hash': password_hash,
                    'key_salt': key_salt_b64,
                    'created_at': int(created_at.timestamp()),
                    'created_at_iso': created_at.isoformat()
                }
            )

            return User(
                user_id=user_id,
                email=user_data.email.lower().strip(),
                password_hash=password_hash,
                key_salt=key_salt.hex(),
                created_at=created_at
            )

        except ClientError as e:
            logger.error(f"Error creating user: {e}")
            return None

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        try:
            response = self.users_table.get_item(Key={'user_id': user_id})
            if 'Item' in response:
                return self._from_dynamodb_item(response['Item'])
            return None
        except ClientError as e:
            logger.error(f"Error getting user by ID: {e}")
            return None

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email using GSI"""
        try:
            response = self.users_table.query(
                IndexName='email-index',
                KeyConditionExpression='email = :email',
                ExpressionAttributeValues={':email': email.lower().strip()}
            )
            if response['Items']:
                return self._from_dynamodb_item(response['Items'][0])
            return None
        except ClientError as e:
            logger.error(f"Error getting user by email: {e}")
            return None

    def authenticate_user(self, login_data: UserLogin) -> Optional[User]:
        """Authenticate user with email and password"""
        user = self.get_user_by_email(login_data.email)
        if not user or not user.password_hash:
            return None

        if verify_password(login_data.password, user.password_hash):
            return user
        return None

    def get_user_encryption_key(self, user_id: str) -> Optional[str]:
        """
        Get user's encryption key from AWS Secrets Manager.

        Args:
            user_id: User's UUID

        Returns:
            Base64-encoded encryption key
        """
        try:
            return secrets_manager.get_user_encryption_key(user_id)
        except Exception as e:
            logger.error(f"Failed to retrieve encryption key for user {user_id}: {e}")
            return None

    def _from_dynamodb_item(self, item: dict) -> User:
        """Convert DynamoDB item to User object"""
        # Convert base64 string back to bytes, then to hex
        key_salt = base64.b64decode(item['key_salt']).hex() if item.get('key_salt') else None
        # Handle Decimal objects from DynamoDB
        created_at_timestamp = float(item.get('created_at', 0))
        created_at = datetime.fromtimestamp(created_at_timestamp)

        return User(
            user_id=item['user_id'],
            email=item['email'],
            password_hash=item.get('password_hash'),
            key_salt=key_salt,
            created_at=created_at
        )