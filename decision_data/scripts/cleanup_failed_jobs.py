#!/usr/bin/env python3
"""
Clean up failed jobs from DynamoDB that were caused by MongoDB errors.

Usage:
    python cleanup_failed_jobs.py
"""

import sys
import boto3
from decision_data.backend.config.config import backend_config

def cleanup_failed_jobs():
    """Remove failed jobs from DynamoDB."""
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=backend_config.REGION_NAME,
        aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY
    )

    jobs_table = dynamodb.Table('panzoto-processing-jobs')

    # Scan for failed jobs
    print("Scanning for failed jobs...")
    response = jobs_table.scan(
        FilterExpression='#status = :failed',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={':failed': 'failed'}
    )

    failed_jobs = response.get('Items', [])
    print(f"Found {len(failed_jobs)} failed jobs\n")

    if not failed_jobs:
        print("No failed jobs to clean up!")
        return

    # Show failed jobs
    print("Failed jobs to be deleted:")
    for i, job in enumerate(failed_jobs, 1):
        print(f"{i}. Job ID: {job['job_id']}")
        print(f"   Type: {job.get('job_type', 'N/A')}")
        print(f"   Error: {job.get('error_message', 'N/A')[:80]}...")
        print()

    # Ask for confirmation
    response = input(f"Delete {len(failed_jobs)} failed jobs? (yes/no): ")
    if response.lower() != 'yes':
        print("Cancelled.")
        return

    # Delete failed jobs
    deleted_count = 0
    for job in failed_jobs:
        try:
            jobs_table.delete_item(Key={'job_id': job['job_id']})
            deleted_count += 1
        except Exception as e:
            print(f"Error deleting job {job['job_id']}: {e}")

    print(f"\n✓ Successfully deleted {deleted_count} failed jobs")

if __name__ == '__main__':
    cleanup_failed_jobs()
