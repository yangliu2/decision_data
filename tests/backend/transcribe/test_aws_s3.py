import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from botocore.exceptions import ClientError, BotoCoreError
from decision_data.backend.transcribe.aws_s3 import (
    upload_to_s3,
    list_s3_files,
    download_from_s3,
    get_s3_client,
)
from decision_data.backend.config.config import backend_config


@pytest.fixture
def mock_s3_client():
    with patch("decision_data.backend.transcribe.aws_s3.get_s3_client") as mock:
        yield mock


def test_get_s3_client():
    # Arrange
    with patch("boto3.client") as mock_boto_client:
        mock_boto_client.return_value = MagicMock()

        # Act
        client = get_s3_client()

        # Assert
        mock_boto_client.assert_called_once_with(
            "s3",
            aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY,
            region_name=backend_config.REGION_NAME,
        )
        assert client == mock_boto_client.return_value


def test_upload_to_s3(mock_s3_client):
    # Arrange
    bucket_name = "test-bucket"
    s3_key = "test/key.txt"
    content = "This is a test content"

    # Mock the S3 client
    mock_client = MagicMock()
    mock_s3_client.return_value = mock_client

    # Act
    upload_to_s3(bucket_name, s3_key, content)

    # Assert
    mock_client.put_object.assert_called_once_with(
        Bucket=bucket_name, Key=s3_key, Body=content
    )


def test_list_s3_files(mock_s3_client):
    # Arrange
    bucket_name = "test-bucket"
    prefix = "test/"
    mock_client = MagicMock()
    mock_s3_client.return_value = mock_client
    mock_client.get_paginator.return_value.paginate.return_value = [
        {"Contents": [{"Key": "test/file1.txt"}, {"Key": "test/file2.txt"}]}
    ]

    # Act
    result = list_s3_files(bucket_name, prefix)

    # Assert
    assert result == ["test/file1.txt", "test/file2.txt"]


def test_list_s3_files_client_error(mock_s3_client):
    # Arrange
    bucket_name = "test-bucket"
    prefix = "test/"
    mock_client = MagicMock()
    mock_s3_client.return_value = mock_client
    mock_client.get_paginator.side_effect = ClientError(
        {"Error": {"Code": "500", "Message": "Internal Server Error"}},
        "list_objects_v2",
    )

    # Act & Assert
    with pytest.raises(ClientError):
        list_s3_files(bucket_name, prefix)


def test_list_s3_files_botocore_error(mock_s3_client):
    # Arrange
    bucket_name = "test-bucket"
    prefix = "test/"
    mock_client = MagicMock()
    mock_s3_client.return_value = mock_client
    mock_client.get_paginator.side_effect = BotoCoreError()

    # Act & Assert
    with pytest.raises(BotoCoreError):
        list_s3_files(bucket_name, prefix)


def test_download_from_s3(mock_s3_client):
    # Arrange
    bucket_name = "test-bucket"
    s3_key = "test/file.txt"
    download_path = Path("/tmp")
    local_file_path = download_path / "file.txt"
    mock_client = MagicMock()
    mock_s3_client.return_value = mock_client

    # Act
    result = download_from_s3(bucket_name, s3_key, download_path)

    # Assert
    mock_client.download_file.assert_called_once_with(
        bucket_name, s3_key, str(local_file_path)
    )
    assert result == local_file_path


def test_download_from_s3_client_error(mock_s3_client):
    # Arrange
    bucket_name = "test-bucket"
    s3_key = "test/file.txt"
    download_path = Path("/tmp")
    mock_client = MagicMock()
    mock_s3_client.return_value = mock_client
    mock_client.download_file.side_effect = ClientError(
        {"Error": {"Code": "404", "Message": "Not Found"}}, "download_file"
    )

    # Act & Assert
    with pytest.raises(FileNotFoundError):
        download_from_s3(bucket_name, s3_key, download_path)


def test_download_from_s3_botocore_error(mock_s3_client):
    # Arrange
    bucket_name = "test-bucket"
    s3_key = "test/file.txt"
    download_path = Path("/tmp")
    mock_client = MagicMock()
    mock_s3_client.return_value = mock_client
    mock_client.download_file.side_effect = BotoCoreError()

    # Act & Assert
    with pytest.raises(BotoCoreError):
        download_from_s3(bucket_name, s3_key, download_path)
