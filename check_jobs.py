#!/usr/bin/env python3
"""Check current processing jobs in DynamoDB"""

import boto3
from decision_data.backend.config.config import backend_config

def check_processing_jobs():
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

        print(f"Found {len(jobs)} processing jobs:")
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

        # Count by status
        status_counts = {}
        for job in jobs:
            status = job.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1

        print(f"\nStatus Summary:")
        for status, count in status_counts.items():
            print(f"  {status}: {count}")

    except Exception as e:
        print(f"Error checking jobs: {e}")

if __name__ == "__main__":
    check_processing_jobs()