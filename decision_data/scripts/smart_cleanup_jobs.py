#!/usr/bin/env python3
"""
Smart cleanup for processing jobs by error category.
Handles legacy encryption files, max retries, and transcription failures.
"""

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
import os
from collections import defaultdict
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

def categorize_error(error_message):
    """Categorize error messages for targeted cleanup."""
    if not error_message:
        return "no_error"

    error_lower = error_message.lower()

    if "automatic decryption not yet implemented" in error_lower:
        return "legacy_encryption"
    elif "exceeded maximum retries" in error_lower:
        return "max_retries"
    elif "transcription failed or too short" in error_lower:
        return "transcription_failed"
    elif "mac check failed" in error_lower:
        return "decryption_error"
    elif "file does not start with riff" in error_lower:
        return "format_error"
    elif "timeout" in error_lower:
        return "timeout"
    else:
        return "other"

def get_all_jobs():
    """Fetch all processing jobs from DynamoDB."""
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=os.getenv('REGION_NAME'),
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
    )

    jobs_table = dynamodb.Table('panzoto-processing-jobs')

    try:
        response = jobs_table.scan()
        items = response['Items']

        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = jobs_table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response['Items'])

        return items
    except Exception as e:
        print(f"[ERROR] Failed to fetch jobs: {e}")
        return []

def categorize_all_jobs(jobs):
    """Categorize all failed jobs."""
    categories = defaultdict(list)

    for job in jobs:
        if job.get('status') == 'failed':
            error = job.get('error_message', 'unknown')
            category = categorize_error(error)
            categories[category].append(job)

    return categories

def delete_jobs_by_category(category, jobs_to_delete):
    """Delete jobs from a specific category."""
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=os.getenv('REGION_NAME'),
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
    )

    jobs_table = dynamodb.Table('panzoto-processing-jobs')

    print(f"\n[DELETE] Deleting {len(jobs_to_delete)} jobs from '{category}'...")

    deleted_count = 0
    with jobs_table.batch_writer() as batch:
        for job in jobs_to_delete:
            batch.delete_item(Key={'job_id': job['job_id']})
            deleted_count += 1
            if deleted_count % 10 == 0:
                print(f"  → Deleted {deleted_count}/{len(jobs_to_delete)}...")

    print(f"[OK] Successfully deleted {deleted_count} jobs")
    return deleted_count

def delete_audio_files_for_jobs(jobs_to_delete):
    """Optionally delete associated audio files from S3."""
    print(f"\n[WARN] Delete {len(jobs_to_delete)} audio files from S3? (yes/no):")
    confirm = input("Type 'yes' to confirm: ")

    if confirm.lower() != 'yes':
        print("[SKIP] Skipping audio file deletion")
        return 0

    s3 = boto3.client(
        's3',
        region_name=os.getenv('REGION_NAME'),
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
    )

    bucket_name = os.getenv('AWS_S3_BUCKET_NAME', 'panzoto')

    print(f"\n[DELETE] Deleting audio files from S3 bucket '{bucket_name}'...")

    # Get unique audio files (some jobs might reference same file)
    audio_files = set()
    for job in jobs_to_delete:
        if job.get('audio_file_id'):
            audio_files.add(job.get('audio_file_id'))

    deleted_count = 0
    for audio_file_id in audio_files:
        try:
            # Try both encrypted and non-encrypted patterns
            s3_keys = [
                f"audio_upload/{job['user_id']}/{audio_file_id}.3gp_encrypted"
                for job in jobs_to_delete
                if job.get('audio_file_id') == audio_file_id
            ]

            for s3_key in s3_keys:
                try:
                    s3.delete_object(Bucket=bucket_name, Key=s3_key)
                    deleted_count += 1
                except Exception as e:
                    print(f"  [WARN] Failed to delete {s3_key}: {e}")

        except Exception as e:
            print(f"  [WARN] Error deleting audio files: {e}")

    print(f"[OK] Deleted {deleted_count} audio files from S3")
    return deleted_count

def show_cleanup_menu(categories):
    """Show interactive menu for selecting what to clean."""
    print("\n" + "=" * 60)
    print("SELECTIVE JOB CLEANUP")
    print("=" * 60)

    print("\n[MENU] Select cleanup options:")
    print("  1. Legacy encryption jobs (old client-side encrypted files)")
    print("  2. Max retries jobs (failed after 3 attempts)")
    print("  3. Transcription failed jobs (too short or API error)")
    print("  4. All failed jobs")
    print("  5. Skip cleanup")

    choice = input("\nEnter choice (1-5): ")

    if choice == '1':
        return ['legacy_encryption']
    elif choice == '2':
        return ['max_retries']
    elif choice == '3':
        return ['transcription_failed']
    elif choice == '4':
        return list(categories.keys())
    else:
        return []

def main():
    print("=" * 60)
    print("SMART CLEANUP FOR PROCESSING JOBS")
    print("=" * 60)

    # Fetch and categorize jobs
    print("\n[SCAN] Scanning panzoto-processing-jobs table...")
    jobs = get_all_jobs()

    if not jobs:
        print("[OK] No jobs found")
        return

    # Categorize
    categories = categorize_all_jobs(jobs)

    # Show summary
    print(f"\n[SUMMARY] Found {len(jobs)} total jobs:")
    print(f"  ✅ completed: {len([j for j in jobs if j.get('status') == 'completed'])}")
    print(f"  ❌ failed:    {len([j for j in jobs if j.get('status') == 'failed'])}")
    print(f"  ⏳ pending:   {len([j for j in jobs if j.get('status') == 'pending'])}")

    if categories:
        print(f"\n[CATEGORIES] Failed jobs by type:")
        for category, jobs_list in sorted(categories.items()):
            print(f"  • {category}: {len(jobs_list)} jobs")

    # Show descriptions
    print("\n[DESCRIPTIONS]")
    if 'legacy_encryption' in categories:
        print("  LEGACY_ENCRYPTION:")
        print("    - Old audio files encrypted with client-side encryption")
        print("    - Created before October 6, 2025")
        print("    - Cannot be decrypted by server processor")
        print("    - Safe to delete if you have new recordings")

    if 'max_retries' in categories:
        print("  MAX_RETRIES:")
        print("    - Jobs that failed 3+ times")
        print("    - Likely indicate persistent problems")
        print("    - May need debugging before retry")

    if 'transcription_failed' in categories:
        print("  TRANSCRIPTION_FAILED:")
        print("    - Audio too short (<1 second) or API errors")
        print("    - May be worth manual review")

    # Offer cleanup options
    if not categories:
        print("\n[OK] No failed jobs to clean up")
        return

    # Interactive menu
    selected_categories = show_cleanup_menu(categories)

    if not selected_categories:
        print("[SKIP] Cleanup cancelled")
        return

    # Summarize what will be deleted
    jobs_to_delete = []
    for category in selected_categories:
        jobs_to_delete.extend(categories.get(category, []))

    print("\n" + "=" * 60)
    print("CLEANUP PLAN")
    print("=" * 60)

    for category in selected_categories:
        count = len(categories.get(category, []))
        print(f"  • Delete {count} jobs from '{category}'")

    print(f"\n[TOTAL] Will delete {len(jobs_to_delete)} processing jobs")

    # Final confirmation
    confirm = input("\nType 'DELETE' to confirm: ")

    if confirm != 'DELETE':
        print("[ERROR] Cancelled - no changes made")
        return

    # Execute cleanup
    total_deleted = 0

    for category in selected_categories:
        jobs_for_category = categories.get(category, [])
        deleted = delete_jobs_by_category(category, jobs_for_category)
        total_deleted += deleted

        # Ask to delete audio files (only for legacy_encryption)
        if category == 'legacy_encryption' and category in selected_categories:
            delete_audio_files_for_jobs(jobs_for_category)

    # Final summary
    print("\n" + "=" * 60)
    print("CLEANUP COMPLETE")
    print("=" * 60)
    print(f"\n[OK] Deleted {total_deleted} processing jobs")
    print("\nNext steps:")
    print("  1. Verify new audio uploads work correctly")
    print("  2. Check /api/user/processing-jobs endpoint")
    print("  3. Monitor background processor logs")
    print()

if __name__ == "__main__":
    main()
