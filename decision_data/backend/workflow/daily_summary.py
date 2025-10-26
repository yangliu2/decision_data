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
from decision_data.backend.utils.secrets_manager import SecretsManager
from decision_data.backend.utils.aes_encryption import AESEncryption
from decision_data.ui.email.email import send_email, format_message

setup_logger()

# Initialize encryption/decryption utilities
secrets_manager = SecretsManager()
aes_encryption = AESEncryption()


def generate_summary(
    year: str,
    month: str,
    day: str,
    prompt_path: Path,
    user_id: str = None,
    recipient_email: str = None,
    timezone_offset_hours: int = 0,
):
    """Generate a summary of all transcripts on a given day.

    Args:
        year: Year (YYYY)
        month: Month (MM)
        day: Day (DD)
        prompt_path: Path to the prompt file
        user_id: Optional user ID (for filtering transcripts by user)
        recipient_email: Optional recipient email (if not provided, uses GMAIL_ACCOUNT from config)
        timezone_offset_hours: User's timezone offset from UTC (e.g., -6 for CST)
    """
    # Step 1: Query transcripts from DynamoDB

    dynamodb = boto3.resource(
        'dynamodb',
        region_name=backend_config.REGION_NAME,
        aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY
    )

    transcripts_table = dynamodb.Table('panzoto-transcripts')

    # Create datetime objects for the requested day in UTC
    # When user requests summary for day D in their local timezone,
    # we need to query from D 00:00 in their timezone to D+1 00:00 in their timezone
    # which equals D minus offset 00:00 UTC to D+1 minus offset 00:00 UTC
    local_date = datetime(int(year), int(month), int(day))
    start_datetime = local_date + timedelta(hours=-timezone_offset_hours)
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

    # Step 2: Decrypt all transcripts and combine into a single text

    decrypted_transcripts = []
    encryption_key = None

    try:
        # Get encryption key once for the user
        encryption_key = secrets_manager.get_user_encryption_key(user_id)
        if not encryption_key:
            logger.warning(f"[DECRYPT] No encryption key found for user {user_id}, using encrypted data")
    except Exception as e:
        logger.warning(f"[DECRYPT] Failed to get encryption key: {e}")

    # Decrypt each transcript
    for item in filtered_data:
        try:
            encrypted_transcript_b64 = item.get('transcript', '')

            if encryption_key:
                # Decrypt the transcript
                decrypted_text = aes_encryption.decrypt_text(encrypted_transcript_b64, encryption_key)
                decrypted_transcripts.append(decrypted_text)
                logger.debug(f"[DECRYPT] Successfully decrypted transcript")
            else:
                # If we can't decrypt, use encrypted data as-is (will fail LLM processing)
                decrypted_transcripts.append(encrypted_transcript_b64)
                logger.debug(f"[DECRYPT] Using encrypted data (key unavailable)")
        except Exception as decrypt_error:
            logger.error(f"[DECRYPT] Failed to decrypt transcript: {decrypt_error}")
            # Skip this transcript if decryption fails
            continue

    if not decrypted_transcripts:

        logger.info(f"No transcripts found for {year}-{month}-{day}, sending empty summary email")

        # Send email even when no transcripts found
        subject = "Panzoto: Daily Summary"
        date = f"{year}-{month}-{day}"
        formated_message = f"""
        <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>Daily Summary for {date}</h2>
                <p>No conversations recorded for this day.</p>
            </body>
        </html>
        """

        final_recipient_email = recipient_email

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

    # Use decrypted transcripts for LLM processing
    combined_text = " ".join(decrypted_transcripts)
    logger.info(f"[SUMMARY] Combining {len(decrypted_transcripts)} decrypted transcripts for LLM")

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
    subject = "Panzoto: Daily Summary"
    date = f"{year}-{month}-{day}"
    formated_message = format_message(
        llm_resopnse=parsed_response,
        date=date,
    )

    # Use provided email (required for sending)
    final_recipient_email = recipient_email

    send_email(
        subject=subject,
        message_body=formated_message,
        recipient_email=final_recipient_email,
    )

    logger.info(f"[EMAIL] Daily summary sent to {final_recipient_email}")

    # Step 5: Save the summary to DynamoDB (encrypted)
    try:
        summaries_table = dynamodb.Table('panzoto-daily-summaries')
        summary_record = {}

        # Create summary ID and date fields
        summary_record['summary_id'] = str(uuid.uuid4())
        summary_record['summary_date'] = date
        summary_record['created_at'] = datetime.utcnow().isoformat()

        # Include user_id if provided (for filtering and access control)
        if user_id:
            summary_record['user_id'] = user_id

        # Convert the summary to JSON string and encrypt it
        import json
        summary_json = json.dumps(parsed_response.model_dump())

        if encryption_key:
            # Encrypt the summary using user's encryption key
            encrypted_summary = aes_encryption.encrypt_text(summary_json, encryption_key)
            summary_record['encrypted_summary'] = encrypted_summary
            logger.debug(f"[ENCRYPT] Encrypted summary ({len(summary_json)} bytes)")
        else:
            # Fallback: store unencrypted if key unavailable (log warning)
            logger.warning(f"[ENCRYPT] No encryption key available, storing unencrypted summary")
            summary_record['summary'] = summary_json

        summaries_table.put_item(Item=summary_record)
        logger.info(f"[AUDIT] Saved encrypted daily summary to DynamoDB for user {user_id} on {date}")
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
