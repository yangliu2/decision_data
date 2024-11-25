""" Using OpenAI services to do speech transcription """

import openai
from openai import OpenAI
from pathlib import Path
from loguru import logger
import os
import sys
from decision_data.backend.transcribe.aws_s3 import (
    download_from_s3,
    upload_to_s3,
    remove_s3_file,
)


def transcribe_from_local(audio_path: Path) -> str:
    """Transcribe audio file using Whiper service

    :param audio_path: local audio path file
    :type audio_path: Path
    :return: transcription
    :rtype: str
    """
    openai.api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAI()
    with audio_path.open("rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model="whisper-1", file=audio_file
        )
    return transcription.text


def transcribe_and_upload() -> None:
    """
    Main function to orchestrate downloading from S3, transcribing, uploading
    transcripts, and cleaning up.

    Args:
        bucket_name (str): Source S3 bucket name containing audio files.
        s3_key (str): Key (path) of the audio file in the source S3 bucket.
        transcripts_bucket (str): Destination S3 bucket name for transcripts.
        transcripts_folder (str): Folder within the destination bucket to store
        transcripts.
        download_dir (str): Local directory path to download audio files.

    Raises:
        Exception: If any step in the process fails.
    """
    bucket_name = "panzoto"
    audio_s3_folder = "audio_upload"
    audio_file_name = "20241120_130749.wav"
    transcripts_s3_folder = "transcripts"
    download_dir = "data/processing_audio"

    try:
        # Step 1: Download audio file from S3
        audio_s3_key = f"{audio_s3_folder}/{audio_file_name}"
        local_audio_path = download_from_s3(
            bucket_name=bucket_name,
            s3_key=audio_s3_key,
            download_path=Path(download_dir),
        )
        logger.debug(f"File downloaded to {local_audio_path}")

        # Step 2: Transcribe the downloaded audio file
        transcript = transcribe_from_local(audio_path=local_audio_path)

        logger.info(f"Transcript: {transcript}")

        # Step 3: Define the S3 key for the transcript
        transcript_file_name = f"{local_audio_path.stem}_transcript.txt"
        transcript_s3_key = f"{transcripts_s3_folder}/{transcript_file_name}"

        # Step 4: Upload the transcript to the destination S3 bucket
        upload_to_s3(
            bucket_name=bucket_name,
            s3_key=transcript_s3_key,
            content=transcript,
        )
        logger.debug(f"uploaded transcript to: {bucket_name}/{transcript_s3_key}")

        # Step 5: Delete the original audio file from S3
        original_s3_key = f"{audio_s3_folder}/{local_audio_path.name}"
        remove_s3_file(
            bucket_name=bucket_name,
            s3_key=original_s3_key,
        )
        logger.debug(f"Remove s3 file: {bucket_name}/{original_s3_key}")

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        sys.exit(1)
    finally:
        # Step 6: Clean up by removing the local audio file
        if "local_audio_path" in locals() and local_audio_path.exists():
            try:
                local_audio_path.unlink()
                logger.info(f"Removed local file {local_audio_path}")
            except Exception as e:
                logger.warning(f"Failed to remove local file {local_audio_path}: {e}")


def main():
    # audio_path = Path("data/20241120_130749.wav")
    # response = transcribe_from_local(audio_path=audio_path)
    # logger.info(f"Transcription: {response}")

    transcribe_and_upload()


if __name__ == "__main__":
    main()
