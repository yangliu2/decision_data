from decision_data.backend.services.controller import (
    get_current_hour,
    automation_controler,
)
from pathlib import Path
from decision_data.backend.config.config import backend_config
from datetime import datetime, timezone
import pytest


def test_get_current_time():
    # Arrange
    offset = 0

    # Act
    current_time = get_current_hour(offset)

    # Assert
    assert isinstance(current_time, int)


@pytest.fixture
def mock_transcribe_and_upload(mocker):
    return mocker.patch(
        "decision_data.backend.services.controller.transcribe_and_upload"
    )


@pytest.fixture
def mock_generate_summary(mocker):
    return mocker.patch("decision_data.backend.services.controller.generate_summary")


@pytest.fixture
def mock_time_sleep(mocker):
    return mocker.patch("time.sleep")


@pytest.fixture
def mock_datetime_now(mocker):
    mock_datetime = mocker.patch("decision_data.backend.services.controller.datetime")
    mock_datetime.now.return_value = datetime(
        2024, 12, 21, 12, 0, 0, tzinfo=timezone.utc
    )
    return mock_datetime


def test_automation_controler(
    mock_transcribe_and_upload,
    mock_generate_summary,
    mock_time_sleep,
    mock_datetime_now,
):
    # Arrange
    backend_config.DAILY_RESET_HOUR = 0
    backend_config.TIME_OFFSET_FROM_UTC = 0
    backend_config.DAILY_SUMMARY_HOUR = 12
    backend_config.TRANSCRIBER_INTERVAL = 1

    # Use a counter to break the loop after a few iterations
    loop_counter = 0
    max_iterations = 3

    def side_effect(*args, **kwargs):
        nonlocal loop_counter
        loop_counter += 1
        if loop_counter >= max_iterations:
            raise KeyboardInterrupt

    mock_time_sleep.side_effect = side_effect

    # Act
    try:
        automation_controler()
    except KeyboardInterrupt:
        pass

    # Assert
    assert mock_transcribe_and_upload.call_count == max_iterations
    mock_generate_summary.assert_called_once_with(
        year="2024",
        month="12",
        day="21",
        prompt_path=Path(backend_config.DAILY_SUMMAYR_PROMPT_PATH),
    )
    assert mock_time_sleep.call_count == max_iterations


def test_automation_controler_reset(
    mock_transcribe_and_upload,
    mock_generate_summary,
    mock_time_sleep,
    mock_datetime_now,
):
    # Arrange
    backend_config.DAILY_RESET_HOUR = 0
    backend_config.TIME_OFFSET_FROM_UTC = 0
    backend_config.DAILY_SUMMARY_HOUR = 12
    backend_config.TRANSCRIBER_INTERVAL = 1

    # Simulate time just before reset
    mock_datetime_now.now.return_value = datetime(
        2024, 12, 21, 23, 59, 59, tzinfo=timezone.utc
    )

    # Use a counter to break the loop after a few iterations
    loop_counter = 0
    max_iterations = 3

    def side_effect(*args, **kwargs):
        nonlocal loop_counter
        loop_counter += 1
        if loop_counter >= max_iterations:
            raise KeyboardInterrupt

    mock_time_sleep.side_effect = side_effect

    # Act
    try:
        automation_controler()
    except KeyboardInterrupt:
        pass

    # Assert
    assert mock_transcribe_and_upload.call_count == max_iterations
    mock_generate_summary.assert_not_called()
    assert mock_time_sleep.call_count == max_iterations
