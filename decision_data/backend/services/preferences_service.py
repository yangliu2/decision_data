"""User preferences service for managing user settings and configurations."""

import uuid
from datetime import datetime
from typing import Optional
import boto3
from botocore.exceptions import ClientError
from decimal import Decimal

from decision_data.backend.config.config import backend_config
from decision_data.data_structure.models import (
    UserPreferences,
    UserPreferencesCreate,
    UserPreferencesUpdate
)


class UserPreferencesService:
    """Service for managing user preferences in DynamoDB."""

    def __init__(self):
        self.dynamodb = boto3.resource(
            'dynamodb',
            region_name=backend_config.REGION_NAME,
            aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY
        )
        self.table_name = 'panzoto-user-preferences'
        self.table = self.dynamodb.Table(self.table_name)

    def create_preferences(self, user_id: str, preferences_data: UserPreferencesCreate) -> Optional[UserPreferences]:
        """Create new user preferences."""
        try:
            now = datetime.utcnow()

            # Check if preferences already exist
            existing = self.get_preferences(user_id)
            if existing:
                return None  # Preferences already exist

            item = {
                'user_id': user_id,
                'notification_email': preferences_data.notification_email,
                'enable_daily_summary': preferences_data.enable_daily_summary,
                'enable_transcription': preferences_data.enable_transcription,
                'summary_time_utc': preferences_data.summary_time_utc,
                'created_at': Decimal(str(now.timestamp())),
                'updated_at': Decimal(str(now.timestamp()))
            }

            self.table.put_item(Item=item)

            return UserPreferences(
                user_id=user_id,
                notification_email=preferences_data.notification_email,
                enable_daily_summary=preferences_data.enable_daily_summary,
                enable_transcription=preferences_data.enable_transcription,
                summary_time_utc=preferences_data.summary_time_utc,
                created_at=now,
                updated_at=now
            )

        except ClientError as e:
            print(f"Error creating user preferences: {e}")
            return None

    def get_preferences(self, user_id: str) -> Optional[UserPreferences]:
        """Get user preferences by user ID."""
        try:
            response = self.table.get_item(Key={'user_id': user_id})

            if 'Item' in response:
                item = response['Item']
                return UserPreferences(
                    user_id=item['user_id'],
                    notification_email=item['notification_email'],
                    enable_daily_summary=item['enable_daily_summary'],
                    enable_transcription=item['enable_transcription'],
                    summary_time_utc=item['summary_time_utc'],
                    created_at=datetime.fromtimestamp(float(item['created_at'])),
                    updated_at=datetime.fromtimestamp(float(item['updated_at']))
                )
            return None

        except ClientError as e:
            print(f"Error getting user preferences: {e}")
            return None

    def update_preferences(self, user_id: str, update_data: UserPreferencesUpdate) -> Optional[UserPreferences]:
        """Update user preferences."""
        try:
            now = datetime.utcnow()

            # Build update expression
            update_expr = "SET updated_at = :updated_at"
            expr_values = {":updated_at": Decimal(str(now.timestamp()))}

            if update_data.notification_email is not None:
                update_expr += ", notification_email = :email"
                expr_values[":email"] = update_data.notification_email

            if update_data.enable_daily_summary is not None:
                update_expr += ", enable_daily_summary = :daily_summary"
                expr_values[":daily_summary"] = update_data.enable_daily_summary

            if update_data.enable_transcription is not None:
                update_expr += ", enable_transcription = :transcription"
                expr_values[":transcription"] = update_data.enable_transcription

            if update_data.summary_time_utc is not None:
                update_expr += ", summary_time_utc = :summary_time"
                expr_values[":summary_time"] = update_data.summary_time_utc

            self.table.update_item(
                Key={'user_id': user_id},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_values
            )

            # Return updated preferences
            return self.get_preferences(user_id)

        except ClientError as e:
            print(f"Error updating user preferences: {e}")
            return None

    def delete_preferences(self, user_id: str) -> bool:
        """Delete user preferences."""
        try:
            self.table.delete_item(Key={'user_id': user_id})
            return True

        except ClientError as e:
            print(f"Error deleting user preferences: {e}")
            return False

    def get_users_with_daily_summary_enabled(self) -> list[UserPreferences]:
        """Get all users who have daily summary enabled."""
        try:
            response = self.table.scan(
                FilterExpression='enable_daily_summary = :enabled',
                ExpressionAttributeValues={':enabled': True}
            )

            preferences_list = []
            for item in response['Items']:
                preferences = UserPreferences(
                    user_id=item['user_id'],
                    notification_email=item['notification_email'],
                    enable_daily_summary=item['enable_daily_summary'],
                    enable_transcription=item['enable_transcription'],
                    summary_time_utc=item['summary_time_utc'],
                    created_at=datetime.fromtimestamp(float(item['created_at'])),
                    updated_at=datetime.fromtimestamp(float(item['updated_at']))
                )
                preferences_list.append(preferences)

            return preferences_list

        except ClientError as e:
            print(f"Error getting users with daily summary enabled: {e}")
            return []