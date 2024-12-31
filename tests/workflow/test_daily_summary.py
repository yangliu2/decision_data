import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from decision_data.backend.workflow.daily_summary import generate_summary
from decision_data.data_structure.models import DailySummary


@pytest.fixture
def mock_mongo_client():
    with patch("decision_data.backend.workflow.daily_summary.MongoDBClient") as mock:
        yield mock


@pytest.fixture
def mock_openai_client():
    with patch("decision_data.backend.workflow.daily_summary.OpenAI") as mock:
        yield mock


@pytest.fixture
def mock_email_functions():
    with patch(
        "decision_data.backend.workflow.daily_summary.send_email"
    ) as mock_send_email, patch(
        "decision_data.backend.workflow.daily_summary.format_message"
    ) as mock_format_message:
        yield mock_send_email, mock_format_message


def test_generate_summary_no_transcripts(
    mock_mongo_client, mock_openai_client, mock_email_functions
):
    # Arrange
    mock_mongo_instance = MagicMock()
    mock_mongo_client.return_value = mock_mongo_instance
    mock_mongo_instance.get_records_between_dates.return_value = []

    prompt_path = Path("decision_data/prompts/daily_summary.txt")
    prompt_path.write_text("Daily summary prompt: {daily_transcript}")

    # Act
    generate_summary(year="2024", month="12", day="11", prompt_path=prompt_path)

    # Assert
    mock_mongo_instance.get_records_between_dates.assert_called_once()


def test_generate_summary_with_transcripts(
    mock_mongo_client, mock_openai_client, mock_email_functions
):
    # Arrange
    mock_mongo_instance = MagicMock()
    mock_mongo_client.return_value = mock_mongo_instance
    mock_mongo_instance.get_records_between_dates.return_value = [
        {
            "transcript": "Test transcript 3",
            "length_in_seconds": 0.0,
            "original_audio_path": "Test path",
            "created_utc": "2024-12-11T00:00:00Z",
        },
    ]

    mock_openai_instance = MagicMock()
    mock_openai_client.return_value = mock_openai_instance
    mock_openai_instance.beta.chat.completions.parse.return_value = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    parsed=DailySummary(
                        business_info=["Business info"],
                        family_info=["Family info"],
                        misc_info=["Misc info"],
                    )
                )
            )
        ]
    )

    prompt_path = Path("decision_data/prompts/daily_summary.txt")
    prompt_path.write_text("Daily summary prompt: {daily_transcript}")

    # Act
    generate_summary(year="2024", month="12", day="11", prompt_path=prompt_path)

    # Assert
    mock_mongo_instance.get_records_between_dates.assert_called_once()
    mock_openai_instance.beta.chat.completions.parse.assert_called_once()
    mock_email_functions[0].assert_called_once()
    mock_email_functions[1].assert_called_once()
    mock_mongo_instance.insert_daily_summary.assert_called_once()
