"""
Service for managing daily summary tracking in DynamoDB.

Tracks which users have had their daily summary scheduled for each day,
ensuring we don't create duplicate jobs and surviving server restarts.
"""

import boto3
from datetime import datetime, timedelta
from typing import List, Optional
import logging

from decision_data.backend.config.config import backend_config

logger = logging.getLogger(__name__)


class DailySummaryTrackingService:
    """Service for tracking daily summary scheduling status."""

    def __init__(self):
        self.dynamodb = boto3.resource(
            'dynamodb',
            region_name=backend_config.REGION_NAME,
            aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY
        )
        self.table_name = 'panzoto-daily-summary-tracking'
        self.table = self.dynamodb.Table(self.table_name)

    def mark_summary_scheduled(self, user_id: str, job_id: str, date_str: str = None) -> bool:
        """
        Mark that a daily summary has been scheduled for a user on a specific date.

        Args:
            user_id: User's UUID
            job_id: The processing job ID created for the summary
            date_str: Date in YYYYMMDD format (defaults to today UTC)

        Returns:
            True if successful, False otherwise
        """
        try:
            if date_str is None:
                date_str = datetime.utcnow().strftime('%Y%m%d')

            # Calculate TTL (30 days from now)
            ttl = int((datetime.utcnow() + timedelta(days=30)).timestamp())

            item = {
                'user_id': user_id,
                'date': date_str,
                'job_id': job_id,
                'status': 'scheduled',
                'created_at': datetime.utcnow().isoformat() + 'Z',
                'ttl': ttl
            }

            self.table.put_item(Item=item)
            logger.info(f"[TRACKING] Marked summary scheduled for user {user_id} on {date_str} (job: {job_id})")
            return True

        except Exception as e:
            logger.error(f"[TRACKING] Failed to mark summary scheduled for user {user_id}: {e}", exc_info=True)
            return False

    def is_summary_scheduled_today(self, user_id: str, date_str: str = None) -> bool:
        """
        Check if a daily summary has already been scheduled for a user today.

        Args:
            user_id: User's UUID
            date_str: Date in YYYYMMDD format (defaults to today UTC)

        Returns:
            True if summary already scheduled, False otherwise
        """
        try:
            if date_str is None:
                date_str = datetime.utcnow().strftime('%Y%m%d')

            response = self.table.get_item(
                Key={
                    'user_id': user_id,
                    'date': date_str
                }
            )

            is_scheduled = 'Item' in response
            if is_scheduled:
                logger.debug(f"[TRACKING] Summary already scheduled for user {user_id} on {date_str}")
            return is_scheduled

        except Exception as e:
            logger.error(f"[TRACKING] Error checking if summary scheduled for {user_id}: {e}", exc_info=True)
            return False

    def get_today_scheduled_users(self, date_str: str = None) -> List[str]:
        """
        Get list of users who have had summaries scheduled today.

        Args:
            date_str: Date in YYYYMMDD format (defaults to today UTC)

        Returns:
            List of user IDs
        """
        try:
            if date_str is None:
                date_str = datetime.utcnow().strftime('%Y%m%d')

            response = self.table.query(
                IndexName='date-index' if self._has_gsi() else None,
                KeyConditionExpression='#date = :date',
                ExpressionAttributeNames={'#date': 'date'},
                ExpressionAttributeValues={':date': date_str}
            )

            user_ids = [item['user_id'] for item in response.get('Items', [])]
            logger.debug(f"[TRACKING] Found {len(user_ids)} users with scheduled summaries on {date_str}")
            return user_ids

        except Exception as e:
            # If GSI doesn't exist, fall back to returning empty list
            logger.debug(f"[TRACKING] Could not query by date: {e}")
            return []

    def reset_daily_tracking(self, date_str: str = None):
        """
        Load today's scheduled summaries from DB into memory (on scheduler startup).

        This is called when the scheduler starts to populate the in-memory cache
        with any summaries that were already scheduled.

        Args:
            date_str: Date in YYYYMMDD format (defaults to today UTC)

        Returns:
            Dictionary mapping user_id -> date
        """
        try:
            if date_str is None:
                date_str = datetime.utcnow().strftime('%Y%m%d')

            logger.info(f"[TRACKING] Loading today's scheduled summaries from database for {date_str}")

            # Query by GSI on date (if available)
            response = self.table.scan(
                FilterExpression='#date = :date AND #status = :status',
                ExpressionAttributeNames={
                    '#date': 'date',
                    '#status': 'status'
                },
                ExpressionAttributeValues={
                    ':date': date_str,
                    ':status': 'scheduled'
                }
            )

            scheduled_users = {}
            for item in response.get('Items', []):
                user_id = item['user_id']
                scheduled_users[user_id] = datetime.strptime(item['date'], '%Y%m%d').date()

            logger.info(f"[TRACKING] Loaded {len(scheduled_users)} today's scheduled summaries from DB")
            return scheduled_users

        except Exception as e:
            logger.error(f"[TRACKING] Error loading today's summaries from DB: {e}", exc_info=True)
            return {}

    def mark_summary_completed(self, user_id: str, job_id: str, date_str: str = None):
        """
        Mark that a daily summary has been completed (email sent).

        Args:
            user_id: User's UUID
            job_id: The processing job ID
            date_str: Date in YYYYMMDD format (defaults to today UTC)
        """
        try:
            if date_str is None:
                date_str = datetime.utcnow().strftime('%Y%m%d')

            self.table.update_item(
                Key={
                    'user_id': user_id,
                    'date': date_str
                },
                UpdateExpression='SET #status = :status, completed_at = :completed_at',
                ExpressionAttributeNames={
                    '#status': 'status'
                },
                ExpressionAttributeValues={
                    ':status': 'completed',
                    ':completed_at': datetime.utcnow().isoformat() + 'Z'
                }
            )
            logger.info(f"[TRACKING] Marked summary completed for user {user_id} on {date_str}")

        except Exception as e:
            logger.error(f"[TRACKING] Failed to mark summary completed for {user_id}: {e}", exc_info=True)

    def mark_summary_failed(self, user_id: str, job_id: str, error_message: str = None, date_str: str = None):
        """
        Mark that a daily summary failed to send.

        Args:
            user_id: User's UUID
            job_id: The processing job ID
            error_message: Error message
            date_str: Date in YYYYMMDD format (defaults to today UTC)
        """
        try:
            if date_str is None:
                date_str = datetime.utcnow().strftime('%Y%m%d')

            update_expr = 'SET #status = :status, failed_at = :failed_at'
            expr_values = {
                ':status': 'failed',
                ':failed_at': datetime.utcnow().isoformat() + 'Z'
            }

            if error_message:
                update_expr += ', error_message = :error'
                expr_values[':error'] = error_message

            self.table.update_item(
                Key={
                    'user_id': user_id,
                    'date': date_str
                },
                UpdateExpression=update_expr,
                ExpressionAttributeNames={
                    '#status': 'status'
                },
                ExpressionAttributeValues=expr_values
            )
            logger.warning(f"[TRACKING] Marked summary failed for user {user_id} on {date_str}: {error_message}")

        except Exception as e:
            logger.error(f"[TRACKING] Failed to mark summary failed for {user_id}: {e}", exc_info=True)

    def _has_gsi(self) -> bool:
        """Check if GSI on date exists (for optimization)."""
        try:
            table_description = self.table.meta.client.describe_table(TableName=self.table_name)
            gsis = table_description.get('Table', {}).get('GlobalSecondaryIndexes', [])
            return any(gsi['IndexName'] == 'date-index' for gsi in gsis)
        except:
            return False
