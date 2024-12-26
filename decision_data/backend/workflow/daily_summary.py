from decision_data.backend.data.mongodb_client import MongoDBClient
from decision_data.backend.config.config import backend_config
from decision_data.data_structure.models import Transcript

from loguru import logger


def generate_summary(
    year: str,
    month: str,
    day: str,
):
    """Generate a summary of all transcripts on a given day."""
    # Step 1: Filter transcription by time

    mongo_client = MongoDBClient(
        uri=backend_config.MONGODB_URI,
        db=backend_config.MONGODB_DB_NAME,
        collection=backend_config.MONGODB_TRANSCRIPTS_COLLECTION_NAME,
    )

    date_field = "created_utc"
    next_day = str(int(day) + 1)
    start_data_str = f"{year}-{month}-{day}T00:00:00Z"
    end_date_str = f"{year}-{month}-{next_day}T00:00:00Z"

    filtered_data = mongo_client.get_records_between_dates(
        date_field=date_field,
        start_date_str=start_data_str,
        end_date_str=end_date_str,
    )

    logger.debug(f"number of transcript on day {day}: {len(filtered_data)}")

    # Step 2: Combine all transcript into a single text

    filtered_objects = [Transcript(**x) for x in filtered_data]

    transcripts = [x.transcript for x in filtered_objects]
    combined_text = " ".join(transcripts)
    logger.debug(f"combined text: {combined_text}")

    # Step 3: Summarize the text using LLM


def main():

    generate_summary(
        year="2024",
        month="12",
        day="10",
    )


if __name__ == "__main__":
    main()
