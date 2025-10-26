"""
Daily Summary Retrieval Service

Handles retrieving and decrypting daily summaries for users.
"""

import boto3
import json
import logging
from typing import List, Optional
from decimal import Decimal
from datetime import datetime

from decision_data.backend.config.config import backend_config
from decision_data.backend.utils.secrets_manager import SecretsManager
from decision_data.backend.utils.aes_encryption import AESEncryption
from decision_data.data_structure.models import DailySummary, DailySummaryResponse

logger = logging.getLogger(__name__)

# Initialize encryption/decryption utilities
secrets_manager = SecretsManager()
aes_encryption = AESEncryption()


class SummaryRetrievalService:
    """Service for retrieving and decrypting daily summaries."""

    def __init__(self):
        self.dynamodb = boto3.resource(
            'dynamodb',
            region_name=backend_config.REGION_NAME,
            aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY
        )
        self.table = self.dynamodb.Table('panzoto-daily-summaries')

    def get_user_summaries(self, user_id: str, limit: int = 50) -> List[DailySummaryResponse]:
        """Get all summaries for a user, decrypted.

        Args:
            user_id: User ID to fetch summaries for
            limit: Maximum number of summaries to return

        Returns:
            List of decrypted DailySummaryResponse objects
        """
        try:
            # Query summaries for this user (using GSI)
            response = self.table.query(
                IndexName='user-date-index',
                KeyConditionExpression='user_id = :user_id',
                ExpressionAttributeValues={':user_id': user_id},
                Limit=limit,
                ScanIndexForward=False  # Most recent first
            )

            items = response.get('Items', [])
            logger.info(f"[RETRIEVE] Found {len(items)} summaries for user {user_id}")

            # Get encryption key for user
            encryption_key = None
            try:
                encryption_key = secrets_manager.get_user_encryption_key(user_id)
                if not encryption_key:
                    logger.warning(f"[DECRYPT] No encryption key found for user {user_id}")
            except Exception as e:
                logger.warning(f"[DECRYPT] Failed to get encryption key: {e}")

            decrypted_summaries = []

            # Decrypt each summary
            for item in items:
                try:
                    summary_id = item.get('summary_id')
                    summary_date = item.get('summary_date')

                    # Try to decrypt
                    encrypted_summary_b64 = item.get('encrypted_summary')
                    summary_json = None

                    if encrypted_summary_b64 and encryption_key:
                        try:
                            summary_json = aes_encryption.decrypt_text(
                                encrypted_summary_b64,
                                encryption_key
                            )
                            logger.debug(f"[DECRYPT] Successfully decrypted summary {summary_id}")
                        except Exception as decrypt_error:
                            logger.error(f"[DECRYPT] Failed to decrypt summary {summary_id}: {decrypt_error}")
                            # Try fallback to unencrypted field
                            summary_json = item.get('summary')
                    else:
                        # Fallback to unencrypted field
                        summary_json = item.get('summary')

                    if not summary_json:
                        logger.warning(f"[RETRIEVE] No summary data found for {summary_id}")
                        continue

                    # Parse the JSON
                    summary_data = json.loads(summary_json)

                    # Create response object
                    response_obj = DailySummaryResponse(
                        summary_id=summary_id,
                        summary_date=summary_date,
                        family_info=summary_data.get('family_info', []),
                        business_info=summary_data.get('business_info', []),
                        misc_info=summary_data.get('misc_info', []),
                        created_at=datetime.fromisoformat(item.get('created_at'))
                    )

                    decrypted_summaries.append(response_obj)

                except Exception as e:
                    logger.error(f"[RETRIEVE] Failed to process summary: {e}", exc_info=True)
                    continue

            return decrypted_summaries

        except Exception as e:
            logger.error(f"[RETRIEVE] Failed to get summaries for user {user_id}: {e}", exc_info=True)
            raise

    def get_summary_by_date(
        self,
        user_id: str,
        summary_date: str
    ) -> Optional[DailySummaryResponse]:
        """Get a specific summary for a user by date (YYYY-MM-DD format).

        Args:
            user_id: User ID
            summary_date: Summary date in YYYY-MM-DD format

        Returns:
            Decrypted DailySummaryResponse or None if not found
        """
        try:
            # Query summaries for this user and date
            response = self.table.query(
                IndexName='user-date-index',
                KeyConditionExpression='user_id = :user_id AND summary_date = :date',
                ExpressionAttributeValues={
                    ':user_id': user_id,
                    ':date': summary_date
                },
                Limit=1
            )

            items = response.get('Items', [])
            if not items:
                logger.info(f"[RETRIEVE] No summary found for user {user_id} on {summary_date}")
                return None

            item = items[0]

            # Get encryption key
            encryption_key = None
            try:
                encryption_key = secrets_manager.get_user_encryption_key(user_id)
            except Exception as e:
                logger.warning(f"[DECRYPT] Failed to get encryption key: {e}")

            # Decrypt summary
            encrypted_summary_b64 = item.get('encrypted_summary')
            summary_json = None

            if encrypted_summary_b64 and encryption_key:
                try:
                    summary_json = aes_encryption.decrypt_text(
                        encrypted_summary_b64,
                        encryption_key
                    )
                except Exception as e:
                    logger.error(f"[DECRYPT] Failed to decrypt summary: {e}")
                    summary_json = item.get('summary')
            else:
                summary_json = item.get('summary')

            if not summary_json:
                return None

            summary_data = json.loads(summary_json)

            return DailySummaryResponse(
                summary_id=item.get('summary_id'),
                summary_date=item.get('summary_date'),
                family_info=summary_data.get('family_info', []),
                business_info=summary_data.get('business_info', []),
                misc_info=summary_data.get('misc_info', []),
                created_at=datetime.fromisoformat(item.get('created_at'))
            )

        except Exception as e:
            logger.error(f"[RETRIEVE] Failed to get summary for {user_id} on {summary_date}: {e}", exc_info=True)
            raise

    def delete_summary(self, user_id: str, summary_id: str) -> bool:
        """Delete a summary for a user.

        Args:
            user_id: User ID (for authorization check)
            summary_id: Summary ID to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            # First retrieve the summary to check ownership
            response = self.table.get_item(Key={'summary_id': summary_id})

            if 'Item' not in response:
                logger.warning(f"[DELETE] Summary {summary_id} not found")
                return False

            item = response['Item']
            if item.get('user_id') != user_id:
                logger.error(f"[DELETE] User {user_id} not authorized to delete summary {summary_id}")
                return False

            # Delete the summary
            self.table.delete_item(Key={'summary_id': summary_id})
            logger.info(f"[DELETE] Deleted summary {summary_id} for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"[DELETE] Failed to delete summary {summary_id}: {e}", exc_info=True)
            return False

    def export_summaries(
        self,
        user_id: str,
        limit: int = 100,
        format: str = "json"
    ) -> str:
        """Export user's summaries in specified format.

        Args:
            user_id: User ID
            limit: Maximum number of summaries to export
            format: Export format ('json' or 'csv')

        Returns:
            Exported data as string
        """
        try:
            summaries = self.get_user_summaries(user_id, limit=limit)

            if format == "json":
                # Convert to JSON
                export_data = []
                for summary in summaries:
                    export_data.append({
                        'summary_id': summary.summary_id,
                        'summary_date': summary.summary_date,
                        'family_info': summary.family_info,
                        'business_info': summary.business_info,
                        'misc_info': summary.misc_info,
                        'created_at': summary.created_at.isoformat()
                    })
                return json.dumps(export_data, indent=2)

            elif format == "csv":
                # Export as CSV
                import csv
                from io import StringIO

                output = StringIO()
                writer = csv.writer(output)

                # Write header
                writer.writerow([
                    'Summary Date',
                    'Family Info',
                    'Business Info',
                    'Misc Info',
                    'Created At'
                ])

                # Write rows
                for summary in summaries:
                    writer.writerow([
                        summary.summary_date,
                        ' | '.join(summary.family_info),
                        ' | '.join(summary.business_info),
                        ' | '.join(summary.misc_info),
                        summary.created_at.isoformat()
                    ])

                return output.getvalue()

            else:
                raise ValueError(f"Unsupported export format: {format}")

        except Exception as e:
            logger.error(f"[EXPORT] Failed to export summaries for user {user_id}: {e}", exc_info=True)
            raise
