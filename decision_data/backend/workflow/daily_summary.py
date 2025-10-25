from loguru import logger
from openai import OpenAI
from pathlib import Path
from pydantic import ValidationError
from datetime import datetime, timedelta
import boto3
from decimal import Decimal
import uuid
from decision_data.backend.config.config import backend_config
from decision_data.data_structure.models import DailySummary
from decision_data.backend.utils.logger import setup_logger
from decision_data.ui.email.email import send_email, format_message

setup_logger()


def generate_summary(
    year: str,
    month: str,
    day: str,
    prompt_path: Path,
    user_id: str = None,
    recipient_email: str = None,
):
    """Generate a summary of all transcripts on a given day.

    Args:
        year: Year (YYYY)
        month: Month (MM)
        day: Day (DD)
        prompt_path: Path to the prompt file
        user_id: Optional user ID (for filtering transcripts by user)
        recipient_email: Optional recipient email (if not provided, uses GMAIL_ACCOUNT from config)
    """
    # Step 1: Query transcripts from DynamoDB

    dynamodb = boto3.resource(
        'dynamodb',
        region_name=backend_config.REGION_NAME,
        aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY
    )

    transcripts_table = dynamodb.Table('panzoto-transcripts')

    # Create datetime objects for start and end of the day
    start_datetime = datetime(int(year), int(month), int(day)) + timedelta(days=-1)
    end_datetime = start_datetime + timedelta(days=1)

    # Format the datetime objects to the required ISO format
    start_date_str = start_datetime.strftime("%Y-%m-%dT%H:%M:%S")
    end_date_str = end_datetime.strftime("%Y-%m-%dT%H:%M:%S")

    # Query transcripts from DynamoDB within date range
    try:
        response = transcripts_table.scan(
            FilterExpression='created_at BETWEEN :start AND :end' +
                           (' AND user_id = :user_id' if user_id else ''),
            ExpressionAttributeValues={
                ':start': start_date_str,
                ':end': end_date_str,
                **(
                    {':user_id': user_id} if user_id else {}
                )
            }
        )
        filtered_data = response.get('Items', [])
    except Exception as e:
        logger.error(f"Failed to query transcripts from DynamoDB: {e}")
        return

    logger.debug(f"number of transcripts on day {day}: {len(filtered_data)}")

    # Step 2: Combine all transcript into a single text

    if not filtered_data:
        logger.info(f"No transcripts found for {year}-{month}-{day}, sending empty summary email")

        # Send email even when no transcripts found
        subject = "PANZOTO: Daily Summary"
        date = f"{year}-{month}-{day}"
        formated_message = f"""
        <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>Daily Summary for {date}</h2>
                <p>No conversations recorded for this day.</p>
            </body>
        </html>
        """

        final_recipient_email = recipient_email or backend_config.GMAIL_ACCOUNT

        try:
            send_email(
                subject=subject,
                message_body=formated_message,
                recipient_email=final_recipient_email,
            )
            logger.info(f"[EMAIL] Empty summary sent to {final_recipient_email}")
        except Exception as e:
            logger.error(f"Failed to send empty summary email: {e}")

        return

    transcripts = [x['transcript'] for x in filtered_data]
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

    if not parsed_response:
        raise ValueError("Parsed response is None")

    # If there is no information, do not send the email or save to database
    if (
        not parsed_response.business_info
        and not parsed_response.family_info
        and not parsed_response.misc_info
    ):
        logger.info("No information to summarize.")
        return

    # Step 4: Send the summary to myself using email
    subject = "PANZOTO: Daily Summary"
    date = f"{year}-{month}-{day}"
    formated_message = format_message(
        llm_resopnse=parsed_response,
        date=date,
    )

    # Use provided email or fallback to config
    final_recipient_email = recipient_email or backend_config.GMAIL_ACCOUNT

    send_email(
        subject=subject,
        message_body=formated_message,
        recipient_email=final_recipient_email,
    )

    logger.info(f"[EMAIL] Daily summary sent to {final_recipient_email}")

    # Step 5: Save the summary to DynamoDB
    try:
        summaries_table = dynamodb.Table('panzoto-daily-summaries')
        summary_record = parsed_response.model_dump()
        summary_record['summary_id'] = str(uuid.uuid4())
        summary_record['date'] = date
        summary_record['created_at'] = datetime.utcnow().isoformat()

        # Only include user_id if provided (for filtering)
        if user_id:
            summary_record['user_id'] = user_id

        summaries_table.put_item(Item=summary_record)
        logger.info(f"Saved daily summary to DynamoDB for {date}")
    except Exception as e:
        logger.error(f"Failed to save summary to DynamoDB: {e}")
        raise


def main():

    prompt_path = Path("decision_data/prompts/daily_summary.txt")
    generate_summary(
        year="2025",
        month="01",
        day="03",
        prompt_path=prompt_path,
    )


if __name__ == "__main__":
    main()
