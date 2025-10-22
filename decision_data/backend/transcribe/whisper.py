""" Using OpenAI services to do speech transcription """

from openai import OpenAI
from pathlib import Path
from loguru import logger
import wave
import time
from datetime import datetime, timezone
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
    """Get duration of an audio file in seconds.

    Supports WAV files via wave module. For other formats (like 3gp),
    returns a default duration since we validate duration at upload time.

    :param audio_path: Path to the audio file.
    :return: Duration in seconds.
    """
    try:
        # Try WAV format first
        with wave.open(str(audio_path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            duration = frames / float(rate)
        return duration
    except wave.Error:
        # For non-WAV files (like 3gp), return a reasonable default
        # Duration validation happens at upload time with file metadata
        logger.warning(f"Cannot read duration from {audio_path.suffix} file, using file size estimate")
        # Estimate: ~1KB per second for 3gp audio (very rough)
        file_size_bytes = audio_path.stat().st_size
        estimated_duration = file_size_bytes / 1000.0
        return max(5.0, min(estimated_duration, 30.0))  # Clamp between 5-30 seconds


def convert_to_supported_format(audio_path: Path) -> Path:
    """Convert audio file to MP3 format supported by OpenAI Whisper.

    OpenAI Whisper supports: flac, m4a, mp3, mp4, mpeg, mpga, oga, ogg, wav, webm
    This function converts 3gp and other unsupported formats to mp3.

    :param audio_path: Path to the original audio file
    :return: Path to the converted audio file (or original if already supported)
    """
    import subprocess

    # Supported formats by OpenAI Whisper
    supported_formats = {'.flac', '.m4a', '.mp3', '.mp4', '.mpeg', '.mpga', '.oga', '.ogg', '.wav', '.webm'}

    if audio_path.suffix.lower() in supported_formats:
        logger.info(f"Audio format {audio_path.suffix} already supported, no conversion needed")
        return audio_path

    # Convert to mp3
    output_path = audio_path.with_suffix('.mp3')
    logger.info(f"Converting {audio_path.suffix} to mp3 format: {output_path}")

    try:
        # Use ffmpeg to convert
        subprocess.run([
            'ffmpeg',
            '-i', str(audio_path),
            '-acodec', 'libmp3lame',
            '-ar', '16000',  # 16kHz sample rate (good for speech)
            '-ac', '1',      # Mono channel
            '-b:a', '32k',   # 32kbps bitrate (sufficient for speech)
            '-y',            # Overwrite output file
            str(output_path)
        ], check=True, capture_output=True, timeout=30)

        logger.info(f"Successfully converted to mp3: {output_path}")

        # Delete original file to save space
        audio_path.unlink()

        return output_path

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to convert audio file: {e.stderr.decode()}")
        raise Exception(f"Audio conversion failed: {e.stderr.decode()}")
    except FileNotFoundError:
        raise Exception("ffmpeg is not installed. Please install ffmpeg: apt-get install ffmpeg")
    except subprocess.TimeoutExpired:
        raise Exception("Audio conversion timed out after 30 seconds")


def transcribe_from_local(audio_path: Path) -> str:
    """Transcribe audio file using Whisper service.

    Automatically converts unsupported formats (like 3gp) to mp3 before transcription.

    :param audio_path: local audio path file
    :type audio_path: Path
    :return: transcription
    :rtype: str
    """
    # Convert to supported format if needed
    converted_path = convert_to_supported_format(audio_path)

    client = OpenAI(api_key=backend_config.OPENAI_API_KEY)
    with converted_path.open("rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )
    return transcription.text


def get_utc_datetime() -> str:
    """Get utc time

    :return: utc time in string format
    :rtype: str
    """
    # Get the current UTC datetime
    now_utc = datetime.now(timezone.utc)

    # Format UTC datetime
    utc_datetime = now_utc.strftime("%Y-%m-%d %H:%M:%S %Z")

    return utc_datetime


def transcribe_and_upload_one(
    bucket_name: str,
    audio_s3_folder: str,
    audio_s3_key: str,
    download_dir: str = "data/processing_audio",
    min_duration: float = 3.0,
    max_duration: float = 30.0,
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
        min_duration (int): Minimum audio length for transcription. Default to
        3.0 seconds.
        max_duration (int): Maximum audio length for transcription. Default to
        30.0 seconds. This is the limite whipser can handle.

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
        original_audio_path = f"s3://{bucket_name}/{audio_s3_key}"
        logger.debug(f"File downloaded to {local_audio_path}")

        # Step 2: Check audio duration
        duration = get_audio_duration(audio_path=local_audio_path)
        logger.debug(f"Audio duration: {duration} seconds")

        # openai will not take audio shorter than min duration
        if min_duration < duration < max_duration:
            logger.info(
                f"Audio duration is less than {min_duration} seconds, or "
                f"longer than {max_duration}. Deleting"
                f"file from S3: {audio_s3_key}"
            )
            remove_s3_file(
                bucket_name=bucket_name,
                s3_key=audio_s3_key,
            )
            logger.info(f"Deleted S3 file: {original_audio_path}")
            return  # Exit the function early

        # Step 3: Transcribe the downloaded audio file
        transcript = transcribe_from_local(audio_path=local_audio_path)

        logger.info(f"Transcript: {transcript}")

        # Step 4: Define the S3 key for the transcript
        transcript_file_name = f"{local_audio_path.stem}_transcript.txt"
        transcript_s3_key = f"{transcripts_s3_folder}/{transcript_file_name}"

        # NOTE: Transcripts are now saved to DynamoDB only (via transcription_service)
        # MongoDB has been removed entirely for data privacy and security

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
        raise
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


def main():

    while True:
        transcribe_and_upload()
        time.sleep(600)


if __name__ == "__main__":
    main()
