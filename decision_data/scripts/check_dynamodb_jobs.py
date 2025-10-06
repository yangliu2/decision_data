#!/usr/bin/env python3
"""
Script to check the current state of the panzoto-processing-jobs DynamoDB table
to diagnose transcription issues.
"""

import boto3
from datetime import datetime
from decision_data.backend.config.config import backend_config
from botocore.exceptions import ClientError

def get_dynamodb_resource():
    """Get DynamoDB resource."""
    return boto3.resource(
        'dynamodb',
        region_name=backend_config.REGION_NAME,
        aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY
    )

def check_table_status():
    """Check if the panzoto-processing-jobs table exists and is active."""
    try:
        dynamodb = get_dynamodb_resource()
        table = dynamodb.Table('panzoto-processing-jobs')

        # Check table status
        response = table.describe_table()
        table_status = response['Table']['TableStatus']
        item_count = response['Table']['ItemCount']

        print(f"[STATS] Table Status: {table_status}")
        print(f"[STATS] Item Count: {item_count}")
        print(f"[STATS] Table Size: {response['Table']['TableSizeBytes']} bytes")

        return table

    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print("[ERROR] Table 'panzoto-processing-jobs' does not exist!")
            return None
        else:
            print(f"[ERROR] Error accessing table: {e}")
            return None

def scan_all_jobs(table):
    """Scan all jobs in the table."""
    try:
        print("\n[SEARCH] Scanning all jobs in panzoto-processing-jobs table...")

        response = table.scan()
        jobs = response['Items']

        if not jobs:
            print("[ERROR] No jobs found in the table!")
            return

        print(f"[OK] Found {len(jobs)} jobs total")

        # Group jobs by status
        status_counts = {}
        for job in jobs:
            status = job.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1

        print("\n[CHART] Jobs by Status:")
        for status, count in status_counts.items():
            print(f"  {status}: {count}")

        # Show recent jobs
        print("\n[INFO] Recent Jobs (last 10):")
        # Sort by created_at if available
        sorted_jobs = sorted(jobs, key=lambda x: x.get('created_at', ''), reverse=True)

        for i, job in enumerate(sorted_jobs[:10]):
            print(f"\n  Job {i+1}:")
            print(f"    Job ID: {job.get('job_id', 'N/A')}")
            print(f"    User ID: {job.get('user_id', 'N/A')}")
            print(f"    Type: {job.get('job_type', 'N/A')}")
            print(f"    Status: {job.get('status', 'N/A')}")
            print(f"    Created: {job.get('created_at', 'N/A')}")
            if 'completed_at' in job:
                print(f"    Completed: {job['completed_at']}")
            if 'error_message' in job:
                print(f"    Error: {job['error_message']}")
            if 'audio_file_id' in job:
                print(f"    Audio File: {job['audio_file_id']}")

        return jobs

    except Exception as e:
        print(f"[ERROR] Error scanning jobs: {e}")
        return []

def check_pending_jobs(table):
    """Check specifically for pending jobs."""
    try:
        print("\n🕐 Checking for pending jobs...")

        response = table.scan(
            FilterExpression='#status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':status': 'pending'}
        )

        pending_jobs = response['Items']

        if not pending_jobs:
            print("[ERROR] No pending jobs found - this might explain why no transcription buttons appear!")
            return

        print(f"[OK] Found {len(pending_jobs)} pending jobs")

        for job in pending_jobs:
            print(f"\n  Pending Job:")
            print(f"    Job ID: {job.get('job_id', 'N/A')}")
            print(f"    User ID: {job.get('user_id', 'N/A')}")
            print(f"    Type: {job.get('job_type', 'N/A')}")
            print(f"    Created: {job.get('created_at', 'N/A')}")
            if 'audio_file_id' in job:
                print(f"    Audio File: {job['audio_file_id']}")

    except Exception as e:
        print(f"[ERROR] Error checking pending jobs: {e}")

def check_failed_jobs(table):
    """Check for failed jobs that might need attention."""
    try:
        print("\n[ERROR] Checking for failed jobs...")

        response = table.scan(
            FilterExpression='#status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':status': 'failed'}
        )

        failed_jobs = response['Items']

        if not failed_jobs:
            print("[OK] No failed jobs found")
            return

        print(f"[ERROR] Found {len(failed_jobs)} failed jobs")

        # Group by error message
        error_counts = {}
        for job in failed_jobs:
            error = job.get('error_message', 'Unknown error')
            error_counts[error] = error_counts.get(error, 0) + 1

        print("\n[STATS] Failed Jobs by Error Type:")
        for error, count in error_counts.items():
            print(f"  '{error}': {count} jobs")

        # Show recent failures
        print("\n[INFO] Recent Failed Jobs (last 5):")
        sorted_failed = sorted(failed_jobs, key=lambda x: x.get('created_at', ''), reverse=True)

        for i, job in enumerate(sorted_failed[:5]):
            print(f"\n  Failed Job {i+1}:")
            print(f"    Job ID: {job.get('job_id', 'N/A')}")
            print(f"    User ID: {job.get('user_id', 'N/A')}")
            print(f"    Type: {job.get('job_type', 'N/A')}")
            print(f"    Created: {job.get('created_at', 'N/A')}")
            print(f"    Error: {job.get('error_message', 'N/A')}")
            if 'audio_file_id' in job:
                print(f"    Audio File: {job['audio_file_id']}")

    except Exception as e:
        print(f"[ERROR] Error checking failed jobs: {e}")

def check_processing_jobs(table):
    """Check for jobs currently in processing state."""
    try:
        print("\n⚙️ Checking for jobs in processing state...")

        response = table.scan(
            FilterExpression='#status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':status': 'processing'}
        )

        processing_jobs = response['Items']

        if not processing_jobs:
            print("[OK] No jobs currently processing")
            return

        print(f"⚙️ Found {len(processing_jobs)} jobs in processing state")

        for job in processing_jobs:
            print(f"\n  Processing Job:")
            print(f"    Job ID: {job.get('job_id', 'N/A')}")
            print(f"    User ID: {job.get('user_id', 'N/A')}")
            print(f"    Type: {job.get('job_type', 'N/A')}")
            print(f"    Created: {job.get('created_at', 'N/A')}")
            if 'audio_file_id' in job:
                print(f"    Audio File: {job['audio_file_id']}")

            # Check if job has been processing for too long
            if 'created_at' in job:
                try:
                    created_time = datetime.fromisoformat(job['created_at'])
                    now = datetime.utcnow()
                    duration = now - created_time
                    print(f"    Processing Duration: {duration}")

                    if duration.total_seconds() > 3600:  # More than 1 hour
                        print("    [WARN] WARNING: Job has been processing for more than 1 hour!")
                except:
                    pass

    except Exception as e:
        print(f"[ERROR] Error checking processing jobs: {e}")

def main():
    """Main function to check the DynamoDB table state."""
    print("[SEARCH] Checking panzoto-processing-jobs DynamoDB table state...")
    print("=" * 60)

    # Check table status
    table = check_table_status()
    if not table:
        return

    # Scan all jobs for overview
    jobs = scan_all_jobs(table)

    # Check specific job states
    check_pending_jobs(table)
    check_processing_jobs(table)
    check_failed_jobs(table)

    print("\n" + "=" * 60)
    print("🎯 Diagnosis Summary:")
    print("1. If no pending jobs exist, users won't see transcription buttons")
    print("2. If jobs are stuck in 'processing', the transcription service may not be running")
    print("3. If many jobs are 'failed', check error messages for common issues")
    print("4. Check if the transcription service is actively polling for jobs")

if __name__ == "__main__":
    main()