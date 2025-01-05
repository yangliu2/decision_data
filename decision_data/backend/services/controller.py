""" Using whisper as transcribe service """

import time
from datetime import datetime, timezone
from pathlib import Path
from decision_data.backend.transcribe.whisper import transcribe_and_upload
from decision_data.backend.config.config import backend_config
from decision_data.backend.workflow.daily_summary import generate_summary


def get_current_hour(offset: int) -> int:
    """Get the current hour with offset

    :param offset: time off set from the user's current time to UTC. + for
    ahead of UTC, - for behind UTC
    :type offset: int
    :return: offset hour
    :rtype: int
    """
    current_hour = datetime.now(timezone.utc).hour
    return current_hour + offset


def is_time_to_send_daily_summary():
    """Check if it is time to send daily summary"""
    current_hour_utc = get_current_hour(offset=backend_config.TIME_OFFSET_FROM_UTC)
    return current_hour_utc == backend_config.DAILY_SUMMARY_HOUR


def is_reset_time():
    """Check if it is time to reset time flags for the day"""
    current_hour_utc = get_current_hour(offset=backend_config.TIME_OFFSET_FROM_UTC)
    return current_hour_utc == backend_config.DAILY_RESET_HOUR


def automation_controler():
    """Main service controller for running the backend services"""

    sent_daily = False

    while True:
        current_utc_time = datetime.now(timezone.utc)

        # Reset all flags
        if is_reset_time():
            sent_daily = False

        # Transcribe audio and upload to s3
        transcribe_and_upload()

        # Generate daily summary at the specified time
        if is_time_to_send_daily_summary() and not sent_daily:
            prompt_path = Path(backend_config.DAILY_SUMMAYR_PROMPT_PATH)
            generate_summary(
                year=str(current_utc_time.year),
                month=str(current_utc_time.month),
                day=str(current_utc_time.day),
                prompt_path=prompt_path,
            )
            sent_daily = True

        time.sleep(backend_config.TRANSCRIBER_INTERVAL)


def main():
    automation_controler()


if __name__ == "__main__":
    main()
