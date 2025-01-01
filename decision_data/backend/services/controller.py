""" Using whisper as transcribe service """

import time
from datetime import datetime
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
    current_hour = datetime.now().hour
    return current_hour + offset


def automation_controler():
    """Main service controller for running the backend services"""

    sent_daily = False

    while True:
        current_time = datetime.now()

        # Reset all flags
        if current_time.hour == backend_config.DAILY_RESET_HOUR:
            sent_daily = False

        # Transcribe audio and upload to s3
        transcribe_and_upload()

        # Generate daily summary at the specified time
        if (
            get_current_hour(offset=backend_config.TIME_OFFSET_FROM_UTC)
            == backend_config.DAILY_SUMMARY_HOUR
        ) and not sent_daily:
            prompt_path = Path(backend_config.DAILY_SUMMAYR_PROMPT_PATH)
            generate_summary(
                year=str(current_time.year),
                month=str(current_time.month),
                day=str(current_time.day),
                prompt_path=prompt_path,
            )
            sent_daily = True

        time.sleep(backend_config.TRANSCRIBER_INTERVAL)


def main():
    automation_controler()


if __name__ == "__main__":
    main()
