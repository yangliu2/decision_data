#!/usr/bin/env python3
"""Check status of audio files and processing jobs."""

import boto3
from decision_data.backend.config.config import backend_config

# Connect to AWS
dynamodb = boto3.resource(
    'dynamodb',
    region_name=backend_config.REGION_NAME,
    aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY
)

s3 = boto3.client(
    's3',
    region_name=backend_config.REGION_NAME,
    aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY
)

# Check audio files
print("=" * 70)
print("AUDIO FILES IN S3")
print("=" * 70)
try:
    response = s3.list_objects_v2(
        Bucket=backend_config.AWS_S3_BUCKET_NAME,
        Prefix=backend_config.AWS_S3_AUDIO_FOLDER
    )

    if 'Contents' not in response:
        print("❌ No audio files in S3!")
    else:
        print(f"✓ Found {len(response['Contents'])} audio files:")
        for obj in response['Contents'][-5:]:  # Show last 5
            print(f"  - {obj['Key']} ({obj['Size']} bytes, {obj['LastModified']})")
except Exception as e:
    print(f"❌ Error checking S3: {e}")

# Check processing jobs
print("\n" + "=" * 70)
print("PROCESSING JOBS")
print("=" * 70)
jobs_table = dynamodb.Table('panzoto-processing-jobs')
response = jobs_table.scan()
items = response.get('Items', [])

if not items:
    print("❌ No processing jobs found!")
else:
    print(f"✓ Found {len(items)} jobs:")

    # Group by status
    by_status = {}
    for job in items:
        status = job.get('status', 'unknown')
        by_status[status] = by_status.get(status, 0) + 1

    print("\nJob breakdown:")
    for status, count in sorted(by_status.items()):
        print(f"  {status}: {count}")

    print("\nLatest 5 jobs:")
    for job in sorted(items, key=lambda x: x.get('created_at', ''), reverse=True)[:5]:
        print(f"  - {job['job_id'][:8]}... ({job.get('job_type', 'unknown')}) - {job.get('status')} - {job.get('created_at', 'N/A')}")

# Check transcripts
print("\n" + "=" * 70)
print("TRANSCRIPTS")
print("=" * 70)
transcripts_table = dynamodb.Table('panzoto-transcripts')
response = transcripts_table.scan()
items = response.get('Items', [])

if not items:
    print("❌ No transcripts found!")
else:
    print(f"✓ Found {len(items)} transcripts:")
    for transcript in sorted(items, key=lambda x: x.get('created_at', ''), reverse=True)[:5]:
        print(f"  - {transcript['transcript_id'][:8]}... - {transcript.get('created_at', 'N/A')}")
        print(f"    Transcript: {transcript.get('transcript', '')[:60]}...")

print("\n" + "=" * 70)
