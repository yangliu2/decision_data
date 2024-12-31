from loguru import logger
from openai import OpenAI
from pathlib import Path
from decision_data.backend.data.mongodb_client import MongoDBClient
from decision_data.backend.config.config import backend_config
from decision_data.data_structure.models import Transcript
from decision_data.backend.utils.logger import setup_logger
from decision_data.data_structure.models import DailySummary
from decision_data.ui.email.email import send_email, format_message

setup_logger()


def generate_summary(
    year: str,
    month: str,
    day: str,
    prompt_path: Path,
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
    mongo_client.close()

    logger.debug(f"number of transcript on day {day}: {len(filtered_data)}")

    # Step 2: Combine all transcript into a single text

    filtered_objects = [Transcript(**x) for x in filtered_data]

    transcripts = [x.transcript for x in filtered_objects]
    combined_text = " ".join(transcripts)
    # logger.debug(f"combined text: {combined_text}")

    # Step 3: Summarize the text using LLM
    daily_summary_prompt = prompt_path.read_text()

    user_prompt = daily_summary_prompt.format(daily_transcript=combined_text)
    logger.debug(f"user prompt: {user_prompt}")

    client = OpenAI(api_key=backend_config.OPENAI_API_KEY)

    completion = client.beta.chat.completions.parse(
        model=backend_config.OPENAI_MODEL,
        messages=[
            {"role": "user", "content": user_prompt},
        ],
        response_format=DailySummary,
    )

    parsed_response = completion.choices[0].message.parsed

    if parsed_response is None:
        raise ValueError("Parsed response is None")

    # Step 4: Send the summary to myself using email
    subject = "PANZOTO: Daily Summary"
    date = f"{year}-{month}-{day}"
    formated_message = format_message(
        llm_resopnse=parsed_response,
        date=date,
    )

    send_email(
        subject=subject,
        message_body=formated_message,
        recipient_email=backend_config.GMAIL_ACCOUNT,
    )

    # Step 5: Save the summary to MongoDB
    mongo_client = MongoDBClient(
        uri=backend_config.MONGODB_URI,
        db=backend_config.MONGODB_DB_NAME,
        collection=backend_config.MONGODB_DAILY_SUMMARY_COLLECTION_NAME,
    )
    record = parsed_response.model_dump()
    record[date_field] = date
    mongo_client.insert_daily_summary(summary_data=[record])
    logger.info(f"Inserted one summary on day: {start_data_str}.")
    mongo_client.close()


def main():

    prompt_path = Path("decision_data/prompts/daily_summary.txt")
    generate_summary(
        year="2024",
        month="12",
        day="11",
        prompt_path=prompt_path,
    )


if __name__ == "__main__":
    main()
