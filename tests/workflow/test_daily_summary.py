import pytest
from unittest.mock import patch
from pathlib import Path
from decision_data.backend.workflow.daily_summary import generate_summary
import tempfile


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


def test_generate_summary(
    mocker,
    mock_mongo_client,
    mock_openai_client,
    mock_email_functions,
):
    # Arrange
    mock_mongo_instance = mock_mongo_client.return_value
    mock_openai_instance = mock_openai_client.return_value

    with tempfile.NamedTemporaryFile(delete=False) as temp_prompt_file:
        temp_prompt_file.write(b"Daily summary prompt: {daily_transcript}")
        temp_prompt_file_path = Path(temp_prompt_file.name)

    # Act
    generate_summary(
        year="2024",
        month="12",
        day="11",
        prompt_path=temp_prompt_file_path,
    )

    # Assert
    mock_mongo_instance.get_records_between_dates.assert_called_once()
    mock_openai_instance.beta.chat.completions.parse.assert_called_once()
    mock_email_functions[0].assert_called_once()
    mock_email_functions[1].assert_called_once()
    mock_mongo_instance.insert_daily_summary.assert_called_once()

    # Clean up
    temp_prompt_file_path.unlink()
