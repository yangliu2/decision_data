""" Manipulations for aws s3 buckets """

import boto3
from pathlib import Path
from loguru import logger
from mypy_boto3_s3 import S3Client
from decision_data.backend.config.config import backend_config
from botocore.exceptions import BotoCoreError, ClientError


def get_s3_client() -> S3Client:
    """Get a s3 client

    :return: s3 client seesion
    :rtype: Session
    """
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY,
        region_name=backend_config.REGION_NAME,
    )
    return s3_client


def download_from_s3(
    bucket_name: str,
    s3_key: str,
    download_path: Path,
) -> Path:
    """
    Download a file from an S3 bucket to a local directory.

    Args:
        bucket_name (str): Name of the source S3 bucket.
        s3_key (str): Key (path) of the file in the S3 bucket.
        download_path (Path): Local directory path where the file will be saved.

    Returns:
        Path: The local path to the downloaded file.

    Raises:
        FileNotFoundError: If the S3 object does not exist.
        BotoCoreError: For other boto3 related errors.
    """
    # Ensure the download directory exists
    download_path.mkdir(parents=True, exist_ok=True)

    # Extract the file name from the S3 key
    file_name = Path(s3_key).name
    local_file_path = download_path / file_name

    # Initialize S3 client
    s3_client = get_s3_client()

    try:
        logger.info(f"Starting download of {s3_key} from bucket {bucket_name}")
        s3_client.download_file(bucket_name, s3_key, str(local_file_path))
        logger.info(f"Downloaded {s3_key} to {local_file_path}")
        return local_file_path
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            logger.error(f"The object {s3_key} does not exist in bucket {bucket_name}.")
            raise FileNotFoundError(
                f"The object {s3_key} does not exist in bucket {bucket_name}."
            )
        else:
            logger.error(f"ClientError while downloading {s3_key}: {e}")
            raise
    except BotoCoreError as e:
        logger.error(f"BotoCoreError while downloading {s3_key}: {e}")
        raise


def upload_to_s3(
    bucket_name: str,
    s3_key: str,
    content: str,
) -> None:
    """
    Upload a transcript string to an S3 bucket.

    Args:
        bucket_name (str): Name of the destination S3 bucket.
        s3_key (str): Key (path) where the transcript will be stored in S3.
        content (str): The transcript text to upload.

    Raises:
        BotoCoreError: For boto3 related errors during upload.
    """
    # Initialize S3 client
    s3_client = get_s3_client()

    try:
        logger.info(f"Uploading transcript to {bucket_name}/{s3_key}")
        s3_client.put_object(Bucket=bucket_name, Key=s3_key, Body=content)
        logger.info(f"Successfully uploaded transcript to {bucket_name}/{s3_key}")
    except BotoCoreError as e:
        logger.error(f"Error uploading transcript to S3: {e}")
        raise


def remove_s3_file(
    bucket_name: str,
    s3_key: str,
):
    # Initialize S3 client
    s3_client = get_s3_client()

    try:
        s3_client.delete_object(Bucket=bucket_name, Key=s3_key)
        logger.info(f"Deleted original audio file from s3://{bucket_name}/{s3_key}")
    except ClientError as e:
        logger.error(f"Failed to delete original audio file from S3: {e}")
        # Depending on your requirements, you might want to raise an exception here
        # raise
