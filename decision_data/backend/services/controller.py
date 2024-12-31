""" Using whisper as transcribe service """

import time
from datetime import datetime
from pathlib import Path
from decision_data.backend.transcribe.whisper import transcribe_and_upload
from decision_data.backend.config.config import backend_config
from decision_data.backend.workflow.daily_summary import generate_summary


def get_current_hour(offset: int = 0) -> int:
    current_hour = datetime.now().hour
    return current_hour - offset


def automation_controler():
    sent_daily = False

    while True:
        # Reset all flags at 2 am
        if get_current_hour() == 2:
            sent_daily = False

        # Transcribe audio and upload to s3
        transcribe_and_upload()

        # Generate daily summary at the specified time
        if (
            get_current_hour(offset=backend_config.TIME_OFFSET)
            == backend_config.DAILY_SUMMARY_HOUR
        ) and not sent_daily:
            prompt_path = Path("decision_data/prompts/daily_summary.txt")
            generate_summary(
                year="2022",
                month="03",
                day="01",
                prompt_path=prompt_path,
            )
            sent_daily = True

        time.sleep(60)


def main():
    automation_controler()


if __name__ == "__main__":
    main()
