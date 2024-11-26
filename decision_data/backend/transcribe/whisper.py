""" Using OpenAI services to do speech transcription """

from openai import OpenAI
from pathlib import Path
from loguru import logger
import sys
import wave
from decision_data.backend.config.config import backend_config
from decision_data.backend.transcribe.aws_s3 import (
    download_from_s3,
    upload_to_s3,
    remove_s3_file,
    list_s3_files,
)
from decision_data.backend.utils.logger import setup_logger

setup_logger()


def get_audio_duration(audio_path: Path) -> float:
    """Get duration of a WAV audio file in seconds.

    :param audio_path: Path to the audio file.
    :return: Duration in seconds.
    """
    with wave.open(str(audio_path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        duration = frames / float(rate)
    return duration


def transcribe_from_local(audio_path: Path) -> str:
    """Transcribe audio file using Whiper service

    :param audio_path: local audio path file
    :type audio_path: Path
    :return: transcription
    :rtype: str
    """
    client = OpenAI(api_key=backend_config.OPENAI_API_KEY)
    with audio_path.open("rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )
    return transcription.text


def transcribe_and_upload_one(
    bucket_name: str,
    audio_s3_folder: str,
    audio_s3_key: str,
    download_dir: str = "data/processing_audio",
) -> None:
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
    transcripts_s3_folder = backend_config.AWS_S3_TRANSCRIPT_FOLDER
    download_dir = "data/processing_audio"

    try:
        # Step 1: Download audio file from S3
        local_audio_path = download_from_s3(
            bucket_name=bucket_name,
            s3_key=audio_s3_key,
            download_path=Path(download_dir),
        )
        logger.debug(f"File downloaded to {local_audio_path}")

        # Step 2: Check audio duration
        duration = get_audio_duration(audio_path=local_audio_path)
        logger.debug(f"Audio duration: {duration} seconds")

        # openai will not take audio shorter than 0.1 seconds
        if duration < 0.1:
            logger.info(
                f"Audio duration is less than 0.1 seconds. Deleting file from "
                f"S3: {audio_s3_key}"
            )
            remove_s3_file(
                bucket_name=bucket_name,
                s3_key=audio_s3_key,
            )
            logger.info(f"Deleted S3 file: s3://{bucket_name}/{audio_s3_key}")
            return  # Exit the function early

        # Step 3: Transcribe the downloaded audio file
        transcript = transcribe_from_local(audio_path=local_audio_path)

        logger.info(f"Transcript: {transcript}")

        # Step 4: Define the S3 key for the transcript
        transcript_file_name = f"{local_audio_path.stem}_transcript.txt"
        transcript_s3_key = f"{transcripts_s3_folder}/{transcript_file_name}"

        # Step 5: Upload the transcript to the destination S3 bucket
        upload_to_s3(
            bucket_name=bucket_name,
            s3_key=transcript_s3_key,
            content=transcript,
        )
        logger.debug(f"uploaded transcript to: {bucket_name}/{transcript_s3_key}")

        # Step 6: Delete the original audio file from S3
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
        # Step 7: Clean up by removing the local audio file
        if "local_audio_path" in locals() and local_audio_path.exists():
            try:
                local_audio_path.unlink()
                logger.info(f"Removed local file {local_audio_path}")
            except Exception as e:
                logger.warning(f"Failed to remove local file {local_audio_path}: {e}")


def transcribe_and_upload():
    """Transcribe all audio from s3 folder

    :param bucket_name: s3 bucket name
    :type bucket_name: str
    :param audio_s3_folder: the folder or s3 key that contains the audio files
    :type audio_s3_folder: str
    """
    bucket_name = backend_config.AWS_S3_BUCKET_NAME

    # Get all files in the folder
    audio_files = list_s3_files(
        bucket_name=bucket_name,
        prefix=backend_config.AWS_S3_AUDIO_FOLDER,
    )

    # Transcribe for each file individually
    for audio_file in audio_files:
        transcribe_and_upload_one(
            bucket_name=bucket_name,
            audio_s3_folder=backend_config.AWS_S3_AUDIO_FOLDER,
            audio_s3_key=audio_file,
        )
        break


def main():

    transcribe_and_upload()


if __name__ == "__main__":
    main()