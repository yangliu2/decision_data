#!/usr/bin/env python3
"""
Migration script to update processing job created_at timestamps.

For jobs created before recorded_at feature, this updates job.created_at
to match the associated audio file's recorded_at time.
"""

import boto3
from datetime import datetime
from dotenv import load_dotenv
import os
from loguru import logger

load_dotenv()


def migrate_job_timestamps():
    """Update processing job timestamps to use audio file's recorded_at."""

    # Initialize DynamoDB
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=os.getenv('REGION_NAME'),
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
    )

    jobs_table = dynamodb.Table('panzoto-processing-jobs')
    audio_files_table = dynamodb.Table('panzoto-audio-files')

    print("=" * 60)
    print("MIGRATE JOB TIMESTAMPS")
    print("=" * 60)

    print("\n[SCAN] Scanning panzoto-processing-jobs table...")

    try:
        # Scan all jobs
        response = jobs_table.scan()
        jobs = response['Items']

        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = jobs_table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            jobs.extend(response['Items'])

        print(f"[STATS] Found {len(jobs)} processing jobs")

        # Filter transcription jobs with audio_file_id
        jobs_to_update = [
            job for job in jobs
            if job.get('job_type') == 'transcription'
            and job.get('audio_file_id')
            and job.get('status') in ['completed', 'failed']  # Skip pending/processing
        ]

        print(f"[TARGET] {len(jobs_to_update)} transcription jobs eligible for update")

        if not jobs_to_update:
            print("\n[OK] No jobs need updating")
            return

        # Show sample
        print(f"\n[SAMPLE] First 3 jobs to update:")
        for job in jobs_to_update[:3]:
            print(f"  • {job['job_id']} - created_at: {job.get('created_at', 'N/A')}")

        # Confirm
        print(f"\n[WARN] About to update {len(jobs_to_update)} job timestamps")
        confirm = input("Type 'UPDATE' to proceed: ")

        if confirm != 'UPDATE':
            print("[SKIP] Update cancelled")
            return

        # Migrate jobs
        print(f"\n[UPDATE] Updating job timestamps...")

        updated_count = 0
        skipped_count = 0

        for job in jobs_to_update:
            try:
                # Get associated audio file
                audio_file_id = job.get('audio_file_id')
                audio_response = audio_files_table.get_item(Key={'file_id': audio_file_id})

                if 'Item' not in audio_response:
                    logger.warning(f"Audio file not found for job {job['job_id']}")
                    skipped_count += 1
                    continue

                audio_file = audio_response['Item']
                recorded_at = audio_file.get('recorded_at')
                recorded_at_iso = audio_file.get('recorded_at_iso')

                if not recorded_at_iso:
                    logger.warning(f"Audio file {audio_file_id} has no recorded_at_iso")
                    skipped_count += 1
                    continue

                # Update job
                jobs_table.update_item(
                    Key={'job_id': job['job_id']},
                    UpdateExpression='SET created_at = :created_at',
                    ExpressionAttributeValues={':created_at': recorded_at_iso}
                )

                updated_count += 1
                if updated_count % 10 == 0:
                    print(f"  → Updated {updated_count}/{len(jobs_to_update)}...")

            except Exception as e:
                logger.error(f"Failed to update job {job['job_id']}: {e}")
                skipped_count += 1
                continue

        print(f"\n[OK] Successfully updated {updated_count} job timestamps")
        if skipped_count > 0:
            print(f"[WARN] Skipped {skipped_count} jobs due to errors")

    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    migrate_job_timestamps()
    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
