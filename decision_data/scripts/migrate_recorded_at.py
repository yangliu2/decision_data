#!/usr/bin/env python3
"""
Migration script to add recorded_at field to existing audio files in DynamoDB.

For audio files created before the recorded_at feature was added,
this script backfills the recorded_at field using uploaded_at as a fallback.
"""

import boto3
from datetime import datetime
from dotenv import load_dotenv
import os
from loguru import logger

load_dotenv()


def migrate_recorded_at():
    """Add recorded_at field to all audio files missing it."""

    # Initialize DynamoDB
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=os.getenv('REGION_NAME'),
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
    )

    audio_files_table = dynamodb.Table('panzoto-audio-files')

    print("=" * 60)
    print("MIGRATE recorded_at FIELD")
    print("=" * 60)

    print("\n[SCAN] Scanning panzoto-audio-files table...")

    try:
        # Scan all audio files
        response = audio_files_table.scan()
        items = response['Items']

        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = audio_files_table.scan(
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response['Items'])

        print(f"[STATS] Found {len(items)} audio files")

        # Separate files with and without recorded_at
        missing_recorded_at = [
            item for item in items
            if 'recorded_at' not in item
        ]
        has_recorded_at = [
            item for item in items
            if 'recorded_at' in item
        ]

        print(f"\n[STATUS] Audio files breakdown:")
        print(f"  • With recorded_at: {len(has_recorded_at)}")
        print(f"  • Without recorded_at (to migrate): {len(missing_recorded_at)}")

        if not missing_recorded_at:
            print("\n[OK] All audio files already have recorded_at field!")
            return

        # Show sample
        print(f"\n[SAMPLE] First 3 files needing migration:")
        for item in missing_recorded_at[:3]:
            print(f"  • {item['file_id']} - uploaded_at: {item.get('uploaded_at_iso', 'N/A')}")

        # Confirm migration
        print(f"\n[WARN] About to update {len(missing_recorded_at)} audio files")
        confirm = input("Type 'MIGRATE' to proceed: ")

        if confirm != 'MIGRATE':
            print("[SKIP] Migration cancelled")
            return

        # Migrate files
        print(f"\n[MIGRATE] Adding recorded_at to {len(missing_recorded_at)} files...")

        updated_count = 0
        with audio_files_table.batch_writer() as batch:
            for item in missing_recorded_at:
                # Use uploaded_at as fallback for recorded_at
                uploaded_at = item.get('uploaded_at')
                uploaded_at_iso = item.get('uploaded_at_iso')

                # Update item
                batch.put_item(
                    Item={
                        **item,
                        'recorded_at': uploaded_at,
                        'recorded_at_iso': uploaded_at_iso,
                    }
                )
                updated_count += 1

                if updated_count % 10 == 0:
                    print(f"  → Updated {updated_count}/{len(missing_recorded_at)}...")

        print(f"\n[OK] Successfully updated {updated_count} audio files")

        # Verify migration
        print("\n[VERIFY] Verifying migration...")
        verify_response = audio_files_table.scan()
        verify_items = verify_response['Items']

        # Handle pagination in verification
        while 'LastEvaluatedKey' in verify_response:
            verify_response = audio_files_table.scan(
                ExclusiveStartKey=verify_response['LastEvaluatedKey']
            )
            verify_items.extend(verify_response['Items'])

        still_missing = [
            item for item in verify_items
            if 'recorded_at' not in item
        ]

        if still_missing:
            print(f"[WARN] {len(still_missing)} files still missing recorded_at")
            for item in still_missing[:3]:
                print(f"  • {item['file_id']}")
        else:
            print(f"[OK] All {len(verify_items)} audio files now have recorded_at!")

    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    migrate_recorded_at()
    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
