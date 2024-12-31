import pytest
from unittest.mock import patch, MagicMock
from decision_data.backend.transcribe.whisper import (
    get_utc_datetime,
    save_to_mongodb,
    transcribe_and_upload,
)


@pytest.fixture
def mock_openai_client():
    with patch("decision_data.backend.transcribe.whisper.OpenAI") as mock:
        yield mock


@pytest.fixture
def mock_mongo_client():
    with patch("decision_data.backend.transcribe.whisper.MongoDBClient") as mock:
        yield mock


@pytest.fixture
def mock_s3_functions():
    with patch(
        "decision_data.backend.transcribe.whisper.download_from_s3"
    ) as mock_download, patch(
        "decision_data.backend.transcribe.whisper.upload_to_s3"
    ) as mock_upload, patch(
        "decision_data.backend.transcribe.whisper.remove_s3_file"
    ) as mock_remove, patch(
        "decision_data.backend.transcribe.whisper.list_s3_files"
    ) as mock_list:
        yield mock_download, mock_upload, mock_remove, mock_list


@pytest.fixture
def mock_time_sleep():
    with patch("time.sleep") as mock:
        yield mock


def test_get_utc_datetime():
    # Act
    utc_datetime = get_utc_datetime()

    # Assert
    assert isinstance(utc_datetime, str)


def test_save_to_mongodb(mock_mongo_client):
    # Arrange
    transcript = "Test transcript"
    duration = 60.0
    original_audio_path = "s3://bucket/audio.wav"
    mock_mongo_instance = MagicMock()
    mock_mongo_client.return_value = mock_mongo_instance

    # Act
    save_to_mongodb(transcript, duration, original_audio_path)

    # Assert
    mock_mongo_instance.insert_transcripts.assert_called_once()


def test_transcribe_and_upload(mock_s3_functions):
    # Arrange
    audio_files = ["audio1.wav", "audio2.wav"]
    _, _, _, mock_list = mock_s3_functions
    mock_list.return_value = audio_files

    with patch(
        "decision_data.backend.transcribe.whisper.transcribe_and_upload_one"
    ) as mock_transcribe_and_upload_one:
        # Act
        transcribe_and_upload()

        # Assert
        assert mock_transcribe_and_upload_one.call_count == len(audio_files)
