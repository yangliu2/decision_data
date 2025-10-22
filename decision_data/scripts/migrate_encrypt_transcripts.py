#!/usr/bin/env python3
"""
Migration script to encrypt existing plaintext transcripts in DynamoDB.

This script converts all existing plaintext transcripts to encrypted format.
Use this after deploying the transcript encryption feature.

Usage:
    python migrate_encrypt_transcripts.py [--dry-run]

Options:
    --dry-run    Show what would be encrypted without making changes
"""

import sys
import boto3
import argparse
from decimal import Decimal
from loguru import logger

from decision_data.backend.config.config import backend_config
from decision_data.backend.utils.secrets_manager import secrets_manager
from decision_data.backend.utils.aes_encryption import aes_encryption

logger.remove()  # Remove default handler
logger.add(sys.stderr, format="<level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>")


def is_encrypted(text: str) -> bool:
    """Check if text looks like base64 (encrypted transcripts are base64)."""
    if not isinstance(text, str) or len(text) < 50:
        return False

    # Base64 encrypted data is longer and contains typical base64 chars
    import base64
    try:
        base64.b64decode(text, validate=True)
        # If it decodes successfully and looks like binary data, it's probably encrypted
        return True
    except Exception:
        return False


def migrate_transcripts(dry_run: bool = False):
    """Migrate plaintext transcripts to encrypted format."""

    # Connect to DynamoDB
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=backend_config.REGION_NAME,
        aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY
    )

    transcripts_table = dynamodb.Table('panzoto-transcripts')

    logger.info("Starting transcript encryption migration...")
    logger.info(f"Dry run: {dry_run}")

    # Scan all transcripts
    response = transcripts_table.scan()
    items = response.get('Items', [])

    logger.info(f"Found {len(items)} transcripts total")

    encrypted_count = 0
    already_encrypted_count = 0
    failed_count = 0
    plaintext_count = 0

    # Process each transcript
    for item in items:
        transcript_id = item['transcript_id']
        user_id = item['user_id']
        transcript_text = item.get('transcript', '')

        try:
            # Check if already encrypted
            if is_encrypted(transcript_text):
                logger.info(f"[SKIP] Transcript {transcript_id} already encrypted")
                already_encrypted_count += 1
                continue

            plaintext_count += 1

            # Get user's encryption key
            encryption_key = secrets_manager.get_user_encryption_key(user_id)
            if not encryption_key:
                logger.error(f"[FAIL] No encryption key found for user {user_id}, skipping transcript {transcript_id}")
                failed_count += 1
                continue

            # Encrypt the transcript
            encrypted_text_b64 = aes_encryption.encrypt_text(transcript_text, encryption_key)

            if dry_run:
                logger.info(f"[DRY-RUN] Would encrypt transcript {transcript_id} for user {user_id}")
                logger.info(f"  Original: {len(transcript_text)} bytes → Encrypted: {len(encrypted_text_b64)} bytes")
            else:
                # Update DynamoDB with encrypted transcript
                transcripts_table.update_item(
                    Key={'transcript_id': transcript_id},
                    UpdateExpression='SET #transcript = :transcript',
                    ExpressionAttributeNames={'#transcript': 'transcript'},
                    ExpressionAttributeValues={':transcript': encrypted_text_b64}
                )
                logger.info(f"[OK] Encrypted transcript {transcript_id} for user {user_id}")
                logger.info(f"  {len(transcript_text)} bytes → {len(encrypted_text_b64)} bytes (base64)")
                encrypted_count += 1

        except Exception as e:
            logger.error(f"[ERROR] Failed to process transcript {transcript_id}: {e}", exc_info=True)
            failed_count += 1

    # Summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("MIGRATION SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Total transcripts:        {len(items)}")
    logger.info(f"Already encrypted:        {already_encrypted_count}")
    logger.info(f"Plaintext transcripts:    {plaintext_count}")
    if dry_run:
        logger.info(f"Would be encrypted:       {plaintext_count}")
    else:
        logger.info(f"Successfully encrypted:   {encrypted_count}")
    logger.info(f"Failed:                   {failed_count}")
    logger.info("=" * 70)

    if dry_run:
        logger.info("DRY RUN COMPLETED - No changes made")
    else:
        logger.info("MIGRATION COMPLETED")

    return encrypted_count, failed_count


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Encrypt existing plaintext transcripts in DynamoDB'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be encrypted without making changes'
    )

    args = parser.parse_args()

    try:
        encrypted, failed = migrate_transcripts(dry_run=args.dry_run)

        if failed > 0:
            logger.warning(f"⚠️  {failed} transcripts failed to encrypt")
            sys.exit(1)
        else:
            logger.info("✅ Migration successful!")
            sys.exit(0)

    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        sys.exit(1)
