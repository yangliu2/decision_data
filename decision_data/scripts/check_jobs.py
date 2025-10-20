#!/usr/bin/env python3
"""Check current processing jobs in DynamoDB with error categorization"""

import boto3
from decision_data.backend.config.config import backend_config
from collections import defaultdict
from datetime import datetime

def categorize_error(error_message):
    """Categorize error messages for better analysis."""
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

def check_processing_jobs(verbose=False):
    # Initialize DynamoDB
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=backend_config.REGION_NAME,
        aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY
    )

    jobs_table = dynamodb.Table('panzoto-processing-jobs')

    try:
        # Scan all jobs
        response = jobs_table.scan()
        jobs = response['Items']

        print(f"\n[INFO] Found {len(jobs)} processing jobs")
        print("=" * 80)

        # Categorize jobs
        status_counts = defaultdict(int)
        error_categories = defaultdict(list)

        for job in jobs:
            status = job.get('status', 'unknown')
            status_counts[status] += 1

            if status == 'failed':
                error = job.get('error_message', 'unknown')
                category = categorize_error(error)
                error_categories[category].append({
                    'job_id': job.get('job_id'),
                    'audio_file_id': job.get('audio_file_id'),
                    'created_at': job.get('created_at'),
                    'error': error
                })

        # Print summary
        print(f"\n[SUMMARY] Status Breakdown:")
        print(f"  ✅ completed: {status_counts['completed']}")
        print(f"  ❌ failed:    {status_counts['failed']}")
        print(f"  ⏳ pending:   {status_counts['pending']}")

        if error_categories:
            print(f"\n[ERROR CATEGORIES]")
            for category, jobs_with_error in error_categories.items():
                print(f"  {category}: {len(jobs_with_error)}")

        # Detailed breakdown
        if error_categories:
            print(f"\n[DETAILED ERROR BREAKDOWN]")
            for category, jobs_with_error in sorted(error_categories.items()):
                print(f"\n  {category.upper()} ({len(jobs_with_error)} jobs):")
                if category == "legacy_encryption":
                    print(f"    → These are from OLD client-side encrypted files")
                    print(f"    → Created before October 6, 2025 migration")
                    print(f"    → SOLUTION: Delete these audio files from S3")
                elif category == "max_retries":
                    print(f"    → Jobs failed 3x and were auto-failed")
                    print(f"    → SOLUTION: Check logs, fix root cause, retry")
                elif category == "transcription_failed":
                    print(f"    → Audio too short or transcription service error")
                    print(f"    → SOLUTION: May need manual review")

                if verbose:
                    for job in jobs_with_error[:3]:  # Show first 3
                        print(f"    • {job['job_id'][:8]}... ({job['created_at']})")

        if verbose:
            print(f"\n[VERBOSE] Detailed Job List:")
            print("=" * 80)
            for job in jobs:
                print(f"Job ID: {job.get('job_id', 'N/A')}")
                print(f"User ID: {job.get('user_id', 'N/A')}")
                print(f"Job Type: {job.get('job_type', 'N/A')}")
                print(f"Status: {job.get('status', 'N/A')}")
                print(f"Audio File ID: {job.get('audio_file_id', 'N/A')}")
                print(f"Created: {job.get('created_at', 'N/A')}")
                if job.get('error_message'):
                    print(f"Error: {job.get('error_message')}")
                print("-" * 40)

    except Exception as e:
        print(f"[ERROR] Error checking jobs: {e}")

if __name__ == "__main__":
    import sys
    verbose = '-v' in sys.argv or '--verbose' in sys.argv
    check_processing_jobs(verbose=verbose)