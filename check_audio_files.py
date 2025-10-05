#!/usr/bin/env python3
"""Check current audio files in DynamoDB"""

import boto3
from decision_data.backend.config.config import backend_config

def check_audio_files():
    # Initialize DynamoDB
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=backend_config.REGION_NAME,
        aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY
    )

    audio_table = dynamodb.Table('panzoto-audio-files')

    try:
        # Scan all audio files
        response = audio_table.scan()
        files = response['Items']

        print(f"Found {len(files)} audio files:")
        print("=" * 80)

        for file in files:
            print(f"File ID: {file.get('file_id', 'N/A')}")
            print(f"User ID: {file.get('user_id', 'N/A')}")
            print(f"S3 Key: {file.get('s3_key', 'N/A')}")
            print(f"File Size: {file.get('file_size', 'N/A')} bytes")
            print(f"Uploaded: {file.get('uploaded_at', 'N/A')}")
            print("-" * 40)

        if len(files) == 0:
            print("No audio files found. This explains why there are no transcription jobs.")
        else:
            print(f"\nTotal audio files: {len(files)}")

    except Exception as e:
        print(f"Error checking audio files: {e}")

if __name__ == "__main__":
    check_audio_files()