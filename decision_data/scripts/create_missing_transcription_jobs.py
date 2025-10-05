#!/usr/bin/env python3
"""Create transcription jobs for existing audio files that don't have them"""

import boto3
from decision_data.backend.config.config import backend_config
from decision_data.backend.services.transcription_service import UserTranscriptionService

def create_missing_transcription_jobs():
    # Initialize DynamoDB
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=backend_config.REGION_NAME,
        aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY
    )

    audio_table = dynamodb.Table('panzoto-audio-files')
    jobs_table = dynamodb.Table('panzoto-processing-jobs')

    try:
        # Get all audio files
        audio_response = audio_table.scan()
        audio_files = audio_response['Items']

        # Get all transcription jobs
        jobs_response = jobs_table.scan(
            FilterExpression='job_type = :job_type',
            ExpressionAttributeValues={':job_type': 'transcription'}
        )
        existing_jobs = jobs_response['Items']

        # Create set of audio file IDs that already have transcription jobs
        audio_files_with_jobs = set()
        for job in existing_jobs:
            if job.get('audio_file_id'):
                audio_files_with_jobs.add(job['audio_file_id'])

        print(f"Found {len(audio_files)} audio files")
        print(f"Found {len(existing_jobs)} existing transcription jobs")
        print(f"Audio files with jobs: {audio_files_with_jobs}")

        # Create transcription service
        transcription_service = UserTranscriptionService()

        # Create jobs for audio files without them
        created_jobs = 0
        for audio_file in audio_files:
            file_id = audio_file['file_id']
            user_id = audio_file['user_id']

            if file_id not in audio_files_with_jobs:
                print(f"Creating transcription job for audio file: {file_id}")
                job_id = transcription_service.create_processing_job(
                    user_id=user_id,
                    job_type="transcription",
                    audio_file_id=file_id
                )
                print(f"  Created job: {job_id}")
                created_jobs += 1
            else:
                print(f"Audio file {file_id} already has a transcription job, skipping")

        print(f"\nCreated {created_jobs} new transcription jobs")

    except Exception as e:
        print(f"Error creating transcription jobs: {e}")

if __name__ == "__main__":
    create_missing_transcription_jobs()