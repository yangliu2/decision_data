#!/usr/bin/env python3
"""Test backend connectivity and S3 presigned URL generation."""

import requests
import json
from decision_data.backend.config.config import backend_config

BACKEND_URL = "http://206.189.185.129:8000/api"

def test_health():
    """Test if backend is reachable."""
    print("=" * 70)
    print("1. Testing Backend Health")
    print("=" * 70)
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=5)
        if response.status_code == 200:
            print(f"✓ Backend is HEALTHY")
            print(f"  Response: {response.json()}")
        else:
            print(f"✗ Backend returned {response.status_code}")
            print(f"  Response: {response.text}")
    except Exception as e:
        print(f"✗ Cannot reach backend: {e}")

def test_presigned_url():
    """Test S3 presigned URL generation."""
    print("\n" + "=" * 70)
    print("2. Testing S3 Presigned URL Generation")
    print("=" * 70)

    test_key = "audio_upload/test-user-id/test_audio.3gp_encrypted"

    try:
        response = requests.get(
            f"{BACKEND_URL}/presigned-url",
            params={"key": test_key},
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            if 'url' in data:
                print(f"✓ Presigned URL generation WORKS")
                print(f"  URL (first 100 chars): {data['url'][:100]}...")
            else:
                print(f"✗ Missing 'url' in response")
                print(f"  Response: {data}")
        else:
            print(f"✗ Failed with status {response.status_code}")
            print(f"  Response: {response.text}")
    except Exception as e:
        print(f"✗ Error getting presigned URL: {e}")

def check_s3_bucket():
    """Check if S3 bucket is accessible."""
    print("\n" + "=" * 70)
    print("3. Checking S3 Bucket Accessibility")
    print("=" * 70)

    try:
        import boto3

        s3 = boto3.client(
            's3',
            region_name=backend_config.REGION_NAME,
            aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY
        )

        # Try to list objects
        response = s3.list_objects_v2(
            Bucket=backend_config.AWS_S3_BUCKET_NAME,
            Prefix="audio_upload",
            MaxKeys=1
        )

        print(f"✓ S3 bucket '{backend_config.AWS_S3_BUCKET_NAME}' is ACCESSIBLE")

        # Count audio files
        response = s3.list_objects_v2(
            Bucket=backend_config.AWS_S3_BUCKET_NAME,
            Prefix="audio_upload"
        )
        count = len(response.get('Contents', []))
        print(f"  Audio files in S3: {count}")

        if count > 0:
            latest = response['Contents'][-1]
            print(f"  Latest file: {latest['Key']} ({latest['Size']} bytes)")

    except Exception as e:
        print(f"✗ Cannot access S3: {e}")

def check_processing_jobs():
    """Check if there are pending jobs."""
    print("\n" + "=" * 70)
    print("4. Checking Processing Jobs")
    print("=" * 70)

    try:
        import boto3

        dynamodb = boto3.resource(
            'dynamodb',
            region_name=backend_config.REGION_NAME,
            aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY
        )

        jobs_table = dynamodb.Table('panzoto-processing-jobs')
        response = jobs_table.scan()

        jobs = response.get('Items', [])
        print(f"✓ Found {len(jobs)} total jobs")

        # Group by status
        by_status = {}
        for job in jobs:
            status = job.get('status', 'unknown')
            by_status[status] = by_status.get(status, 0) + 1

        for status, count in sorted(by_status.items()):
            print(f"  {status}: {count}")

    except Exception as e:
        print(f"✗ Cannot access DynamoDB: {e}")

if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("PANZOTO BACKEND DIAGNOSTIC TEST")
    print("=" * 70 + "\n")

    test_health()
    test_presigned_url()
    check_s3_bucket()
    check_processing_jobs()

    print("\n" + "=" * 70)
    print("Diagnostic complete!")
    print("=" * 70 + "\n")
